from unittest.mock import patch
import pytest

import events
import recommender as rec
from fixtures.sample_events import SAMPLE_EVENTS


@pytest.fixture(autouse=True)
def sample_catalog():
    """The app serves no events until the live calendar loads, so load the samples."""
    events.update_live_cache(SAMPLE_EVENTS)
    yield
    events.update_live_cache([])


def _make_interactions(n_global: int, n_user: int, user_id: str = "testhash") -> list[dict]:
    rows = [{"hashed_netid": user_id, "event_id": f"evt-{i}"} for i in range(n_user)]
    rows += [{"hashed_netid": f"other-{i}", "event_id": f"evt-{i}"} for i in range(n_global - n_user)]
    return rows


# ── Cold-start ────────────────────────────────────────────────────────────────

def test_coldstart_with_known_major():
    with (
        patch.object(rec, "get_total_interaction_count", return_value=0),
        patch.object(rec, "get_user_interaction_count", return_value=0),
        patch.object(rec, "get_popular_event_ids", return_value=[]),
    ):
        events, mode = rec.get_recommendations("testhash", major="Computer Science", limit=8)
        assert mode == "cold-start"
        # The major's category first, then topped up with other events to fill the list.
        tech = [e for e in SAMPLE_EVENTS if e["category"] == "technology"]
        assert [e["category"] for e in events[: len(tech)]] == ["technology"] * len(tech)
        assert len(events) == 8


def test_coldstart_with_unknown_major_falls_back_to_popularity():
    with (
        patch.object(rec, "get_total_interaction_count", return_value=0),
        patch.object(rec, "get_user_interaction_count", return_value=0),
        patch.object(rec, "get_popular_event_ids", return_value=[]),
    ):
        events, mode = rec.get_recommendations("testhash", major="Underwater Basket Weaving")
        assert mode == "cold-start"
        assert len(events) > 0


# ── Popularity fallback ───────────────────────────────────────────────────────

def test_popularity_when_user_has_some_interactions_but_below_threshold():
    with (
        patch.object(rec, "get_total_interaction_count", return_value=0),
        patch.object(rec, "get_user_interaction_count", return_value=5),
        patch.object(rec, "get_popular_event_ids", return_value=[]),
    ):
        events, mode = rec.get_recommendations("testhash")
        assert mode == "popularity"
        assert len(events) > 0


def test_popularity_when_global_below_threshold_even_if_user_above():
    with (
        patch.object(rec, "get_total_interaction_count", return_value=10),
        patch.object(rec, "get_user_interaction_count", return_value=15),
        patch.object(rec, "get_popular_event_ids", return_value=[]),
    ):
        events, mode = rec.get_recommendations("testhash")
        # global < 50, so CF must not activate
        assert mode in ("popularity", "cold-start")
        assert mode != "collaborative-filtering"


# ── CF threshold gating ───────────────────────────────────────────────────────

def test_cf_does_not_activate_below_global_threshold():
    with (
        patch.object(rec, "get_total_interaction_count", return_value=49),
        patch.object(rec, "get_user_interaction_count", return_value=20),
        patch.object(rec, "get_popular_event_ids", return_value=[]),
    ):
        _, mode = rec.get_recommendations("testhash")
        assert mode != "collaborative-filtering"


def test_cf_activates_above_both_thresholds():
    rows = _make_interactions(n_global=60, n_user=15, user_id="testhash")
    with (
        patch.object(rec, "get_total_interaction_count", return_value=60),
        patch.object(rec, "get_user_interaction_count", return_value=15),
        patch.object(rec, "get_all_interactions", return_value=rows),
    ):
        _, mode = rec.get_recommendations("testhash")
        assert mode == "collaborative-filtering"


# ── Return shape ──────────────────────────────────────────────────────────────

def test_recommendations_respect_limit():
    with (
        patch.object(rec, "get_total_interaction_count", return_value=0),
        patch.object(rec, "get_user_interaction_count", return_value=0),
        patch.object(rec, "get_popular_event_ids", return_value=[]),
    ):
        events, _ = rec.get_recommendations("testhash", limit=3)
        assert len(events) <= 3


def test_each_event_has_required_fields():
    with (
        patch.object(rec, "get_total_interaction_count", return_value=0),
        patch.object(rec, "get_user_interaction_count", return_value=0),
        patch.object(rec, "get_popular_event_ids", return_value=[]),
    ):
        events, _ = rec.get_recommendations("testhash")
        assert events  # an empty list would make the loop below pass vacuously
        for e in events:
            assert "id" in e
            assert "title" in e
            assert "category" in e


# ── Candidate cleanup (recommender PR 1) ──────────────────────────────────────

def _with_catalog(catalog):
    events.update_live_cache(catalog)


def _event(event_id, title, category="social"):
    return {"id": event_id, "title": title, "category": category, "building": "UW1",
            "date": "Nov 05, 2026", "description": "", "url": None}


@pytest.mark.parametrize("user_count", [0, 5])  # cold start and popularity
def test_staff_events_and_repeat_dates_are_never_recommended(user_count):
    _with_catalog([
        _event("t1", "Campus Tour"),
        _event("s1", "Sponsored Research Virtual Office Hours for Faculty"),
        _event("t2", "Campus Tour"),
        _event("r1", "Resume Workshop", "business"),
    ])
    with (
        patch.object(rec, "get_total_interaction_count", return_value=0),
        patch.object(rec, "get_user_interaction_count", return_value=user_count),
        patch.object(rec, "get_popular_event_ids", return_value=[]),
    ):
        events_out, _ = rec.get_recommendations("testhash", limit=10)
    assert [e["id"] for e in events_out] == ["t1", "r1"]


def test_popularity_counts_clicks_on_any_date_of_a_series():
    _with_catalog([
        _event("r1", "Resume Workshop", "business"),
        _event("t1", "Campus Tour"),
        _event("t2", "Campus Tour"),   # a later date of the same tour
    ])
    with (
        patch.object(rec, "get_total_interaction_count", return_value=0),
        patch.object(rec, "get_user_interaction_count", return_value=3),
        patch.object(rec, "get_popular_event_ids", return_value=["t2"]),
    ):
        events_out, mode = rec.get_recommendations("testhash", limit=10)
    assert mode == "popularity"
    assert [e["id"] for e in events_out] == ["t1", "r1"]  # the tour's next date ranks first
