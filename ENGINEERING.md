# Engineering notes

How Campus Pulse is built, what changed during the rebuild, and how each change was verified. The [README](README.md) has the short version.

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 16 (App Router), React 19, TypeScript, Leaflet / OpenStreetMap |
| Auth | Auth0 (Next.js SDK v4), Google sign-in; UW accounts only |
| Backend | FastAPI, Python 3.11, httpx, PyJWT |
| AI | OpenAI gpt-4o-mini (JSON mode) for alert structuring |
| Data | Supabase Postgres (click history); in-memory caches for alerts, events, buses |
| Sources | UW Alert blog RSS, campus calendar (Trumba) RSS, OneBusAway Puget Sound API |
| CI/CD | GitHub Actions (ruff, pytest, ESLint, build), Render deploy hook, Vercel |

## Changes, with evidence

### Security
- **Identity from the token, never the request.** `/api/recommendations` and `/api/interactions` used to accept a `hashed_netid` from the URL or body. Now `backend/auth.py` verifies an Auth0 RS256 access token (signature against the tenant's JWKS, `exp`/`iss`/`aud`/`sub`, UW email claim): **401** if invalid, **403** if non-UW, **503** if not configured. Tests sign real JWTs with a throwaway RSA key: forged signature, edited payload, `alg: none`, HS256, expired, wrong audience/issuer, missing email. Production probes: no token, the old `?hashed_netid=` request, and a forged token all return 401.
- **UW-only, enforced twice.** An Auth0 post-login Action (code in `auth0/actions/`) refuses non-UW accounts, and the backend checks the email claim again.
- **Admin by permission, not password.** Demo alerts (fake pins for presentations) went from an open endpoint, to a shared secret, to the `demo:write` permission from an Auth0 role. Shared state uses a lock, so a cap of 5 holds under 20 concurrent requests.
- **Dependencies:** pip-audit 19 → 0 known vulnerabilities, npm audit 7 → 0 (FastAPI/Starlette upgrade, Next.js 14 → 16).
- **Tests can't reach the real database:** a pytest fixture fails any test that creates a database client. It caught two tests that had been running real database code (they only passed because no keys were set).

### AI evaluation (`backend/evals/`)
- 34 labeled alerts (owner-reviewed): severity, scope (this campus / all UW / another campus), building.
- Critical errors, weighted by harm: an emergency answered below "high", a campus alert hidden, an all-clear answered "high", another campus pinned here.

| Run | Severity | Building | Scope | Critical errors |
|---|---|---|---|---|
| v1 (original prompt) | 88.2% | 94.7% | 97.1% | 1 → 0 with the guard |
| v2 (building names, ordered severity rules) | 100% | 100% | 94.1% | 2 → 0 with the guard |
| v3 (shipped) | 97.1% | 100% | 94.1% | 0 |

- v2 fixed one wrong pin and created two. The v3 run changed only the suspected cause and didn't fix it, so the hypothesis was rejected. Scope safety moved into code (`building_coords.effective_scope`): no pin without evidence of this campus in the text. Results are versioned in `backend/evals/results/`; `--rescore` re-scores saved runs offline.

### Data pipelines
- **Alerts:** the feed URL was WordPress's comments feed (always empty) and the API reported it healthy. Now: the official UW Alert blog, a 48-hour window (it's a blog with months of posts), and "not a feed" reported as unavailable. Text is sent to the LLM once per alert (cached by content hash), not every 5 minutes.
- **Events:** a date regex expected "November" while the feed writes "Nov.", so 408 of 411 events were dropped. Now the dates come from the feed's structured fields, ongoing and multi-day events use their end dates, "today" is computed in Pacific time, and categories use whole-word matching. Real feeds: **3 → 406** events. Fixture tests use the real feed structure with invented text.

### Recommender (`backend/scoring.py`)
- SVD trained on click-only data (every rating 1) ranked about as well as random in a controlled experiment, and in production it never activated.
- Now: student events only (staff sessions filtered by audience phrases), one card per repeating series, and a weighted, explainable score. Clicks store category and series, so they stay useful after an event ends. Per request it reads only the user's clicks; aggregates are rebuilt hourly (paged past Supabase's 1,000-row limit).
- `backend/evaluate_recommender.py`: leave-last-out hit rate@5 vs. a popularity baseline (synthetic two-taste data: 1.00 vs 0.67).

### Performance and concurrency
- **Blocking calls froze the event loop:** a 1-second recommendation call delayed `/api/health` by 0.8 s. Blocking work now runs on the thread pool. Tests share one event loop (as in production) and assert that the slow path really ran.
- **Buses:** one shared 30-second cache with single flight (no cache stampede), absolute arrival times (minutes computed per request), parallel or rate-limited fetching depending on the API key (the shared key returns 429 on concurrent calls). Live: **0.82 s → 0.08 s** per request.

### Frontend
- React 19 hooks built on `useSyncExternalStore` (`useLocalStorageValue`, `useMediaQuery`, `useNow`, `usePolledJson`): no hydration mismatches and pure renders; polling pauses in background tabs.
- Pages split into focused components; ESLint with Next.js's React rules in CI.

### Delivery
- One branch and one pull request per change (20), each with what / why / how it was verified. API contracts in `api/` are written before the code.
- CI: ruff + pytest (202 tests), ESLint + build. On merge, a deploy job triggers Render and **polls `/api/health` until the live version equals the merged commit** (it would have caught Render silently deploying an old repository).

## Status

**Built and deployed:** everything above.

**Not built** (some appeared in the original course proposal):
- University SSO (Shibboleth); sign-in uses Google with UW accounts.
- Email or push notifications.
- Automatic purging of old click data.
- Major lookup from the university's student API; students type their major.
- Frontend tests (behavior was verified by hand for each change).
- A hold-out set for the alert evaluation, and repeat runs to measure LLM noise.
- Zero-downtime deploys (the free hosting plan restarts the backend).
- A personal OneBusAway key (the shared demo key is rate-limited).
