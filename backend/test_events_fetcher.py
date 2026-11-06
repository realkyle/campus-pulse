"""Tests for parsing the campus calendar feeds (contract: api/events.md)."""
import hashlib
import logging
from datetime import date
from pathlib import Path

import pytest

from events_fetcher import RSS_FEEDS, fetch_live_events

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 5)


def feed_texts(campus: str = "trumba_campus.rss", studentlife: str = "trumba_studentlife.rss"):
    """A fake downloader serving the sanitized fixture feeds by URL."""
    files = {RSS_FEEDS[0]: studentlife, RSS_FEEDS[1]: campus}

    def get_text(url: str) -> str:
        return (FIXTURES / files[url]).read_text(encoding="utf-8")

    return get_text


def load(today: date = TODAY) -> dict[str, dict]:
    events, ok = fetch_live_events(today=today, get_text=feed_texts())
    assert ok
    return {e["title"]: e for e in events}


def test_upcoming_events_sorted_by_date_then_title():
    events, _ = fetch_live_events(today=TODAY, get_text=feed_texts())
    assert [e["title"] for e in events] == [
        "Holiday Plant Sale",        # ongoing since Oct 1 → sorts as today
        "Resume Workshop",           # today
        "Staff Appreciation Party",  # today
        "AI Community of Practice",  # Nov 6
        "Intramural Sports Signups", # Nov 7
        "Study Abroad Week",         # Dec 6
        "Winter Reading Challenge",  # Dec 28
        "Fall Kickoff",              # Sept 14, 2027 ("Sept." abbreviation)
    ]


def test_past_events_dropped_and_todays_kept():
    events = load()
    assert "Old Lecture" not in events
    assert events["Resume Workshop"]["date"] == "Nov 05, 2026"


def test_ongoing_event_shows_end_date():
    assert load()["Holiday Plant Sale"]["date"] == "Through Nov 08, 2026"


def test_ongoing_event_dropped_after_it_ends():
    assert "Holiday Plant Sale" not in load(today=date(2026, 11, 9))


def test_multi_day_event_across_new_year():
    assert load(today=date(2027, 1, 2))["Winter Reading Challenge"]["date"] == "Through Jan 03, 2027"
    assert "Winter Reading Challenge" not in load(today=date(2027, 1, 4))


def test_future_multi_day_event_shows_start_date():
    assert load()["Study Abroad Week"]["date"] == "Dec 06, 2026"


@pytest.mark.parametrize("title, building", [
    ("Resume Workshop", "UW1"),             # Campus location "Founder's Hall (UW1)"
    ("Study Abroad Week", "LIB"),           # "Library - LBA (Annex)"
    ("Fall Kickoff", "ARC"),                # "Activities & Recreation Center (ARC)"
    ("AI Community of Practice", "ONLINE"), # Location Type: Online
    ("Winter Reading Challenge", "ONLINE"),
    ("Holiday Plant Sale", "CAMPUS"),       # in person, no location given
    ("Staff Appreciation Party", "CAMPUS"), # unknown location name
])
def test_building(title, building):
    assert load()[title]["building"] == building


@pytest.mark.parametrize("title, category", [
    ("Resume Workshop", "business"),
    ("AI Community of Practice", "technology"),  # whole word "AI"
    ("Intramural Sports Signups", "sports"),     # plural of "sport"
    ("Staff Appreciation Party", "social"),      # "said"/"chair" aren't "ai"; "start"/"party" aren't "art"
])
def test_category_uses_whole_words(title, category):
    assert load()[title]["category"] == category


def test_registration_link_is_intact():
    assert load()["Resume Workshop"]["url"] == "https://uw.joinhandshake.com/stu/events/12345?ref=cat"


def test_event_page_link_when_no_registration_link():
    assert load()["Fall Kickoff"]["url"] == "https://calendar.example.edu/event?eventid=1007"


def test_description_excludes_header_and_metadata():
    description = load()["Resume Workshop"]["description"]
    assert description.startswith("Bring a draft resume")
    assert "Event interval" not in description
    assert "Nov. 5" not in description


def test_ids_are_stable_and_duplicates_removed():
    events, _ = fetch_live_events(today=TODAY, get_text=feed_texts())
    resume = [e for e in events if e["title"] == "Resume Workshop"]
    expected = "live-" + hashlib.md5(b"http://uid.trumba.com/event/1001").hexdigest()[:10]
    assert [e["id"] for e in resume] == [expected]


def test_one_failed_feed_keeps_the_other():
    healthy = feed_texts()

    def flaky(url: str) -> str:
        if url == RSS_FEEDS[0]:
            raise OSError("network down")
        return healthy(url)

    events, ok = fetch_live_events(today=TODAY, get_text=flaky)
    assert ok
    assert "Intramural Sports Signups" not in [e["title"] for e in events]
    assert "Resume Workshop" in [e["title"] for e in events]


def test_all_feeds_failing_reports_not_ok():
    def down(url: str) -> str:
        raise OSError("network down")

    assert fetch_live_events(today=TODAY, get_text=down) == ([], False)


def test_logs_parse_rate(caplog):
    with caplog.at_level(logging.INFO, logger="events_fetcher"):
        fetch_live_events(today=TODAY, get_text=feed_texts())
    assert "parsed 8 of 8 entries" in caplog.text
