# Buses API

Next arrivals at the stops near campus, from the OneBusAway (OBA) Puget Sound API.

## `GET /api/buses`

**200**
```json
{
  "stops": [
    {
      "id": "1_76224",
      "name": "Beardslee Blvd & 108th Ave NE",
      "lat": 47.762245,
      "lon": -122.1959,
      "arrivals": [
        {"route": "535", "headsign": "Lynnwood", "minutes": 4, "predicted": true}
      ]
    }
  ],
  "updated_at": "2026-11-06T08:00:00+00:00"
}
```

| Field | Rules |
|---|---|
| `minutes` | Whole minutes until arrival, **computed when the request is answered** from the stored arrival time. Never stale. |
| `predicted` | `true` if OBA has a live (GPS) prediction; otherwise the timetable time is used |
| `arrivals` | Sorted by `minutes`, at most 8 per stop. Buses that already arrived are left out. Empty if the stop has no data newer than 10 minutes. |
| `updated_at` | When OBA last answered successfully (ISO 8601 UTC); `null` if never |

The old `time` field was removed: it was formatted in the server's time zone (UTC on Render), and the UI never showed it.

## Rules

- **Shared cache:** OBA is called at most once per 30 seconds for all users together (TTL cache).
- **Single flight:** when the cache expires, concurrent requests wait for one refresh instead of each calling OBA.
- **Parallel:** the 3 stops are fetched concurrently (8 s timeout each).
- **Partial failure:** a stop whose request fails keeps its last good arrivals (still subject to the 10-minute limit); the others update normally.
- A failed refresh still counts as a refresh for the 30-second window, so an OBA outage isn't hammered.

## Test plan (`backend/test_bus_fetcher.py`, fake OBA via `httpx.MockTransport`, fake clock)

1. First request fetches each stop once; a second within 30 s makes no calls; after 30 s it refetches.
2. 10 concurrent requests on an expired cache → one refresh (3 calls).
3. Stops are fetched in parallel (3 × 0.2 s slow responses finish in well under 0.6 s).
4. `minutes` decreases as time passes without a refetch; departed buses disappear.
5. Data older than 10 minutes is dropped.
6. One stop failing keeps its last good data; the others update.
7. Predicted time preferred; scheduled used otherwise; entries with no time skipped; at most 8, sorted.
8. Response has no `time` field.
