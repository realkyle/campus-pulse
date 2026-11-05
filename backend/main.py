import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from building_coords import resolve_coordinates, CAMPUS_CENTER
from rss_fetcher import fetch_alerts
from nlp_summarizer import summarize, triage
from database import log_interaction
from recommender import get_recommendations
from events_fetcher import fetch_live_events
from events import update_live_cache
from bus_fetcher import fetch_all_stops

load_dotenv()

app = FastAPI(title="Campus Pulse API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://css382-dyop.vercel.app", "http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# ── In-memory cache ──────────────────────────────────────────────────────────

class AlertPin(BaseModel):
    id: str
    raw_text: str
    building_name: str
    incident_type: str
    severity: str                    # low | medium | high
    recommended_action: str
    coordinates: list[float]         # [lat, lng]
    published: str
    headline: str | None = None      # smart triage — high severity only
    safety_brief: str | None = None  # smart triage — high severity only

class AlertsResponse(BaseModel):
    alerts: list[AlertPin]
    last_updated: str
    ai_available: bool
    feed_available: bool

_cache: AlertsResponse = AlertsResponse(
    alerts=[],
    last_updated=datetime.now(timezone.utc).isoformat(),
    ai_available=True,
    feed_available=True,
)

_demo_pins: list[AlertPin] = []

DEMO_SCENARIOS = {
    "high": (
        "Active Threat",
        "ACTIVE THREAT reported near {building}. Shelter in place immediately. Lock doors and avoid windows.",
        "Shelter in place immediately. Lock all doors, stay away from windows. Do not leave until all-clear is issued.",
    ),
    "medium": (
        "Suspicious Activity",
        "Suspicious activity reported near {building}. Campus safety and police are responding to the scene.",
        "Avoid the area around {building}. Follow instructions from campus safety officers.",
    ),
    "low": (
        "Minor Incident",
        "Minor incident reported near {building}. Campus safety is on scene and the situation is under control.",
        "Avoid the immediate area around {building}. Normal operations may continue elsewhere on campus.",
    ),
}

# ── Background refresh ────────────────────────────────────────────────────────

POLL_INTERVAL_SECONDS = 300  # 5 minutes


async def refresh_alerts() -> None:
    global _cache

    raw_alerts, feed_ok = fetch_alerts()
    ai_ok = True
    pins: list[AlertPin] = []

    for raw in raw_alerts:
        summary, ai_available = summarize(raw["raw_text"])
        if not ai_available:
            ai_ok = False

        if summary:
            coords = resolve_coordinates(summary.building_name)
            headline = None
            safety_brief = None
            if summary.severity == "high":
                result = triage(raw["raw_text"], summary)
                if result:
                    headline = result.headline
                    safety_brief = result.safety_brief
            pins.append(
                AlertPin(
                    id=raw["id"],
                    raw_text=raw["raw_text"],
                    building_name=summary.building_name,
                    incident_type=summary.incident_type,
                    severity=summary.severity,
                    recommended_action=summary.recommended_action,
                    coordinates=list(coords),
                    published=raw["published"],
                    headline=headline,
                    safety_brief=safety_brief,
                )
            )
        else:
            # AI fallback: raw text on campus center
            pins.append(
                AlertPin(
                    id=raw["id"],
                    raw_text=raw["raw_text"],
                    building_name="CAMPUS",
                    incident_type="Alert",
                    severity="medium",
                    recommended_action="See raw alert text for details.",
                    coordinates=list(CAMPUS_CENTER),
                    published=raw["published"],
                )
            )

    _cache = AlertsResponse(
        alerts=pins,
        last_updated=datetime.now(timezone.utc).isoformat(),
        ai_available=ai_ok,
        feed_available=feed_ok,
    )


async def poll_loop() -> None:
    while True:
        try:
            await refresh_alerts()
        except Exception as e:
            logger.error("poll_loop error: %s", e)
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


EVENTS_REFRESH_SECONDS = 3600  # 1 hour


async def events_loop() -> None:
    while True:
        try:
            events, ok = await asyncio.get_event_loop().run_in_executor(
                None, fetch_live_events
            )
            if ok and events:
                update_live_cache(events)
                logger.info("Events cache updated: %d live events", len(events))
        except Exception as e:
            logger.error("events_loop error: %s", e)
        await asyncio.sleep(EVENTS_REFRESH_SECONDS)


@app.on_event("startup")
async def startup_event() -> None:
    asyncio.create_task(poll_loop())
    asyncio.create_task(events_loop())


# ── Routes ────────────────────────────────────────────────────────────────────

_bus_cache: list[dict] = []

@app.get("/api/buses")
async def get_buses() -> dict:
    global _bus_cache
    stops = await asyncio.get_event_loop().run_in_executor(None, fetch_all_stops)
    # Only update cache if we got real data — serve stale on API failure
    if any(s["arrivals"] for s in stops):
        _bus_cache = stops
    return {"stops": _bus_cache if _bus_cache else stops}


@app.get("/api/events")
async def get_events() -> dict:
    from events import get_all_events
    events = get_all_events()
    return {"events": events, "count": len(events), "source": "live" if any(e["id"].startswith("live-") for e in events) else "static"}


@app.get("/api/alerts", response_model=AlertsResponse)
async def get_alerts() -> AlertsResponse:
    if not _demo_pins:
        return _cache
    return AlertsResponse(
        alerts=_cache.alerts + _demo_pins,
        last_updated=_cache.last_updated,
        ai_available=_cache.ai_available,
        feed_available=_cache.feed_available,
    )


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/recommendations")
async def recommendations(
    hashed_netid: str,
    major: Optional[str] = None,
    limit: int = 10,
) -> dict:
    events, mode = get_recommendations(hashed_netid, major=major, limit=limit)
    return {"events": events, "mode": mode}


@app.post("/api/demo")
async def trigger_demo(building: str = "UW1", severity: str = "high") -> dict:
    global _demo_pins

    pin_id = f"demo-{int(datetime.now(timezone.utc).timestamp() * 1000)}"
    incident_type, raw_tpl, action_tpl = DEMO_SCENARIOS.get(severity, DEMO_SCENARIOS["high"])

    raw_text = raw_tpl.format(building=building.upper())
    action = action_tpl.format(building=building.upper())
    headline = None
    safety_brief = None
    if severity == "high":
        from nlp_summarizer import AlertSummary
        mock = AlertSummary(building_name=building.upper(), incident_type=incident_type, severity="high", recommended_action=action)
        result = triage(raw_text, mock)
        if result:
            headline = result.headline
            safety_brief = result.safety_brief
    demo_pin = AlertPin(
        id=pin_id,
        raw_text=raw_text,
        building_name=building.upper(),
        incident_type=incident_type,
        severity=severity,
        recommended_action=action,
        coordinates=list(resolve_coordinates(building.upper())),
        published=datetime.now(timezone.utc).isoformat(),
        headline=headline,
        safety_brief=safety_brief,
    )

    _demo_pins.append(demo_pin)

    async def remove_pin():
        global _demo_pins
        await asyncio.sleep(60)
        _demo_pins = [p for p in _demo_pins if p.id != pin_id]

    asyncio.create_task(remove_pin())
    return {"status": "ok", "pin_id": pin_id, "building": building.upper(), "severity": severity, "expires_in": 60}


@app.post("/api/demo/clear")
async def clear_demo() -> dict:
    global _demo_pins
    _demo_pins = []
    return {"status": "cleared"}


class InteractionRequest(BaseModel):
    hashed_netid: str
    event_id: str


@app.post("/api/interactions")
async def record_interaction(body: InteractionRequest) -> dict:
    ok = log_interaction(body.hashed_netid, body.event_id)
    return {"recorded": ok}
