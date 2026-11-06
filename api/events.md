# Events API

Upcoming campus events, read hourly from the campus calendar's two Trumba RSS feeds and served from memory.

## `GET /api/events`

**200**
```json
{
  "events": [
    {
      "id": "live-1a2b3c4d5e",
      "title": "Resume Workshop",
      "category": "business",
      "building": "UW1",
      "date": "Nov 05, 2026",
      "description": "Short plain-text description…",
      "url": "https://…"
    }
  ],
  "count": 1,
  "source": "live"
}
```

| Field | Rules |
|---|---|
| `id` | `"live-"` + first 10 hex chars of MD5(feed GUID). Stable across refreshes, because stored clicks reference it. |
| `category` | One of `technology`, `science`, `business`, `arts`, `health`, `sports`, `social`. First category with a **whole-word** keyword match in title + description (a trailing `s` is allowed, e.g. "workshops"); otherwise `social`. |
| `building` | From the feed's "Campus location" field, else the location line of the description, normalized to a code (`UW1`, `UW2`, `LIB`, `DISC`, `STEM`, `ARC`, `HH`, `NCH`). `ONLINE` when the feed's "Location Type" is Online and no campus location is given. `CAMPUS` when unknown. |
| `date` | Display text. `"Nov 05, 2026"` for the start date; `"Through Nov 08, 2026"` for an ongoing or multi-day event that has already started. |
| `url` | A Handshake registration link if the description has one, else the calendar's event page. Never truncated. |
| `source` | `"live"` when events are available, `"none"` when the calendar hasn't been loaded. |

## Rules

- **Date** comes from the item's structured `<category>YYYY/MM/DD (Day)</category>`, not from prose.
- **End date** is the last date in the description's header (e.g. "Ongoing through Sunday, Nov. 8, 2026" or "Sunday, Dec. 6 – Saturday, Dec. 12, 2026"); without one, the end date is the start date.
- An event is **included while its end date is today or later**, comparing calendar dates in Pacific time (the campus time zone). Today's events are included.
- **Sorted** by the date it is (still) happening, then title; an event already in progress sorts as today. At most 200 events.
- **Deduplicated** by `id` across the two feeds.
- If the calendar has never loaded, `events` is empty. No sample or invented events are ever served.
- A failed hourly refresh keeps the previous list.
- Each refresh logs `parsed X of Y entries` per feed, so a parsing failure can't go unnoticed.

## Test plan (`backend/test_events_fetcher.py`, `backend/test_events.py`)

Fixture: `backend/fixtures/trumba_sample.rss`, real feed structure with invented text (no real names or emails).

1. Abbreviated months ("Nov.", "Sept.") parse; the date comes from `<category>`.
2. Past events are dropped; today's events are kept (fixed "today").
3. An ongoing event that started before today but ends after it is kept, shown as "Through …", sorted as today.
4. A multi-day range ("Dec. 6 – Dec. 12") gets the right end date, including one crossing a year boundary.
5. Results are sorted by date, then title.
6. Online-only events → `ONLINE`; "Campus location" wins over everything else; unknown → `CAMPUS`.
7. Categories: whole words only ("said" isn't `technology`, "start" isn't `arts`); plurals match.
8. Registration URLs are intact.
9. IDs are stable and match the existing derivation; duplicates across feeds appear once.
10. `get_all_events()` is empty before any load; `get_event_by_id` works after `update_live_cache`.
11. `/api/events` reports `source: "none"` and an empty list when nothing is loaded.
