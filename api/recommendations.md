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

**200**
```json
{
  "events": [ { "…event fields, see api/events.md…": "", "reason": "Because you liked Technology events" } ],
  "mode": "personalized"
}
```

- `mode`: `personalized` when the user has clicked at least one event, else `cold-start`.
- `reason`: a short explanation of the strongest factor behind the event's rank (see Ranking).

### Ranking

Candidates are student events only, one per series (next date); see `backend/candidates.py`. Each candidate gets:

```
score = 3.0 · category affinity   share of the user's clicks in this category; with no clicks, 1 if the category matches the major
      + 2.0 · series affinity     1 if the user clicked any date of this series before
      + 1.5 · co-click similarity strongest cosine similarity to a series the user clicked, from users' click sets
                                  (only once there are ≥ 50 clicks in total)
      + 1.0 · popularity          this series' clicks in the last 7 days, relative to the most-clicked series
      + 1.0 · soonness            1 for the soonest candidate, minus 1/n per position (n = number of candidates)
```

Ties keep the soonest-first order. `reason` names the most specific factor present: a series the user opened ("Another date of an event you opened"), then co-clicks ("Popular with students who like what you like"), then category ("Because you liked <Category> events", or "Matches your major" with no clicks), then popularity ("Popular on campus this week"), else "Coming up soon". Repeat clicks on one event count once.

Click history: the user's own clicks are read per request; popularity and co-click similarity are rebuilt hourly from all clicks (paged, no row cap). Each click stores the event's `category` and `series_key`; older rows are mapped through the current event list when possible.

## `POST /api/interactions`

Body: `{"event_id": "live-1a2b3c4d5e"}`

| Status | When |
|---|---|
| 200 `{"recorded": true \| false}` | Event exists; stored with its `category` and `series_key`; `false` if the database write failed |
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

Ranking (`backend/test_scoring.py`, pure functions on hand-made data): a technology fan gets technology first; a cold-start user gets the major's categories first; a previously clicked series ranks higher; co-click similarity has no effect below 50 total clicks and lifts related series above; popularity breaks ties among equals; each event's reason matches its strongest factor; staff-only events and repeat dates never appear.
