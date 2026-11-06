"""For You recommendations (contract: api/recommendations.md).

Student candidates (candidates.py) ranked by the hybrid score (scoring.py):
the user's own clicks are read per request; everyone's clicks are aggregated
by refresh_stats() once an hour in the background, never per request.
"""
import logging
from datetime import UTC, datetime

from candidates import series_key, student_candidates
from database import fetch_all_interactions, get_user_interactions
from events import get_all_events, get_event_by_id, infer_categories_from_major
from scoring import InteractionStats, UserProfile, rank

logger = logging.getLogger(__name__)

# Replaced as a whole by refresh_stats(); readers see either the old or the new value.
_stats = InteractionStats(total_clicks=0, popularity={}, similar={})


def resolve_event(event_id: str) -> tuple[str, str] | None:
    """(series_key, category) for clicks stored before those columns existed, if the event is still listed."""
    event = get_event_by_id(event_id)
    return (series_key(event["title"]), event["category"]) if event else None


def refresh_stats(now: datetime | None = None) -> bool:
    """Rebuild popularity and co-click aggregates from all clicks. Keeps the old ones on error."""
    global _stats
    try:
        rows = fetch_all_interactions()
    except Exception as e:
        logger.error("Keeping previous recommendation stats; reading clicks failed: %s", e)
        return False
    _stats = InteractionStats.build(rows, now=now or datetime.now(UTC), resolve=resolve_event)
    logger.info("Recommendation stats: %d clicks, %d popular series", _stats.total_clicks, len(_stats.popularity))
    return True


def get_recommendations(user_hash: str, major: str | None = None, limit: int = 10) -> tuple[list[dict], str]:
    """(ranked events, each with a "reason", mode). Mode is "personalized" once the user has clicks."""
    profile = UserProfile.from_rows(get_user_interactions(user_hash), resolve=resolve_event)
    major_categories = infer_categories_from_major(major) if major else []
    ranked = rank(student_candidates(get_all_events()), profile, _stats, major_categories, limit)
    return ranked, "personalized" if profile.clicks else "cold-start"
