import hashlib
import html
import logging
import re
from datetime import date, datetime
from typing import Callable, NamedTuple, Optional
from zoneinfo import ZoneInfo

import feedparser
import httpx

logger = logging.getLogger(__name__)

# Event dates are calendar days on campus, so "today" is computed in this zone.
CAMPUS_TZ = ZoneInfo("America/Los_Angeles")

RSS_FEEDS = [
    "https://www.trumba.com/calendars/bot_studentlife.rss",
    "https://www.trumba.com/calendars/bot_campus.rss",
]

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "technology": ["tech", "code", "coding", "hackathon", "software", "computer", "cyber",
                   "ai", "ml", "data", "web", "dev", "programming", "react", "python"],
    "science":    ["science", "biology", "chemistry", "physics", "research", "lab",
                   "astronomy", "environment", "ecology", "stem"],
    "business":   ["business", "entrepreneur", "startup", "finance", "career", "resume",
                   "interview", "networking", "job", "internship", "leadership", "accounting"],
    "arts":       ["art", "music", "film", "gallery", "performance", "theater", "creative",
                   "design", "photography", "exhibition", "open mic", "dance", "poetry"],
    "health":     ["health", "wellness", "mental", "meditation", "mindfulness", "fitness",
                   "nutrition", "therapy", "counseling", "stress", "de-stress", "yoga"],
    "sports":     ["sport", "soccer", "basketball", "volleyball", "intramural",
                   "recreation", "athletic", "hiking", "outdoor"],
}

BUILDING_ALIASES: dict[str, str] = {
    "library": "LIB",
    "lb1":     "LIB",
    "uw1":     "UW1",
    "uw2":     "UW2",
    "discovery hall": "DISC",
    "discovery": "DISC",
    "stem":    "STEM",
    "arc":     "ARC",
    "activities and recreation": "ARC",
    "husky hall": "HH",
    "north creek": "NCH",
    "summit":  "UW1",
}

DEFAULT_CATEGORY = "social"

# Whole words only, with an optional plural "s": "ai" must not match "said",
# "art" must not match "start".
_CATEGORY_PATTERNS = {
    category: re.compile(r"\b(?:" + "|".join(re.escape(k) for k in keywords) + r")s?\b", re.IGNORECASE)
    for category, keywords in CATEGORY_KEYWORDS.items()
}
_BUILDING_PATTERNS = [
    (re.compile(r"\b" + re.escape(alias) + r"\b", re.IGNORECASE), code)
    for alias, code in BUILDING_ALIASES.items()
]

_FEED_DATE = re.compile(r"(\d{4})/(\d{2})/(\d{2})")
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
# "Nov. 8, 2026", "Sept. 14, 2027", "December 6", "Dec. 6"
_HEADER_DATE = re.compile(
    r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?"
    r"|Sept?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+(\d{1,2})\b(?:,\s*(\d{4}))?",
    re.IGNORECASE,
)
_PARAGRAPH_BREAK = re.compile(r"<br\s*/?>\s*<br\s*/?>", re.IGNORECASE)
_LINE_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)
_METADATA_FIELD = re.compile(r"<b>\s*([^<:]+?)\s*</b>\s*:(.*?)(?=<br\s*/?>|$)", re.IGNORECASE | re.DOTALL)
_HANDSHAKE_LINK = re.compile(r'href="(https?://[^"]*joinhandshake\.com[^"]*)"', re.IGNORECASE)
_DESCRIPTION_STOPS = ("event interval", "registration link", "register in handshake", "register here")


class _ParsedEntry(NamedTuple):
    start: date
    end: date
    event: dict


def _to_text(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment)
    text = html.unescape(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _metadata(description_html: str) -> dict[str, str]:
    """The "<b>Field</b>: value" lines Trumba appends, keyed by lowercase field name."""
    return {name.strip().lower(): _to_text(value) for name, value in _METADATA_FIELD.findall(description_html)}


def _start_date(entry) -> date:
    """The structured <category>YYYY/MM/DD (Day)</category> date; never parsed from prose."""
    for tag in entry.get("tags") or []:
        match = _FEED_DATE.search(tag.get("term", ""))
        if match:
            return date(int(match[1]), int(match[2]), int(match[3]))
    raise ValueError("entry has no YYYY/MM/DD category")


def _header_dates(header_text: str, fallback_year: int) -> list[date]:
    """All dates in the description header, e.g. both ends of "Dec. 6 – Dec. 12, 2026".

    A date without a year takes the year of the next date that has one, minus one
    if its month is later ("Dec. 28 – Jan. 3, 2027" starts in 2026).
    """
    dates: list[date] = []
    next_year: Optional[int] = None
    next_month = 0
    for match in reversed(list(_HEADER_DATE.finditer(header_text))):
        month = _MONTHS[match[1][:3].lower()]
        if match[3]:
            year = int(match[3])
        elif next_year is not None:
            year = next_year - 1 if month > next_month else next_year
        else:
            year = fallback_year
        try:
            dates.append(date(year, month, int(match[2])))
        except ValueError:
            continue
        next_year, next_month = year, month
    return list(reversed(dates))


def _category(text: str) -> str:
    for category, pattern in _CATEGORY_PATTERNS.items():
        if pattern.search(text):
            return category
    return DEFAULT_CATEGORY


def _building(candidates: list[str], location_type: str) -> str:
    for text in candidates:
        for pattern, code in _BUILDING_PATTERNS:
            if text and pattern.search(text):
                return code
    if location_type.lower() == "online":
        return "ONLINE"
    return "CAMPUS"


def _parse_entry(entry) -> _ParsedEntry:
    start = _start_date(entry)
    description_html = entry.get("description", "") or entry.get("summary", "")
    # Trumba puts the location/date header first, then a blank line, then the body.
    parts = _PARAGRAPH_BREAK.split(description_html, maxsplit=1)
    header_html = parts[0]
    body_html = parts[1] if len(parts) > 1 else ""
    header_lines = [_to_text(line) for line in _LINE_BREAK.split(header_html)]
    header_text = " ".join(header_lines)

    header_dates = _header_dates(header_text, start.year)
    end = max([start, *header_dates])

    fields = _metadata(description_html)
    location_lines = [line for line in header_lines if line and not _HEADER_DATE.search(line)]
    building = _building(
        [fields.get("campus location", ""), fields.get("campus room", ""), *location_lines],
        fields.get("location type", ""),
    )

    body = _to_text(body_html)
    for stop in _DESCRIPTION_STOPS:
        index = body.lower().find(stop)
        if index != -1:
            body = body[:index].strip()

    title = entry.get("title", "Untitled Event")
    handshake = _HANDSHAKE_LINK.search(description_html)
    uid = entry.get("id") or entry.get("link") or (title + start.isoformat())
    return _ParsedEntry(start, end, {
        "id":          "live-" + hashlib.md5(uid.encode()).hexdigest()[:10],
        "title":       title,
        "category":    _category(f"{title} {body}"),
        "building":    building,
        "description": body[:250].strip() or "Click ↗ details to view on the campus events calendar.",
        "url":         handshake.group(1) if handshake else (entry.get("link") or None),
    })


def _parse_feed(feed_text: str, today: date) -> list[tuple[date, dict]]:
    """Upcoming events in one feed as (sort date, event) pairs."""
    entries = feedparser.parse(feed_text).entries
    upcoming: list[tuple[date, dict]] = []
    parsed = 0
    for entry in entries:
        try:
            item = _parse_entry(entry)
        except (ValueError, KeyError, TypeError) as e:
            logger.warning("Skipping malformed entry %r: %s", entry.get("title"), e)
            continue
        parsed += 1
        if item.end < today:
            continue
        in_progress = item.start < today
        event = dict(item.event)
        event["date"] = f"Through {item.end:%b %d, %Y}" if in_progress else f"{item.start:%b %d, %Y}"
        upcoming.append((today if in_progress else item.start, event))
    # A sudden drop in this ratio is how a parsing bug shows up in the logs.
    logger.info("parsed %d of %d entries, %d upcoming", parsed, len(entries), len(upcoming))
    return upcoming


def _download(url: str) -> str:
    response = httpx.get(url, timeout=10, follow_redirects=True)
    response.raise_for_status()
    return response.text


def fetch_live_events(
    limit: int = 200,
    today: Optional[date] = None,
    get_text: Callable[[str], str] = _download,
) -> tuple[list[dict], bool]:
    """Fetch both calendar feeds and return (upcoming events, any_feed_ok).

    Events are deduplicated by ID across feeds and sorted by the date they're
    (still) happening, then title. `today` and `get_text` are injectable so tests
    can pin the date and serve fixture files instead of the network.
    """
    today = today or datetime.now(CAMPUS_TZ).date()
    seen: set[str] = set()
    upcoming: list[tuple[date, dict]] = []
    any_ok = False

    for url in RSS_FEEDS:
        try:
            parsed = _parse_feed(get_text(url), today)
        except Exception as e:
            logger.error("Failed to fetch %s: %s", url, e)
            continue
        any_ok = True
        for sort_date, event in parsed:
            if event["id"] not in seen:
                seen.add(event["id"])
                upcoming.append((sort_date, event))

    upcoming.sort(key=lambda pair: (pair[0], pair[1]["title"]))
    return [event for _, event in upcoming[:limit]], any_ok
