"""Tests for the live event cache and GET /api/events (contract: api/events.md)."""
import pytest
from fastapi.testclient import TestClient

import events
import main

client = TestClient(main.app)

SAMPLE = [
    {"id": "live-a", "title": "A", "category": "social", "building": "UW1", "date": "Nov 05, 2026", "description": "", "url": None},
    {"id": "live-b", "title": "B", "category": "arts", "building": "ONLINE", "date": "Nov 06, 2026", "description": "", "url": None},
]


@pytest.fixture(autouse=True)
def empty_cache():
    events.update_live_cache([])
    yield
    events.update_live_cache([])


def test_no_events_before_the_calendar_loads():
    assert events.get_all_events() == []
    assert events.get_event_by_id("evt-001") is None


def test_lookup_after_load():
    events.update_live_cache(SAMPLE)
    assert events.get_all_events() == SAMPLE
    assert events.get_event_by_id("live-b")["title"] == "B"
    assert events.get_event_by_id("missing") is None


def test_api_reports_none_when_nothing_loaded():
    assert client.get("/api/events").json() == {"events": [], "count": 0, "source": "none"}


def test_api_serves_live_events():
    events.update_live_cache(SAMPLE)
    body = client.get("/api/events").json()
    assert body["source"] == "live"
    assert body["count"] == 2
    assert [e["id"] for e in body["events"]] == ["live-a", "live-b"]
