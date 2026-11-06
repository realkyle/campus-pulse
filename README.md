# Campus Pulse

[![CI](https://github.com/realkyle/campus-pulse/actions/workflows/ci.yml/badge.svg)](https://github.com/realkyle/campus-pulse/actions/workflows/ci.yml)
[![Live demo](https://img.shields.io/badge/live%20demo-css382--dyop.vercel.app-blue)](https://css382-dyop.vercel.app)

A real-time campus map: official emergency alerts turned into map pins by an LLM, a personalized feed of campus events, and live bus arrivals.

<!-- Screenshot: add a capture of the live map here, e.g. ![Campus Pulse map](docs-assets/map.png) -->

## What it does

- **Alerts:** polls the official UW Alert feed, uses GPT-4o-mini to extract building, severity and scope, and pins campus incidents on the map. Public, no login.
- **For You:** ranks upcoming campus events for a signed-in UW student (Google sign-in through UW NetID + Duo) and explains each pick, e.g. *"Because you liked Technology events"*.
- **Buses:** next arrivals at the stops near campus, from OneBusAway.

## Architecture

```mermaid
flowchart LR
  U["Browser"] -->|"pages, /auth/*"| V["Next.js 16 on Vercel<br/>Auth0 session"]
  U -->|"public API + Bearer JWT (For You)"| R["FastAPI on Render"]
  V -.->|"login"| Z["Auth0 + Google<br/>→ UW NetID + Duo"]
  R -.->|"signing keys (JWKS)"| Z
  R --> O["OpenAI gpt-4o-mini"]
  R --> A["UW Alert RSS"]
  R --> T["Campus calendar RSS"]
  R --> B["OneBusAway"]
  R --> S[("Supabase Postgres")]
  G["GitHub Actions"] -->|"lint + tests, deploy hook,<br/>verify live version"| R
```

Background loops refresh alerts (5 min) and events (60 min) into memory, so API requests never wait on a feed or the LLM.

## Highlights

- **The backend verifies every sign-in itself.** It used to accept any user ID sent by the browser. Now FastAPI checks an Auth0 RS256 JWT against the tenant's public keys and enforces UW-only access server-side. Admin features need an RBAC permission in the token. Production probes return 401 for a missing, forged, or old-style request.
- **The LLM is measured, not trusted.** A labeled set of 34 alerts weighs errors by real-world harm (an under-called emergency is critical). Prompt iterations raised severity accuracy from 88% to 97–100% with zero under-calls. When prompt tweaks kept trading one mis-placed pin for another, a controlled run rejected my hypothesis, and a deterministic guard now refuses to pin an alert unless the text itself shows it's on this campus.
- **Silent failures, found and fixed.** The alert feed URL pointed at an always-empty comments feed while reporting "healthy", and a date regex dropped 408 of 411 events. Structured fields and fixture tests from the real feeds took events from **3 to 406**.
- **A recommender that can actually learn.** SVD on click-only data ranked about as well as random (measured), so I replaced it with an explainable hybrid score (category affinity, other dates of an opened series, item-item co-clicks, popularity, soonness) plus an offline leave-last-out evaluation against a popularity baseline.

More detail, with evidence for each change: [ENGINEERING.md](ENGINEERING.md).

## Run it locally

```bash
# Backend (Python 3.11)
cd backend
python3.11 -m venv venv
./venv/bin/pip install -r requirements-dev.txt
cp ../.env.example .env        # OpenAI, Supabase, Auth0 values
./venv/bin/python -m uvicorn main:app --reload --port 8000
./venv/bin/python -m pytest    # no keys needed; tests never touch the real database

# Frontend (Node 20+)
cd frontend
npm install
cp .env.example .env.local     # Auth0 values; NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                    # http://localhost:3000
```

Setup guides: [Auth0](auth0/README.md) · [Database](supabase/README.md) · API contracts in [`api/`](api/).

## Project history

Campus Pulse started as a three-person course project. I later audited it end to end and rebuilt it: security, AI evaluation, data pipelines, the recommender, performance, and CI/CD, in 20 pull requests. Not yet built: notifications, university SSO, frontend tests. See [ENGINEERING.md](ENGINEERING.md#status).
