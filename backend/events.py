# ── Live event cache ──────────────────────────────────────────────────────────
# Filled hourly by events_loop in main.py. Empty until the first successful
# fetch: invented events are never served (api/events.md).

# The list and its ID index are swapped together as one tuple, so a reader on
# another thread never sees a new list with an old index.
_cache: tuple[list[dict], dict[str, dict]] = ([], {})


def update_live_cache(events: list[dict]) -> None:
    """Replace the cached events (called after each successful hourly fetch)."""
    global _cache
    _cache = (events, {e["id"]: e for e in events})


def get_all_events() -> list[dict]:
    """Upcoming events, soonest first; empty if the calendar hasn't loaded yet."""
    return _cache[0]


def get_event_by_id(event_id: str) -> dict | None:
    return _cache[1].get(event_id)


# Maps declared UW major keywords to event categories for cold-start seeding.
MAJOR_TO_CATEGORIES: dict[str, list[str]] = {
    "css": ["technology", "business"],
    "csse": ["technology"],
    "computer": ["technology"],
    "business": ["business", "social"],
    "accounting": ["business"],
    "biology": ["science", "health"],
    "chemistry": ["science"],
    "physics": ["science", "technology"],
    "psychology": ["health", "social"],
    "nursing": ["health", "science"],
    "education": ["social", "arts"],
    "english": ["arts", "social"],
    "math": ["science", "technology"],
    "environmental": ["science"],
    "art": ["arts"],
    "film": ["arts"],
    "sociology": ["social"],
    "economics": ["business"],
}


def infer_categories_from_major(major: str) -> list[str]:
    major_lower = major.lower()
    for keyword, cats in MAJOR_TO_CATEGORIES.items():
        if keyword in major_lower:
            return cats
    return []
