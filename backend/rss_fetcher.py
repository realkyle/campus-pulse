import calendar
import hashlib
import html
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import feedparser
import httpx

logger = logging.getLogger(__name__)

# The official UW Alert blog. (The previous URL, /safety/alert/feed/, was a
# WordPress *comments* feed that is always empty.)
ALERT_FEED_URL = "https://emergency.uw.edu/feed/"

# The feed is a blog that keeps months of posts; only recent ones are current.
RECENT_WINDOW = timedelta(hours=48)

# Caps what is sent to the AI per alert (cost and prompt size).
MAX_TEXT_CHARS = 2000


def _download(url: str) -> str:
    # httpx instead of letting feedparser download: it has a timeout (a hung
    # server can't stall the alert loop) and ships its own CA certificates.
    response = httpx.get(url, timeout=10, follow_redirects=True)
    response.raise_for_status()
    return response.text


def _plain_text(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment)
    text = html.unescape(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _published(entry) -> Optional[datetime]:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)


def fetch_alerts(
    now: Optional[datetime] = None,
    get_text: Callable[[str], str] = _download,
) -> tuple[list[dict], bool]:
    """Return (recent alerts, feed_ok). Each alert has id, raw_text, published.

    feed_ok is False when the feed can't be downloaded or the response isn't a
    feed at all (e.g. the URL now serves an HTML page), so a broken source shows
    up as "feed unavailable" instead of a healthy-looking empty list.
    `now` and `get_text` are injectable for tests.
    """
    now = now or datetime.now(timezone.utc)
    try:
        feed = feedparser.parse(get_text(ALERT_FEED_URL))
    except Exception as e:
        logger.error("Failed to fetch alert feed: %s", e)
        return [], False
    if not feed.version:
        logger.error("Alert feed URL did not return an RSS/Atom feed")
        return [], False

    alerts = []
    for entry in feed.entries:
        published = _published(entry)
        if published is None or now - published > RECENT_WINDOW:
            continue
        content = entry.get("content") or []
        body = content[0].get("value", "") if content else entry.get("summary", "")
        text = f"{_plain_text(entry.get('title', ''))}. {_plain_text(body)}"[:MAX_TEXT_CHARS]
        alerts.append({
            "id": hashlib.md5(text.encode()).hexdigest()[:12],
            "raw_text": text,
            "published": published.isoformat(),
        })

    hours = int(RECENT_WINDOW.total_seconds() // 3600)
    logger.info("Alert feed: %d of %d posts within the last %d hours", len(alerts), len(feed.entries), hours)
    return alerts, True
