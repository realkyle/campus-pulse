import asyncio
import logging
import os
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Literal, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from building_coords import BUILDING_COORDS, CAMPUS_CENTER, resolve_coordinates
from rss_fetcher import fetch_alerts
from alert_pipeline import AlertPin, AlertPipeline, AlertsResponse
from demo_pins import DemoCapacityError, DemoPinStore
from nlp_summarizer import AlertSummary, summarize, triage
from database import log_interaction
from recommender import get_recommendations
from events_fetcher import fetch_live_events
from events import update_live_cache
from bus_fetcher import fetch_all_stops

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the background polling loops with the server and stop them on shutdown.

    Holding the task references matters: asyncio keeps only weak references to
    tasks, so a task nobody holds can be garbage-collected mid-run.
    """
    tasks = [asyncio.create_task(poll_loop()), asyncio.create_task(events_loop())]
    yield
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(title="Campus Pulse API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://css382-dyop.vercel.app", "http://localhost:3000"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-Admin-Token"],
)

# ── In-memory cache ──────────────────────────────────────────────────────────

_cache: AlertsResponse = AlertsResponse(
    alerts=[],
    last_updated=datetime.now(timezone.utc).isoformat(),
    ai_available=True,
    feed_available=True,
)

demo_pins: DemoPinStore[AlertPin] = DemoPinStore()

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


alert_pipeline = AlertPipeline(
    fetch=fetch_alerts,
    summarize=summarize,
    triage=triage,
    resolve_coordinates=resolve_coordinates,
    fallback_coordinates=CAMPUS_CENTER,
)


async def refresh_alerts() -> None:
    global _cache
    # The feed download and OpenAI calls block, so run them on a worker thread;
    # called directly here they would freeze every request until they finished.
    _cache = await asyncio.to_thread(alert_pipeline.refresh)


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
            events, ok = await asyncio.to_thread(fetch_live_events)
            if ok and events:
                update_live_cache(events)
                logger.info("Events cache updated: %d live events", len(events))
        except Exception as e:
            logger.error("events_loop error: %s", e)
        await asyncio.sleep(EVENTS_REFRESH_SECONDS)


# ── Routes ────────────────────────────────────────────────────────────────────

_bus_cache: list[dict] = []

@app.get("/api/buses")
async def get_buses() -> dict:
    global _bus_cache
    stops = await asyncio.to_thread(fetch_all_stops)
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
    active_demos = demo_pins.active()
    if not active_demos:
        return _cache
    return AlertsResponse(
        alerts=_cache.alerts + active_demos,
        last_updated=_cache.last_updated,
        ai_available=_cache.ai_available,
        feed_available=_cache.feed_available,
    )


@app.get("/api/health")
async def health() -> dict:
    # CI polls this after a deploy until `version` matches the merged commit (api/health.md).
    return {"status": "ok", "version": os.environ.get("RENDER_GIT_COMMIT", "unknown")}


# Plain `def` routes run on FastAPI's thread pool. They call synchronous
# Supabase (and SVD) code, which inside `async def` would freeze the event loop
# and every other request with it.
@app.get("/api/recommendations")
def recommendations(
    hashed_netid: str,
    major: Optional[str] = None,
    limit: int = 10,
) -> dict:
    events, mode = get_recommendations(hashed_netid, major=major, limit=limit)
    return {"events": events, "mode": mode}


def require_demo_admin(x_admin_token: Optional[str] = Header(default=None)) -> None:
    """Allow the request only if it carries the server's DEMO_ADMIN_TOKEN.

    The feature is off (404) when no token is configured, so a deployment
    without the env var can't be abused. Interim until login tokens are
    verified on the backend; see api/demo.md.
    """
    expected = os.environ.get("DEMO_ADMIN_TOKEN")
    if not expected:
        raise HTTPException(status_code=404, detail="Not Found")
    # compare_digest takes the same time wherever the strings differ, so response
    # timing can't be used to guess the token one character at a time.
    if x_admin_token is None or not secrets.compare_digest(x_admin_token.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Invalid or missing admin token")


# Plain `def` (not async): FastAPI runs it on a thread pool, so the blocking
# OpenAI triage call doesn't freeze the event loop for other requests.
@app.post("/api/demo", dependencies=[Depends(require_demo_admin)])
def trigger_demo(
    building: str = "UW1",
    severity: Literal["low", "medium", "high"] = "high",
) -> dict:
    building = building.strip().upper()
    if building not in BUILDING_COORDS:
        raise HTTPException(status_code=422, detail=f"Unknown building: {building}")
    # Checked before the AI call so a full store doesn't cost an OpenAI request;
    # demo_pins.add() below is still the authoritative, atomic check.
    if demo_pins.is_full():
        raise HTTPException(status_code=429, detail="Too many active demo alerts")

    incident_type, raw_tpl, action_tpl = DEMO_SCENARIOS[severity]
    raw_text = raw_tpl.format(building=building)
    action = action_tpl.format(building=building)
    headline = None
    safety_brief = None
    if severity == "high":
        summary = AlertSummary(building_name=building, incident_type=incident_type, severity="high", recommended_action=action)
        result = triage(raw_text, summary)
        if result:
            headline = result.headline
            safety_brief = result.safety_brief

    pin_id = f"demo-{uuid.uuid4().hex[:12]}"
    pin = AlertPin(
        id=pin_id,
        raw_text=raw_text,
        building_name=building,
        incident_type=incident_type,
        severity=severity,
        recommended_action=action,
        coordinates=list(resolve_coordinates(building)),
        published=datetime.now(timezone.utc).isoformat(),
        headline=headline,
        safety_brief=safety_brief,
    )
    try:
        demo_pins.add(pin_id, pin)
    except DemoCapacityError:
        raise HTTPException(status_code=429, detail="Too many active demo alerts")
    return {"status": "ok", "pin_id": pin_id, "building": building, "severity": severity, "expires_in": demo_pins.ttl_seconds}


@app.delete("/api/demo/{pin_id}", dependencies=[Depends(require_demo_admin)])
def remove_demo(pin_id: str) -> dict:
    if not demo_pins.remove(pin_id):
        raise HTTPException(status_code=404, detail="No active demo pin with that ID")
    return {"status": "removed", "pin_id": pin_id}


@app.post("/api/demo/clear", dependencies=[Depends(require_demo_admin)])
def clear_demo() -> dict:
    demo_pins.clear()
    return {"status": "cleared"}


class InteractionRequest(BaseModel):
    hashed_netid: str
    event_id: str


@app.post("/api/interactions")
def record_interaction(body: InteractionRequest) -> dict:
    ok = log_interaction(body.hashed_netid, body.event_id)
    return {"recorded": ok}
