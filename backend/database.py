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


INTERACTION_COLUMNS = "hashed_netid, event_id, timestamp, category, series_key"
PAGE_SIZE = 1000  # Supabase's default maximum rows per request


def log_interaction(hashed_netid: str, event_id: str, category: str, series_key: str) -> bool:
    """Record a click, with the event's category and series (they outlive the event). True on success."""
    try:
        _get_client().table("interactions").insert({
            "hashed_netid": hashed_netid,
            "event_id": event_id,
            "category": category,
            "series_key": series_key,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }).execute()
        return True
    except Exception as e:
        logger.error("log_interaction failed: %s", e)
        return False


def get_user_interactions(hashed_netid: str, limit: int = 500) -> list[dict]:
    """This user's most recent clicks. Empty on error, so recommendations degrade to cold start."""
    try:
        result = (
            _get_client()
            .table("interactions")
            .select(INTERACTION_COLUMNS)
            .eq("hashed_netid", hashed_netid)
            .order("timestamp", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.error("get_user_interactions failed: %s", e)
        return []


def fetch_all_interactions() -> list[dict]:
    """Every click, read page by page so Supabase's per-request row cap can't truncate it.

    Raises on error, so the caller can keep its previous aggregates instead of
    replacing them with empty ones.
    """
    rows: list[dict] = []
    start = 0
    while True:
        page = (
            _get_client()
            .table("interactions")
            .select(INTERACTION_COLUMNS)
            # id is a random UUID: sort by time first so pages are chronological
            # and a click inserted mid-read lands at the end, not inside a page.
            .order("timestamp")
            .order("id")
            .range(start, start + PAGE_SIZE - 1)
            .execute()
        ).data or []
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        start += PAGE_SIZE
