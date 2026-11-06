"""Bus arrivals near campus from OneBusAway, behind a shared cache (contract: api/buses.md)."""
import asyncio
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

import httpx

logger = logging.getLogger(__name__)

OBA_BASE = "https://api.pugetsound.onebusaway.org/api/where"

# Key UW Bothell bus stops — hardcoded since these are fixed infrastructure
UW_BOTHELL_STOPS = [
    {"id": "29_2229",  "name": "UW Bothell & Cascadia College", "lat": 47.761773, "lon": -122.192425},
    {"id": "1_76224",  "name": "Beardslee Blvd & 108th Ave NE", "lat": 47.762245, "lon": -122.195900},
    {"id": "1_76301",  "name": "Beardslee Blvd & 110th Ave NE", "lat": 47.763996, "lon": -122.193596},
]

MAX_ARRIVALS_PER_STOP = 8

# OBA's shared demo key answers 429 to simultaneous or back-to-back requests;
# measured 2026-11-06: requests ≥ 0.25 s apart all succeed.
TEST_KEY_SPACING_SECONDS = 0.3


def _get_api_key() -> str:
    return os.environ.get("OBA_API_KEY", "TEST")


@dataclass(frozen=True)
class _Arrival:
    route: str
    headsign: str
    arrival_ms: int   # absolute time, so "minutes away" can be computed at read time
    predicted: bool


@dataclass(frozen=True)
class _StopData:
    fetched_at: float          # seconds since epoch
    arrivals: tuple[_Arrival, ...]


def _parse_arrivals(payload: dict) -> tuple[_Arrival, ...]:
    result = []
    for a in payload["data"]["entry"]["arrivalsAndDepartures"]:
        # A live (GPS) prediction when OBA has one, otherwise the timetable.
        arrival_ms = a["predictedArrivalTime"] if a.get("predicted") and a.get("predictedArrivalTime") else a.get("scheduledArrivalTime")
        if not arrival_ms:
            continue
        result.append(_Arrival(
            route=a.get("routeShortName", ""),
            headsign=a.get("tripHeadsign", ""),
            arrival_ms=arrival_ms,
            predicted=bool(a.get("predicted")) and bool(a.get("predictedArrivalTime")),
        ))
    return tuple(result)


class BusBoard:
    """Next arrivals for a fixed set of stops, shared by all users.

    - TTL cache: OBA is called at most once per `ttl_seconds` for everyone.
    - Single flight: when the cache expires, concurrent requests wait on one
      refresh (an asyncio.Lock) instead of each calling OBA (a cache stampede).
    - Rate-aware: with the shared "TEST" key, stops are fetched one at a time,
      0.3 s apart (it rejects concurrent calls with 429); with a personal
      OBA_API_KEY they're fetched in parallel (httpx.AsyncClient + gather).
    - Arrival times are stored as absolute times; "minutes" is computed per
      request, departed buses are dropped, and data older than `max_age_seconds`
      is ignored, so a stale cache can't show "3 min" hours later.

    `clock` and `transport` are injectable so tests control time and fake OBA.
    """

    def __init__(
        self,
        stops: list[dict] = UW_BOTHELL_STOPS,
        ttl_seconds: float = 30,
        max_age_seconds: float = 600,
        clock: Callable[[], float] = time.time,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        max_concurrent: Optional[int] = None,
        min_interval_seconds: Optional[float] = None,
    ) -> None:
        self._stops = stops
        self._ttl = ttl_seconds
        self._max_age = max_age_seconds
        self._clock = clock
        self._transport = transport
        self._data: dict[str, _StopData] = {}
        self._last_refresh: Optional[float] = None
        self._lock = asyncio.Lock()
        shared_key = _get_api_key() == "TEST"
        self._max_concurrent = max_concurrent or (1 if shared_key else len(stops))
        self._min_interval = min_interval_seconds if min_interval_seconds is not None else (
            TEST_KEY_SPACING_SECONDS if shared_key else 0.0)
        self._last_request_start: Optional[float] = None

    async def get(self) -> dict:
        """The response body for GET /api/buses."""
        await self._refresh_if_stale()
        now = self._clock()
        now_ms = now * 1000
        stops = []
        for stop in self._stops:
            data = self._data.get(stop["id"])
            upcoming: list[dict] = []
            if data and now - data.fetched_at <= self._max_age:
                for a in sorted(data.arrivals, key=lambda a: a.arrival_ms):
                    if a.arrival_ms < now_ms:
                        continue  # already arrived
                    upcoming.append({
                        "route": a.route,
                        "headsign": a.headsign,
                        "minutes": int((a.arrival_ms - now_ms) // 60000),
                        "predicted": a.predicted,
                    })
            stops.append({**stop, "arrivals": upcoming[:MAX_ARRIVALS_PER_STOP]})

        last_ok = max((d.fetched_at for d in self._data.values()), default=None)
        return {
            "stops": stops,
            "updated_at": datetime.fromtimestamp(last_ok, tz=timezone.utc).isoformat() if last_ok else None,
        }

    def _is_fresh(self) -> bool:
        return self._last_refresh is not None and self._clock() - self._last_refresh < self._ttl

    async def _refresh_if_stale(self) -> None:
        if self._is_fresh():
            return
        async with self._lock:
            if self._is_fresh():  # another request refreshed while we waited
                return
            # Counted even if it fails, so an OBA outage isn't retried on every request.
            self._last_refresh = self._clock()
            slots = asyncio.Semaphore(self._max_concurrent)
            async with httpx.AsyncClient(timeout=8, transport=self._transport) as client:
                results = await asyncio.gather(*(self._fetch_stop(client, slots, s["id"]) for s in self._stops))
            now = self._clock()
            for stop, arrivals in zip(self._stops, results):
                if arrivals is not None:  # a failed stop keeps its last good data
                    self._data[stop["id"]] = _StopData(fetched_at=now, arrivals=arrivals)

    async def _wait_for_spacing(self) -> None:
        # Called with a semaphore slot held; with one slot, starts are serialized.
        if self._min_interval and self._last_request_start is not None:
            wait = self._last_request_start + self._min_interval - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
        self._last_request_start = time.monotonic()

    async def _fetch_stop(
        self, client: httpx.AsyncClient, slots: asyncio.Semaphore, stop_id: str
    ) -> Optional[tuple[_Arrival, ...]]:
        try:
            async with slots:
                await self._wait_for_spacing()
                response = await client.get(
                    f"{OBA_BASE}/arrivals-and-departures-for-stop/{stop_id}.json",
                    params={"key": _get_api_key(), "minutesBefore": 0, "minutesAfter": 60},
                )
            response.raise_for_status()
            return _parse_arrivals(response.json())
        except Exception as e:
            logger.error("Failed to fetch arrivals for stop %s: %s", stop_id, e)
            return None
