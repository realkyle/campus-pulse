import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_KEY"]
        _client = create_client(url, key)
    return _client


def log_interaction(hashed_netid: str, event_id: str) -> bool:
    """Record that a user viewed/clicked an event. Returns True on success."""
    try:
        _get_client().table("interactions").insert({
            "hashed_netid": hashed_netid,
            "event_id": event_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }).execute()
        return True
    except Exception as e:
        logger.error("log_interaction failed: %s", e)
        return False


def get_user_interaction_count(hashed_netid: str) -> int:
    """How many interactions this specific user has logged."""
    try:
        result = (
            _get_client()
            .table("interactions")
            .select("id", count="exact")
            .eq("hashed_netid", hashed_netid)
            .execute()
        )
        return result.count or 0
    except Exception as e:
        logger.error("get_user_interaction_count failed: %s", e)
        return 0


def get_total_interaction_count() -> int:
    """Total interactions across all users (used for global threshold check)."""
    try:
        result = (
            _get_client()
            .table("interactions")
            .select("id", count="exact")
            .execute()
        )
        return result.count or 0
    except Exception as e:
        logger.error("get_total_interaction_count failed: %s", e)
        return 0


def get_all_interactions() -> list[dict]:
    """Return all interaction rows for building the collaborative filtering matrix."""
    try:
        result = (
            _get_client()
            .table("interactions")
            .select("hashed_netid, event_id")
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.error("get_all_interactions failed: %s", e)
        return []


def get_popular_event_ids(days: int = 7, limit: int = 20) -> list[str]:
    """
    Return event_ids ranked by interaction count in the past `days` days.
    Used as the popularity fallback when CF thresholds aren't met.
    """
    try:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        result = (
            _get_client()
            .table("interactions")
            .select("event_id")
            .gte("timestamp", cutoff)
            .execute()
        )
        rows = result.data or []
        counts: dict[str, int] = {}
        for row in rows:
            eid = row["event_id"]
            counts[eid] = counts.get(eid, 0) + 1
        ranked = sorted(counts, key=lambda e: counts[e], reverse=True)
        return ranked[:limit]
    except Exception as e:
        logger.error("get_popular_event_ids failed: %s", e)
        return []
