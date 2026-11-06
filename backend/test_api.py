from fastapi.testclient import TestClient

import main

# Not used as a context manager, so the startup event (the RSS/OpenAI polling loops) never runs.
client = TestClient(main.app)


def test_removed_netid_login_endpoint_returns_404():
    # The old typed-NetID login had no password; it must stay gone.
    response = client.post("/api/login", json={"netid": "someone"})
    assert response.status_code == 404


def test_lifespan_starts_and_stops_background_loops(monkeypatch):
    import asyncio

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
