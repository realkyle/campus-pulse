"""get_recommendations() and refresh_stats() with the database faked (contract: api/recommendations.md)."""
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

import events
import recommender as rec
from fixtures.sample_events import SAMPLE_EVENTS
from scoring import InteractionStats

NOW = datetime(2026, 11, 6, 12, tzinfo=UTC)


@pytest.fixture(autouse=True)
def sample_catalog():
    """The app serves no events until the live calendar loads, so load the samples."""
    events.update_live_cache(SAMPLE_EVENTS)
    previous_stats = rec._stats
    yield
    events.update_live_cache([])
    rec._stats = previous_stats


def _event(event_id, title, category="social"):
    return {"id": event_id, "title": title, "category": category, "building": "UW1",
            "date": "Nov 05, 2026", "description": "", "url": None}


def _click(event_id, category=None, series=None, user="me"):
    return {"hashed_netid": user, "event_id": event_id, "category": category,
            "series_key": series, "timestamp": NOW.isoformat()}


def recommend(user_rows, major=None, limit=10):
    with patch.object(rec, "get_user_interactions", return_value=user_rows):
        return rec.get_recommendations("me", major=major, limit=limit)


def test_cold_start_puts_the_major_first():
    ranked, mode = recommend([], major="Computer Science", limit=8)
    assert mode == "cold-start"
    tech = [e for e in SAMPLE_EVENTS if e["category"] == "technology"]
    assert [e["category"] for e in ranked[: len(tech)]] == ["technology"] * len(tech)
    assert ranked[0]["reason"] == "Matches your major"
    assert len(ranked) == 8


def test_unknown_major_still_returns_a_full_list():
    ranked, mode = recommend([], major="Underwater Basket Weaving", limit=5)
    assert mode == "cold-start"
    assert len(ranked) == 5


def test_clicks_make_it_personalized_with_reasons():
    ranked, mode = recommend([_click("evt-011", "arts", "spring art show student gallery")])
    assert mode == "personalized"
    assert ranked[0]["category"] == "arts"
    assert ranked[0]["reason"].startswith("Because you liked Arts")


def test_old_clicks_are_mapped_through_the_event_list():
    # Stored before the category/series columns existed: looked up by event ID.
    ranked, mode = recommend([_click("evt-011")])
    assert mode == "personalized"
    assert ranked[0]["category"] == "arts"


def test_each_event_has_required_fields_and_limit():
    ranked, _ = recommend([], limit=3)
    assert len(ranked) == 3
    for e in ranked:
        assert {"id", "title", "category", "reason"} <= e.keys()


@pytest.mark.parametrize("user_rows", [[], [_click("r1", "business", "resume workshop")]])
def test_staff_events_and_repeat_dates_are_never_recommended(user_rows):
    events.update_live_cache([
        _event("t1", "Campus Tour"),
        _event("s1", "Sponsored Research Virtual Office Hours for Faculty"),
        _event("t2", "Campus Tour"),
        _event("r1", "Resume Workshop", "business"),
    ])
    ranked, _ = recommend(user_rows)
    assert sorted(e["id"] for e in ranked) == ["r1", "t1"]


def test_refresh_stats_builds_aggregates():
    rows = [_click("evt-011", "arts", "spring art show student gallery", user=f"u{i}") for i in range(3)]
    with patch.object(rec, "fetch_all_interactions", return_value=rows):
        assert rec.refresh_stats(now=NOW)
    assert rec._stats.total_clicks == 3
    assert rec._stats.popularity == {"spring art show student gallery": 1.0}


def test_refresh_stats_keeps_previous_on_error():
    rec._stats = InteractionStats(total_clicks=7, popularity={"x": 1.0}, similar={})
    with patch.object(rec, "fetch_all_interactions", side_effect=RuntimeError("database down")):
        assert not rec.refresh_stats(now=NOW)
    assert rec._stats.total_clicks == 7
