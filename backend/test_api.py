import asyncio
import threading
import time

from fastapi.testclient import TestClient

import events
import main
from auth import AuthenticatedUser, get_current_user

# Not used as a context manager, so the startup event (the RSS/OpenAI polling loops) never runs.
client = TestClient(main.app)


def test_removed_netid_login_endpoint_returns_404():
    # The old typed-NetID login had no password; it must stay gone.
    response = client.post("/api/login", json={"netid": "someone"})
    assert response.status_code == 404


def test_lifespan_starts_and_stops_background_loops(monkeypatch):
    started: list[str] = []
    cancelled: list[str] = []

    def fake_loop(name):
        async def loop():
            started.append(name)
            try:
                await asyncio.Event().wait()  # run until cancelled, like the real loops
            except asyncio.CancelledError:
                cancelled.append(name)
                raise
        return loop

    monkeypatch.setattr(main, "poll_loop", fake_loop("alerts"))
    monkeypatch.setattr(main, "events_loop", fake_loop("events"))

    with TestClient(main.app) as running:  # context manager runs the lifespan
        assert running.get("/api/health").status_code == 200
        assert sorted(started) == ["alerts", "events"]
    assert sorted(cancelled) == ["alerts", "events"]


def test_health_reports_deployed_commit(monkeypatch):
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abc123")
    assert client.get("/api/health").json() == {"status": "ok", "version": "abc123"}


def test_health_version_unknown_outside_render(monkeypatch):
    monkeypatch.delenv("RENDER_GIT_COMMIT", raising=False)
    assert client.get("/api/health").json() == {"status": "ok", "version": "unknown"}


# ── Event-loop responsiveness ─────────────────────────────────────────────────

def _health_latency_while(monkeypatch, start_slow_request) -> float:
    """Start a slow request in a thread, then time /api/health while it runs.

    The context manager matters: all requests then share ONE event loop, as in
    production. Without it each request gets its own loop and blocking would
    go unnoticed.
    """
    async def idle_loop():
        await asyncio.Event().wait()

    monkeypatch.setattr(main, "poll_loop", idle_loop)
    monkeypatch.setattr(main, "events_loop", idle_loop)

    # Sign the slow request in, so it reaches the slow code instead of failing
    # fast with 401/503 (which would make the latency check prove nothing).
    main.app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(sub="test-user", email="t@uw.edu")
    slow_status: list[int] = []
    try:
        with TestClient(main.app) as shared:
            slow = threading.Thread(target=lambda: slow_status.append(start_slow_request(shared).status_code))
            slow.start()
            time.sleep(0.2)  # let the slow request get going
            began = time.perf_counter()
            assert shared.get("/api/health").status_code == 200
            latency = time.perf_counter() - began
            slow.join()
    finally:
        main.app.dependency_overrides.clear()
    assert slow_status == [200], "the slow request must actually run"
    return latency


def test_slow_recommendations_do_not_block_other_requests(monkeypatch):
    def slow_recommendations(*args, **kwargs):
        time.sleep(1.0)  # stands in for the Supabase query
        return [], "popularity"

    monkeypatch.setattr(main, "get_recommendations", slow_recommendations)
    latency = _health_latency_while(monkeypatch, lambda c: c.get("/api/recommendations"))
    assert latency < 0.3


def test_slow_interaction_logging_does_not_block_other_requests(monkeypatch):
    def slow_log(*args, **kwargs):
        time.sleep(1.0)  # stands in for the Supabase insert
        return True

    monkeypatch.setattr(main, "log_interaction", slow_log)
    event = {"id": "e", "title": "Chess Club", "category": "social"}
    monkeypatch.setattr(events, "_cache", ([event], {"e": event}))
    latency = _health_latency_while(monkeypatch, lambda c: c.post("/api/interactions", json={"event_id": "e"}))
    assert latency < 0.3


def test_alert_refresh_does_not_block_event_loop(monkeypatch):
    class SlowPipeline:
        def refresh(self):
            time.sleep(0.5)  # stands in for the feed download + OpenAI calls
            return main.AlertsResponse(alerts=[], last_updated="now", ai_available=True, feed_available=True)

    monkeypatch.setattr(main, "alert_pipeline", SlowPipeline())

    async def scenario() -> float:
        refresh = asyncio.create_task(main.refresh_alerts())
        began = time.perf_counter()
        await asyncio.sleep(0.01)  # another coroutine wanting a turn
        waited = time.perf_counter() - began
        await refresh
        return waited

    assert asyncio.run(scenario()) < 0.2
