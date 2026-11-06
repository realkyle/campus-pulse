"""Ranking rules (contract: api/recommendations.md, Ranking). Pure functions, no database."""
from datetime import datetime, timedelta, timezone

import pytest

from scoring import (
    CO_CLICK_MIN_CLICKS,
    InteractionStats,
    UserProfile,
    rank,
)

NOW = datetime(2026, 11, 6, 12, tzinfo=timezone.utc)


def event(event_id: str, title: str, category: str = "social") -> dict:
    return {"id": event_id, "title": title, "category": category}


def click(series: str, category: str = "social", user: str = "me", days_ago: float = 1) -> dict:
    return {"hashed_netid": user, "event_id": f"id-{series}", "series_key": series,
            "category": category, "timestamp": (NOW - timedelta(days=days_ago)).isoformat()}


CATALOG = [  # soonest first
    event("a", "Art Walk", "arts"),
    event("h", "Hackathon", "technology"),
    event("c", "Chess Club"),
    event("w", "Web Dev Workshop", "technology"),
]

EMPTY_STATS = InteractionStats.build([], now=NOW, resolve=lambda event_id: None)


def ids(ranked) -> list[str]:
    return [e["id"] for e in ranked]


def profile(*clicks: dict) -> UserProfile:
    return UserProfile.from_rows(list(clicks), resolve=lambda event_id: None)


# ── Building blocks ───────────────────────────────────────────────────────────

def test_profile_category_shares_and_series():
    p = profile(click("hackathon", "technology"), click("web dev workshop", "technology"), click("chess club"))
    assert p.clicks == 3
    assert p.category_share == pytest.approx({"technology": 2 / 3, "social": 1 / 3})
    assert p.series == {"hackathon", "web dev workshop", "chess club"}


def test_old_rows_are_mapped_through_the_event_list():
    old_row = {"hashed_netid": "me", "event_id": "live-1", "series_key": None, "category": None,
               "timestamp": NOW.isoformat()}
    p = UserProfile.from_rows([old_row], resolve=lambda event_id: ("hackathon", "technology"))
    assert p.category_share == {"technology": 1.0}
    # Unknown events (one-offs that already happened) are skipped, not guessed.
    assert UserProfile.from_rows([old_row], resolve=lambda event_id: None).clicks == 0


def test_popularity_counts_only_the_last_7_days():
    rows = [click("chess club", days_ago=1), click("chess club", user="u2", days_ago=2), click("art walk", days_ago=30)]
    stats = InteractionStats.build(rows, now=NOW, resolve=lambda event_id: None)
    assert stats.popularity == {"chess club": 1.0}
    assert stats.total_clicks == 3


def test_co_click_similarity_is_cosine_over_users():
    rows = [click("hackathon", user="u1"), click("web dev workshop", user="u1"),
            click("hackathon", user="u2"), click("web dev workshop", user="u2"),
            click("hackathon", user="u3"), click("chess club", user="u3")]
    stats = InteractionStats.build(rows, now=NOW, resolve=lambda event_id: None)
    # hackathon: 3 users, web dev: 2, both: 2  →  2 / sqrt(3·2)
    assert stats.similar["hackathon"]["web dev workshop"] == pytest.approx(2 / (3 * 2) ** 0.5)
    assert "hackathon" not in stats.similar["hackathon"]


# ── Ranking ───────────────────────────────────────────────────────────────────

def test_technology_fan_gets_technology_first():
    ranked = rank(CATALOG, profile(click("old tech talk", "technology")), EMPTY_STATS, major_categories=[], limit=4)
    assert ids(ranked)[:2] == ["h", "w"]
    assert ranked[0]["reason"] == "Because you liked Technology events"


def test_cold_start_puts_the_major_first():
    ranked = rank(CATALOG, profile(), EMPTY_STATS, major_categories=["arts"], limit=4)
    assert ids(ranked)[0] == "a"
    assert ranked[0]["reason"] == "Matches your major"


def test_previously_clicked_series_ranks_higher():
    ranked = rank(CATALOG, profile(click("chess club")), EMPTY_STATS, major_categories=[], limit=4)
    assert ids(ranked)[0] == "c"
    assert ranked[0]["reason"] == "Another date of an event you opened"


def test_the_exact_event_opened_gets_no_series_boost():
    opened = {"hashed_netid": "me", "event_id": "c", "series_key": "chess club", "category": "social",
              "timestamp": NOW.isoformat()}
    p = UserProfile.from_rows([opened], resolve=lambda event_id: None)
    catalog = [event("c", "Chess Club"), event("c2", "Chess Club")]  # same series, next date
    ranked = rank(catalog, p, EMPTY_STATS, major_categories=[], limit=2)
    assert ids(ranked)[0] == "c2"
    assert ranked[0]["reason"] == "Another date of an event you opened"
    assert ranked[1]["reason"] == "Because you liked Social events"


def _co_click_rows(n_extra_users: int) -> list[dict]:
    # Many users who clicked the Hackathon also clicked the Art Walk.
    rows = []
    for i in range(n_extra_users):
        rows += [click("hackathon", "technology", user=f"u{i}", days_ago=20),
                 click("art walk", "arts", user=f"u{i}", days_ago=20)]
    return rows


def test_co_clicks_are_ignored_below_the_threshold():
    rows = _co_click_rows(n_extra_users=(CO_CLICK_MIN_CLICKS // 2) - 1)  # fewer than 50 clicks
    stats = InteractionStats.build(rows, now=NOW, resolve=lambda event_id: None)
    ranked = rank(CATALOG, profile(click("hackathon", "technology")), stats, major_categories=[], limit=4)
    assert ranked[ids(ranked).index("a")]["reason"] != "Popular with students who like what you like"


def test_co_clicks_lift_related_series_above_the_threshold():
    rows = _co_click_rows(n_extra_users=CO_CLICK_MIN_CLICKS // 2)  # exactly 50 clicks
    stats = InteractionStats.build(rows, now=NOW, resolve=lambda event_id: None)
    ranked = rank(CATALOG, profile(click("hackathon", "technology")), stats, major_categories=[], limit=4)
    art = ranked[ids(ranked).index("a")]
    assert art["reason"] == "Popular with students who like what you like"
    assert ids(ranked).index("a") < ids(ranked).index("c")  # beats the unrelated Chess Club


def test_popularity_breaks_ties_among_equals():
    rows = [click("chess club", user="u1"), click("chess club", user="u2")]
    stats = InteractionStats.build(rows, now=NOW, resolve=lambda event_id: None)
    catalog = [event("x", "Board Game Night"), event("c", "Chess Club")]
    ranked = rank(catalog, profile(), stats, major_categories=[], limit=2)
    assert ids(ranked) == ["c", "x"]
    assert ranked[0]["reason"] == "Popular on campus this week"


def test_without_any_signal_soonest_comes_first():
    ranked = rank(CATALOG, profile(), EMPTY_STATS, major_categories=[], limit=4)
    assert ids(ranked) == ["a", "h", "c", "w"]
    assert {e["reason"] for e in ranked} == {"Coming up soon"}


def test_limit_and_original_events_untouched():
    ranked = rank(CATALOG, profile(), EMPTY_STATS, major_categories=[], limit=2)
    assert len(ranked) == 2
    assert "reason" not in CATALOG[0]  # rank() returns copies
