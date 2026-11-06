"""BusBoard: shared TTL cache over OneBusAway (contract: api/buses.md)."""
import asyncio
import itertools
import time

import httpx
import pytest

from bus_fetcher import BusBoard

STOPS = [
    {"id": "s1", "name": "Stop 1", "lat": 0.0, "lon": 0.0},
    {"id": "s2", "name": "Stop 2", "lat": 0.0, "lon": 0.0},
    {"id": "s3", "name": "Stop 3", "lat": 0.0, "lon": 0.0},
]
T0 = 1_800_000_000.0  # seconds


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> float:
        return self.now


def arrival(minutes_from_t0: float, route="535", predicted=True, scheduled_only=False) -> dict:
    at_ms = int((T0 + minutes_from_t0 * 60) * 1000)
    return {
        "routeShortName": route,
        "tripHeadsign": "Somewhere",
        "predicted": predicted and not scheduled_only,
        "predictedArrivalTime": 0 if scheduled_only else at_ms,
        "scheduledArrivalTime": at_ms,
    }


class FakeOBA:
    """Serves arrivals per stop ID and counts calls; can fail or be slow on demand."""

    def __init__(self, arrivals_by_stop: dict, delay: float = 0.0) -> None:
        self.arrivals_by_stop = arrivals_by_stop
        self.delay = delay
        self.failing: set[str] = set()
        self.calls: list[str] = []

    async def handler(self, request: httpx.Request) -> httpx.Response:
        stop_id = request.url.path.rsplit("/", 1)[-1].removesuffix(".json")
        self.calls.append(stop_id)
        if self.delay:
            await asyncio.sleep(self.delay)
        if stop_id in self.failing:
            return httpx.Response(500)
        payload = {"data": {"entry": {"arrivalsAndDepartures": self.arrivals_by_stop.get(stop_id, [])}}}
        return httpx.Response(200, json=payload)


def board(oba: FakeOBA, clock: Clock, **kwargs) -> BusBoard:
    """Parallel and unspaced unless a test says otherwise (as with a personal OBA key)."""
    options = {"max_concurrent": len(STOPS), "min_interval_seconds": 0, **kwargs}
    return BusBoard(stops=STOPS, clock=clock, transport=httpx.MockTransport(oba.handler), **options)


def run(coro):
    return asyncio.run(coro)


def arrivals(result: dict, stop_id: str) -> list[dict]:
    return next(s for s in result["stops"] if s["id"] == stop_id)["arrivals"]


# ── Caching ───────────────────────────────────────────────────────────────────

def test_cache_is_shared_for_30_seconds():
    oba, clock = FakeOBA({"s1": [arrival(5)]}), Clock()
    b = board(oba, clock)

    async def scenario():
        await b.get()
        assert sorted(oba.calls) == ["s1", "s2", "s3"]
        clock.now += 29
        await b.get()
        assert len(oba.calls) == 3          # served from cache
        clock.now += 2
        await b.get()
        assert len(oba.calls) == 6          # expired → refetched

    run(scenario())


def test_concurrent_requests_trigger_one_refresh():
    oba, clock = FakeOBA({}, delay=0.05), Clock()
    b = board(oba, clock)

    async def scenario():
        await asyncio.gather(*(b.get() for _ in range(10)))

    run(scenario())
    assert len(oba.calls) == 3


def test_stops_are_fetched_in_parallel():
    oba, clock = FakeOBA({}, delay=0.2), Clock()
    b = board(oba, clock)
    began = time.perf_counter()
    run(b.get())
    assert time.perf_counter() - began < 0.45  # sequential would take ≥ 0.6 s


def test_failed_refresh_is_not_retried_within_30_seconds():
    oba, clock = FakeOBA({}), Clock()
    oba.failing = {"s1", "s2", "s3"}
    b = board(oba, clock)

    async def scenario():
        await b.get()
        await b.get()

    run(scenario())
    assert len(oba.calls) == 3


class TrackingOBA(FakeOBA):
    """Also records when each request starts and the peak number in flight."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.starts: list[float] = []
        self.in_flight = 0
        self.peak = 0

    async def handler(self, request: httpx.Request) -> httpx.Response:
        self.starts.append(time.perf_counter())
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)
        try:
            return await super().handler(request)
        finally:
            self.in_flight -= 1


def test_shared_key_mode_fetches_one_at_a_time_with_spacing():
    oba = TrackingOBA({}, delay=0.01)
    run(board(oba, Clock(), max_concurrent=1, min_interval_seconds=0.1).get())
    assert oba.peak == 1
    gaps = [b - a for a, b in itertools.pairwise(oba.starts)]
    assert len(gaps) == 2 and min(gaps) >= 0.095


def test_default_mode_follows_the_api_key(monkeypatch):
    monkeypatch.delenv("OBA_API_KEY", raising=False)  # falls back to the shared TEST key
    shared = BusBoard(stops=STOPS)
    assert (shared._max_concurrent, shared._min_interval) == (1, 0.3)
    monkeypatch.setenv("OBA_API_KEY", "personal-key")
    personal = BusBoard(stops=STOPS)
    assert (personal._max_concurrent, personal._min_interval) == (3, 0.0)


# ── Minutes and freshness ─────────────────────────────────────────────────────

def test_minutes_are_computed_now_and_departed_buses_drop_out():
    oba, clock = FakeOBA({"s1": [arrival(2, route="A"), arrival(10, route="B")]}), Clock()
    b = board(oba, clock, ttl_seconds=3600)  # no refetch: prove minutes move on their own

    async def scenario():
        first = await b.get()
        assert [(a["route"], a["minutes"]) for a in arrivals(first, "s1")] == [("A", 2), ("B", 10)]
        clock.now += 3 * 60
        later = await b.get()
        assert [(a["route"], a["minutes"]) for a in arrivals(later, "s1")] == [("B", 7)]

    run(scenario())
    assert len(oba.calls) == 3


def test_data_older_than_10_minutes_is_dropped():
    oba, clock = FakeOBA({"s1": [arrival(60)]}), Clock()
    b = board(oba, clock)

    async def scenario():
        await b.get()
        oba.failing = {"s1", "s2", "s3"}     # OBA goes down
        clock.now += 9 * 60
        assert arrivals(await b.get(), "s1")  # 9 min old: still shown
        clock.now += 2 * 60
        assert arrivals(await b.get(), "s1") == []  # 11 min old: dropped

    run(scenario())


def test_one_failing_stop_keeps_its_last_good_data():
    oba, clock = FakeOBA({"s1": [arrival(20, route="old")], "s2": [arrival(20, route="x")]}), Clock()
    b = board(oba, clock)

    async def scenario():
        await b.get()
        oba.failing = {"s1"}
        oba.arrivals_by_stop["s2"] = [arrival(25, route="new")]
        clock.now += 31
        result = await b.get()
        assert [a["route"] for a in arrivals(result, "s1")] == ["old"]
        assert [a["route"] for a in arrivals(result, "s2")] == ["new"]

    run(scenario())


# ── Parsing and shape ─────────────────────────────────────────────────────────

def test_predicted_preferred_scheduled_fallback_sorted_and_capped():
    entries = [arrival(m, route=f"r{m}") for m in range(20, 10, -1)]  # 10 entries, unsorted
    entries.append(arrival(3, route="sched", scheduled_only=True))
    entries.append({"routeShortName": "none", "tripHeadsign": "", "predicted": False,
                    "predictedArrivalTime": 0, "scheduledArrivalTime": 0})
    oba, clock = FakeOBA({"s1": entries}), Clock()
    result = run(board(oba, clock).get())
    stop = arrivals(result, "s1")
    assert len(stop) == 8
    assert stop[0] == {"route": "sched", "headsign": "Somewhere", "minutes": 3, "predicted": False}
    assert [a["minutes"] for a in stop] == sorted(a["minutes"] for a in stop)
    assert all("time" not in a for a in stop)


def test_updated_at_reports_the_last_successful_fetch():
    oba, clock = FakeOBA({}), Clock()
    oba.failing = {"s1", "s2", "s3"}
    assert run(board(oba, clock).get())["updated_at"] is None
    ok = run(board(FakeOBA({}), Clock()).get())
    assert ok["updated_at"].startswith("2027-01-15T")  # T0 as ISO 8601 UTC


def test_response_lists_every_stop():
    result = run(board(FakeOBA({}), Clock()).get())
    assert [s["id"] for s in result["stops"]] == ["s1", "s2", "s3"]
    assert set(result["stops"][0]) == {"id", "name", "lat", "lon", "arrivals"}


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    """Every test passes a MockTransport; a real request would be a bug."""
    def refuse(*args, **kwargs):
        raise AssertionError("test tried to reach the real OneBusAway API")
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", refuse)


def test_api_route_serves_the_shared_board(monkeypatch):
    from fastapi.testclient import TestClient

    import main

    oba, clock = FakeOBA({"s1": [arrival(5)]}), Clock()
    monkeypatch.setattr(main, "bus_board", board(oba, clock))

    async def idle():
        await asyncio.Event().wait()

    monkeypatch.setattr(main, "poll_loop", idle)
    monkeypatch.setattr(main, "events_loop", idle)
    with TestClient(main.app) as client:  # one event loop for all requests, as in production
        first = client.get("/api/buses").json()
        client.get("/api/buses")
    assert arrivals(first, "s1")[0]["minutes"] == 5
    assert len(oba.calls) == 3  # second request served from the cache
