"""The offline evaluation harness on synthetic data with clear taste groups."""
from datetime import UTC, datetime, timedelta

from evaluate_recommender import leave_last_out

START = datetime(2026, 11, 1, tzinfo=UTC)
TECH = ["hackathon", "web dev workshop", "ai talk", "cyber panel", "data night", "code club"]
ARTS = ["art walk", "open mic", "film night", "gallery tour", "poetry slam", "dance show"]


def rows_for(user: str, series: list[str], category: str) -> list[dict]:
    return [{"hashed_netid": user, "event_id": f"{user}-{i}", "series_key": s, "category": category,
             "timestamp": (START + timedelta(hours=i)).isoformat()} for i, s in enumerate(series)]


def test_hybrid_beats_popularity_when_tastes_differ():
    rows = []
    for i in range(6):
        rows += rows_for(f"tech{i}", TECH[i:] + TECH[:i], "technology")
    for i in range(3):
        rows += rows_for(f"arts{i}", ARTS[i:] + ARTS[:i], "arts")
    result = leave_last_out(rows, resolve=lambda event_id: None, k=5)
    assert result["users_evaluated"] == 9
    # Popularity recommends the majority's (tech) series to everyone, so it misses the arts fans.
    assert result["hybrid_hit_rate"] > result["popularity_hit_rate"]


def test_users_with_one_known_click_are_skipped():
    rows = rows_for("u1", ["hackathon"], "technology")
    assert leave_last_out(rows, resolve=lambda event_id: None)["users_evaluated"] == 0
