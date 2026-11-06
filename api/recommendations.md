# Recommendations and interactions API

Personalized events for a signed-in UW user, and logging which events they open. Both endpoints identify the user **only** from a verified Auth0 access token.

## Authentication (both endpoints)

Header: `Authorization: Bearer <access token>`. The frontend gets the token from its own `/auth/access-token` route.

The backend (`backend/auth.py`, dependency `get_current_user`) checks, in order:

| Check | Failure |
|---|---|
| `AUTH0_DOMAIN` and `AUTH0_AUDIENCE` are configured on the server | **503**: sign-in features unavailable |
| Header present, scheme `Bearer` | **401** |
| Signature valid (RS256 only) against the tenant's published keys (JWKS, cached) | **401** |
| `exp` in the future, `iss` = `https://<AUTH0_DOMAIN>/`, `aud` includes `AUTH0_AUDIENCE`, `sub` present | **401** |
| Claim `https://campus-pulse/email` ends in `@uw.edu` or `@washington.edu` | **403** |

401 responses include `WWW-Authenticate: Bearer`. The user's ID is `sha256(sub)` as 64 hex characters, stored as `hashed_netid`. It's the same value the browser used to compute, so earlier clicks stay linked. A request can never choose which user it acts as.

## `GET /api/recommendations`

| Query | Type | Default | Rules |
|---|---|---|---|
| `major` | string | none | Optional, free text (seeds cold start) |
| `limit` | int | 10 | 1–200, else **422** |

**200** `{"events": [ …event objects, see api/events.md… ], "mode": "cold-start" | "popularity" | "collaborative-filtering"}`

## `POST /api/interactions`

Body: `{"event_id": "live-1a2b3c4d5e"}`

| Status | When |
|---|---|
| 200 `{"recorded": true \| false}` | Event exists; `false` if the database write failed |
| 404 | `event_id` isn't a current event |
| 422 | Body missing or malformed |

## Test plan (`backend/test_auth.py`)

Tokens are signed with a test RSA key pair; the verifier is given the matching public key instead of downloading JWKS.

1. Valid UW token → 200; recommendations are computed for `sha256(sub)`.
2. Missing header, wrong scheme → 401 with `WWW-Authenticate: Bearer`.
3. Token signed with a different key, edited payload, `alg: none`, HS256 → 401.
4. Expired, wrong audience, wrong issuer, missing `sub` → 401.
5. Non-UW email, missing email claim → 403.
6. Old-style `?hashed_netid=` / body field is ignored: identity always comes from the token.
7. Interactions: unknown `event_id` → 404; valid → logged with the token user's hash.
8. `limit` 0 or 201 → 422.
9. Auth not configured → 503; public endpoints still 200.
