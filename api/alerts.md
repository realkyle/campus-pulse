# Alerts API

Current emergency alerts from the official UW Alert blog (`https://emergency.uw.edu/feed/`), structured by GPT-4o-mini and refreshed every 5 minutes.

## `GET /api/alerts`

**200**
```json
{
  "alerts": [
    {
      "id": "3f2a9c1b7d4e",
      "raw_text": "UW Alert: … (title. plain-text body)",
      "building_name": "UW1",
      "incident_type": "Police Activity",
      "severity": "high",
      "recommended_action": "Avoid the area.",
      "scope": "campus",
      "coordinates": [47.75884, -122.19067],
      "published": "2026-11-05T17:56:15+00:00",
      "headline": "…",
      "safety_brief": "…"
    }
  ],
  "last_updated": "2026-11-06T03:00:00+00:00",
  "ai_available": true,
  "feed_available": true
}
```

| Field | Rules |
|---|---|
| `scope` | `campus`: about this campus, **pinned** on the map. `university`: affects all of UW (e.g. a drill, smoke advisory), shown in the alert list **without a pin**. |
| `coordinates` | `[lat, lng]` for `campus` alerts; `null` for `university` alerts. |
| `building_name` | A code from the coordinate table (`UW1`, `UW2`, `DISC`, `LIB`, `ARC`, `HH`, `NCH`, `CC`) or `CAMPUS`. |
| `severity` | `low` \| `medium` \| `high`. |
| `headline`, `safety_brief` | Only for `high` severity, when the second AI call succeeds. |
| `published` | ISO 8601 UTC. |
| `feed_available` | `false` if the feed couldn't be downloaded **or the response isn't an RSS/Atom feed** (e.g. the URL now serves an HTML page). |
| `ai_available` | `false` only if OpenAI couldn't be reached (network, auth, outage) during this refresh. A malformed AI answer doesn't count. |

## Rules

- **Recency:** only posts published in the last **48 hours** are considered. The feed is a blog that keeps months of posts.
- **Scope:** the AI labels each alert `campus`, `university_wide` or `other_campus`. An alert whose text names this campus is always `campus`, whatever the AI says. `other_campus` alerts are **left out**.
- **AI failure:** the alert is still shown with its raw text, severity `medium`: pinned at the campus center if it names this campus, otherwise listed as `university` without a pin.
- **Cost:** each alert text is sent to the AI once; the result (including "left out") is reused while the post stays in the 48-hour window. An edited post has new text and is analyzed again.
- Text sent to the AI is the post title plus its body with HTML removed, at most 2,000 characters.
- Demo pins (`api/demo.md`) are `campus` alerts.

## Test plan

- `test_rss_fetcher.py` (sanitized fixture of the real feed structure): recent posts kept, old posts dropped (fixed "now"); HTML stripped; title + body combined; an HTML page instead of a feed → `feed_available: false`; download error → `false`; text capped at 2,000 characters.
- `test_nlp_summarizer_errors.py` (fake OpenAI client): connection/auth error → `ai_available: false`; invalid JSON or a missing field → summary `None` but `ai_available: true`; a missing `OPENAI_API_KEY` → `ai_available: false`; scope defaults to `university_wide` when omitted.
- `test_alert_pipeline.py`: campus → pinned; university-wide → `coordinates: null`; other campus → left out and not re-analyzed; campus name in the text overrides the AI; AI failure with/without the campus name.
- `test_building_coords.py`: whole-word matching (`"UW"` is not `UW1`).
