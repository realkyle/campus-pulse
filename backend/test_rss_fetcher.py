"""Tests for reading the UW Alert blog feed (contract: api/alerts.md)."""
from datetime import UTC, datetime
from pathlib import Path

import rss_fetcher
from rss_fetcher import ALERT_FEED_URL, fetch_alerts

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 11, 6, 3, 0, tzinfo=UTC)


def serve(filename: str):
    def get_text(url: str) -> str:
        assert url == ALERT_FEED_URL
        return (FIXTURES / filename).read_text(encoding="utf-8")
    return get_text


def load():
    alerts, ok = fetch_alerts(now=NOW, get_text=serve("uw_alert_blog.rss"))
    assert ok
    return alerts


def test_feed_url_is_the_uw_alert_blog():
    # The old URL was a WordPress *comments* feed that is always empty.
    assert ALERT_FEED_URL == "https://emergency.uw.edu/feed/"


def test_only_posts_from_the_last_48_hours():
    titles = [a["raw_text"].split(".")[0] for a in load()]
    assert len(titles) == 3
    assert not any("Hazardous materials" in t for t in titles)


def test_text_is_title_plus_plain_body():
    first = load()[0]["raw_text"]
    assert first.startswith("UW Alert – Police activity near UW1. UPDATE at 10:15 a.m.:")
    assert "Avoid the area & follow police instructions." in first
    assert "<" not in first


def test_text_is_capped_for_the_ai():
    assert max(len(a["raw_text"]) for a in load()) == rss_fetcher.MAX_TEXT_CHARS


def test_published_is_iso_utc():
    assert load()[0]["published"] == "2026-11-05T17:56:15+00:00"


def test_id_changes_when_text_changes():
    ids = [a["id"] for a in load()]
    assert len(set(ids)) == 3
    assert all(len(i) == 12 for i in ids)


def test_html_page_instead_of_feed_is_not_ok():
    assert fetch_alerts(now=NOW, get_text=serve("not_a_feed.html")) == ([], False)


def test_download_error_is_not_ok():
    def down(url: str) -> str:
        raise OSError("timeout")
    assert fetch_alerts(now=NOW, get_text=down) == ([], False)
