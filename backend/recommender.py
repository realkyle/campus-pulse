import logging

from surprise import Dataset, Reader, SVD
import pandas as pd

logger = logging.getLogger(__name__)

from candidates import series_key, student_candidates
from database import get_all_interactions, get_total_interaction_count, get_user_interaction_count, get_popular_event_ids
from events import get_all_events, get_event_by_id, infer_categories_from_major

GLOBAL_THRESHOLD = 50   # total interactions needed before CF activates
USER_THRESHOLD = 10     # per-user interactions needed to use CF for that user


def _candidates() -> list[dict]:
    """Student events only, one (next) date per series, soonest first."""
    return student_candidates(get_all_events())


def _popularity_fallback(limit: int = 10) -> list[dict]:
    """Candidates whose series was clicked most in the past 7 days, then the rest by date.

    Popularity is counted per series: a click on any date of "Campus Tour" counts
    for the next date shown.
    """
    rank: dict[str, int] = {}
    for event_id in get_popular_event_ids(days=7, limit=50):
        event = get_event_by_id(event_id)
        if event:
            rank.setdefault(series_key(event["title"]), len(rank))
    candidates = _candidates()
    # Stable sort: popular series first in popularity order, the rest keep date order.
    ordered = sorted(candidates, key=lambda e: rank.get(series_key(e["title"]), len(rank)))
    return ordered[:limit]


def _coldstart(major: str | None, limit: int = 10) -> list[dict]:
    """
    For users with zero interactions: seed by declared major category if available,
    otherwise fall back to popularity.
    """
    popular = _popularity_fallback(limit=len(_candidates()))
    cats = infer_categories_from_major(major) if major else []
    # The major's categories first, then topped up with popular events so the
    # list is full even when few events match the major.
    seeded = [e for e in popular if e["category"] in cats]
    rest = [e for e in popular if e["category"] not in cats]
    return (seeded + rest)[:limit]


def _collaborative_filter(hashed_netid: str, limit: int = 10) -> list[dict]:
    """Train SVD on all interaction data and return top-N unseen events for this user."""
    rows = get_all_interactions()
    if not rows:
        return _popularity_fallback(limit)

    df = pd.DataFrame(rows)
    df["rating"] = 1.0

    reader = Reader(rating_scale=(0, 1))
    dataset = Dataset.load_from_df(df[["hashed_netid", "event_id", "rating"]], reader)
    trainset = dataset.build_full_trainset()

    model = SVD(n_factors=20, n_epochs=20, random_state=42)
    model.fit(trainset)

    seen_ids = {row["event_id"] for row in rows if row["hashed_netid"] == hashed_netid}
    candidates = [e for e in _candidates() if e["id"] not in seen_ids]

    scored = []
    for event in candidates:
        pred = model.predict(hashed_netid, event["id"])
        scored.append((event, pred.est))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [event for event, _ in scored[:limit]]


def get_recommendations(
    hashed_netid: str,
    major: str | None = None,
    limit: int = 10,
) -> tuple[list[dict], str]:
    """
    Returns (ranked_events, mode) where mode describes which strategy was used.

    Threshold rules from the proposal:
    - Global < 50 OR user < 10  →  popularity / cold-start
    - Global >= 50 AND user >= 10  →  collaborative filtering
    """
    total = get_total_interaction_count()
    user_count = get_user_interaction_count(hashed_netid)

    if total < GLOBAL_THRESHOLD or user_count < USER_THRESHOLD:
        if user_count == 0:
            events = _coldstart(major, limit)
            mode = "cold-start"
        else:
            events = _popularity_fallback(limit)
            mode = "popularity"
    else:
        try:
            events = _collaborative_filter(hashed_netid, limit)
            mode = "collaborative-filtering"
        except Exception as e:
            logger.error("CF failed, falling back to popularity: %s", e)
            events = _popularity_fallback(limit)
            mode = "popularity"

    return events, mode
