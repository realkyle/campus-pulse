# Demo alerts API

Temporary, fake alert pins used to demonstrate the map during presentations. They are merged into `GET /api/alerts` for 60 seconds. Only an admin may create or remove them.

## Authentication

Every endpoint below requires the header `X-Admin-Token`, which must equal the server's `DEMO_ADMIN_TOKEN` environment variable (compared in constant time).

- If `DEMO_ADMIN_TOKEN` is **not set**, the feature is off: every endpoint returns **404**, whatever the request contains.
- A missing or wrong token returns **401** before any input is validated, so unauthenticated callers learn nothing about valid inputs.

Interim design: a shared secret until login tokens are verified on the backend; it will then become an admin role in the access token.

## `POST /api/demo`

Create a demo pin.

| Query param | Type | Default | Rules |
|---|---|---|---|
| `building` | string | `UW1` | Case-insensitive; must be a known building code or name from `building_coords.BUILDING_COORDS` |
| `severity` | `low` \| `medium` \| `high` | `high` | |

**200**
```json
{"status": "ok", "pin_id": "demo-<hex>", "building": "UW1", "severity": "high", "expires_in": 60}
```

| Status | When |
|---|---|
| 401 | Missing or wrong `X-Admin-Token` |
| 404 | `DEMO_ADMIN_TOKEN` not set |
| 422 | Unknown `building`, or `severity` not `low`/`medium`/`high` |
| 429 | 5 demo pins are already active |

For `high` severity the server also asks the AI for a headline and safety brief; if that fails, the pin is still created without them.

## `DELETE /api/demo/{pin_id}`

Remove one demo pin. **200** `{"status": "removed", "pin_id": "…"}` · **404** if no active pin has that ID (or the feature is off) · **401** as above.

## `POST /api/demo/clear`

Remove all demo pins. **200** `{"status": "cleared"}` · **401** / **404** as above.

## Rules

- A pin is visible in `GET /api/alerts` from creation until 60 seconds later, then disappears without any request to remove it.
- At most 5 pins are active at once. The limit is enforced atomically, so concurrent requests can't exceed it.
- Pins live in server memory; a server restart removes them.

## Test plan (`backend/test_demo.py`)

1. Feature off (`DEMO_ADMIN_TOKEN` unset) → 404 for create, delete and clear, even with a token header.
2. Missing token → 401. Wrong token → 401.
3. Missing token **and** invalid severity → 401 (auth is checked first).
4. Valid token → 200; the pin appears in `GET /api/alerts`.
5. Unknown building → 422. Invalid severity → 422.
6. Sixth active pin → 429.
7. Pin is gone from `GET /api/alerts` after 60 seconds (controlled clock).
8. `DELETE /api/demo/{pin_id}` removes only that pin; an unknown ID → 404.
9. `POST /api/demo/clear` removes all pins.
10. High severity never calls the real AI in tests (triage is faked).
