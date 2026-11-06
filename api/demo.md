# Demo alerts API

Temporary, fake alert pins used to demonstrate the map during presentations. They are merged into `GET /api/alerts` for 60 seconds. Only an admin may create or remove them.

## Authentication

Every endpoint below requires `Authorization: Bearer <access token>` (same verification as `api/recommendations.md`) **and** the permission `demo:write` in the token's `permissions` claim. The permission comes from the `Admin` role in Auth0 (RBAC on the Campus Pulse API, with "Add Permissions in the Access Token").

| Request | Status |
|---|---|
| No or invalid token | **401** |
| Valid UW token without `demo:write` | **403** |
| Server not configured for sign-in | **503** |

Auth is checked before input is validated, so callers without the permission learn nothing about valid inputs. (This replaced the shared `DEMO_ADMIN_TOKEN` secret on 2026-11-06.)

## `GET /api/me`

The signed-in user, so the frontend can decide whether to show Demo Controls. **This only hides the controls; the demo endpoints still check the permission themselves.**

**200** `{"email": "student@uw.edu", "is_admin": false}`. 401/403/503 as above (without the `demo:write` requirement).

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
| 401 | No or invalid token |
| 403 | Token without `demo:write` |
| 422 | Unknown `building`, or `severity` not `low`/`medium`/`high` |
| 429 | 5 demo pins are already active |

For `high` severity the server also asks the AI for a headline and safety brief; if that fails, the pin is still created without them.

## `DELETE /api/demo/{pin_id}`

Remove one demo pin. **200** `{"status": "removed", "pin_id": "…"}` · **404** if no active pin has that ID · **401/403** as above.

## `POST /api/demo/clear`

Remove all demo pins. **200** `{"status": "cleared"}` · **401/403** as above.

## Rules

- A pin is visible in `GET /api/alerts` from creation until 60 seconds later, then disappears without any request to remove it.
- At most 5 pins are active at once. The limit is enforced atomically, so concurrent requests can't exceed it.
- Pins live in server memory; a server restart removes them.

## Test plan (`backend/test_demo.py`)

1. No token → 401; invalid token → 401; valid UW token without `demo:write` → 403, for create, delete and clear.
2. No permission **and** invalid severity → 403 (auth is checked first).
3. Admin token → 200; the pin appears in `GET /api/alerts`.
4. Unknown building → 422. Invalid severity → 422.
5. Sixth active pin → 429.
6. Pin is gone from `GET /api/alerts` after 60 seconds (controlled clock).
7. `DELETE /api/demo/{pin_id}` removes only that pin; an unknown ID → 404.
8. `POST /api/demo/clear` removes all pins.
9. High severity never calls the real AI in tests (triage is faked).
10. `GET /api/me` → `is_admin` true with `demo:write`, false without; 401 without a token.
11. The old `X-Admin-Token` header grants nothing.
