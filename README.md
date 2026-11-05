# UW Bothell Campus Pulse

[![Live Demo](https://img.shields.io/badge/Live%20Demo-css382--dyop.vercel.app-blue)](https://css382-dyop.vercel.app)

Real-time interactive map of UW Bothell displaying live campus events and emergency alerts with personalized recommendations.
Built with Next.js, FastAPI, OpenStreetMap (Leaflet), and GPT-4o-mini.

## Deployment

**Live Site:** https://css382-dyop.vercel.app

> The map and emergency alerts are fully public — no login required.
> The For You personalized events panel requires a UW email (@uw.edu or @washington.edu) via Google login.

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 14 + TypeScript + react-leaflet |
| Map | OpenStreetMap via Leaflet |
| Backend | FastAPI + Python 3.11 |
| AI | GPT-4o-mini (NLP alert summarizer) |
| Recommender | scikit-surprise SVD (collaborative filtering) |
| Events Feed | Trumba RSS (UW Bothell official calendar, refreshed hourly) |
| Database | PostgreSQL / Supabase |
| Auth | Auth0 (Google login + UW Duo MFA) |
| Deployment | Vercel (frontend) + Render (backend) |

## Milestone Status

| Milestone | Status | Criteria |
|---|---|---|
| Week 7 | ✅ | Map renders UW Bothell; test pin at UW1 |
| Week 8 (MVP) | ✅ | RSS feed + NLP summarizer + fallback banner |
| Week 9 (Testing) | ✅ | Event recommender + Supabase + Auth0 + project website |
| Week 10 (Final) | ✅ | Public deploy on Vercel + Render |

## Quick Start

### Backend

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pip install "numpy<2"

cp ../.env.example .env
# Edit .env and add:
#   OPENAI_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY

uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
# Edit .env.local and add:
#   NEXT_PUBLIC_API_URL=http://localhost:8000
#   AUTH0_SECRET, AUTH0_BASE_URL, AUTH0_ISSUER_BASE_URL, AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET

npm run dev         # opens http://localhost:3000
```

### Test Suites

```bash
cd backend
source venv/bin/activate

# NLP summarizer — must show ≥90% (18/20) valid JSON responses
python test_nlp_summarizer.py

# Unit tests — building coords + recommender threshold logic (no API keys needed)
python -m pytest -v
```

## Architecture

```
Browser
  └─► Next.js on Vercel (css382-dyop.vercel.app)
        ├─ CampusMap (react-leaflet / OpenStreetMap)
        ├─ For You panel (SVD recommender + search + infinite scroll)
        └─► FastAPI on Render (css382-dyop.onrender.com)
              ├─ Alert poller (5 min) → UW Alerts RSS → GPT-4o-mini → map pins
              ├─ Events poller (60 min) → Trumba RSS → category inference → For You feed
              ├─ Building coords lookup → pin placement on map
              ├─ Supabase → interaction logging + recommendations
              └─ Auth0 → Google login + UW Duo MFA → hashed user ID
```
