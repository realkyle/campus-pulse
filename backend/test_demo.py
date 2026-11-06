"""Tests for the admin-only demo alert endpoints (contract: api/demo.md)."""
import threading
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import main
from auth import get_token_verifier
from demo_pins import DemoCapacityError, DemoPinStore
from fixtures.tokens import bearer, make_token, test_verifier
from nlp_summarizer import AlertTriage

AUTH = bearer(make_token(permissions=["demo:write"]))      # signed-in admin
NOT_ADMIN = bearer(make_token(permissions=["read:other"]))  # signed in, no demo:write

# Not used as a context manager, so the startup polling loops never run.
client = TestClient(main.app)


class FakeClock:
    """A clock the test moves forward by hand."""

    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def triage_calls(monkeypatch) -> list[str]:
    """Replace the OpenAI triage call with a fake that records each call."""
    calls: list[str] = []

    def fake_triage(raw_text, summary):
        calls.append(summary.building_name)
        return AlertTriage(headline="Test headline", safety_brief="Test brief.")

    monkeypatch.setattr(main, "triage", fake_triage)
    return calls


@pytest.fixture(autouse=True)
def isolated_demo_state(monkeypatch, clock, triage_calls):
    monkeypatch.setattr(main, "demo_pins", DemoPinStore(clock=clock))
    main.app.dependency_overrides[get_token_verifier] = test_verifier
    yield
    main.app.dependency_overrides.clear()


def create_pin(**params):
    return client.post("/api/demo", params=params, headers=AUTH)


def alert_ids() -> list[str]:
    return [a["id"] for a in client.get("/api/alerts").json()["alerts"]]


# ── Authentication and permission ─────────────────────────────────────────────

@pytest.mark.parametrize("headers, status", [
    ({}, 401),                                   # not signed in
    (bearer("not-a-jwt"), 401),                  # invalid token
    ({"X-Admin-Token": "anything"}, 401),        # the old shared secret grants nothing
    (NOT_ADMIN, 403),                            # signed in without demo:write
    (bearer(make_token()), 403),                 # signed in, no permissions claim at all
])
def test_every_demo_endpoint_requires_the_permission(headers, status):
    assert client.post("/api/demo", headers=headers).status_code == status
    assert client.delete("/api/demo/demo-abc", headers=headers).status_code == status
    assert client.post("/api/demo/clear", headers=headers).status_code == status


def test_permission_is_checked_before_input_validation():
    response = client.post("/api/demo", params={"severity": "extreme"}, headers=NOT_ADMIN)
    assert response.status_code == 403


def test_me_reports_admin_status():
    assert client.get("/api/me", headers=AUTH).json() == {"email": "student@uw.edu", "is_admin": True}
    assert client.get("/api/me", headers=NOT_ADMIN).json() == {"email": "student@uw.edu", "is_admin": False}
    assert client.get("/api/me").status_code == 401


# ── Creating pins ─────────────────────────────────────────────────────────────

def test_admin_creates_pin_visible_in_alerts():
    response = create_pin(building="uw2", severity="medium")
    assert response.status_code == 200
    body = response.json()
    assert body["building"] == "UW2"
    assert body["severity"] == "medium"
    assert body["expires_in"] == 60
    assert body["pin_id"] in alert_ids()


def test_unknown_building_is_rejected():
    assert create_pin(building="NOT-A-BUILDING").status_code == 422


def test_invalid_severity_is_rejected():
    assert create_pin(severity="extreme").status_code == 422


def test_high_severity_uses_triage(triage_calls):
    pin_id = create_pin(building="DISC", severity="high").json()["pin_id"]
    assert triage_calls == ["DISC"]
    pin = next(a for a in client.get("/api/alerts").json()["alerts"] if a["id"] == pin_id)
    assert pin["headline"] == "Test headline"


def test_low_severity_skips_triage(triage_calls):
    create_pin(severity="low")
    assert triage_calls == []


def test_sixth_active_pin_is_rejected():
    for _ in range(5):
        assert create_pin().status_code == 200
    assert create_pin().status_code == 429


# ── Expiry and removal ────────────────────────────────────────────────────────

def test_pin_expires_after_sixty_seconds(clock):
    pin_id = create_pin().json()["pin_id"]
    clock.advance(59)
    assert pin_id in alert_ids()
    clock.advance(1)
    assert pin_id not in alert_ids()


def test_expired_pins_free_up_capacity(clock):
    for _ in range(5):
        create_pin()
    clock.advance(60)
    assert create_pin().status_code == 200


def test_delete_removes_only_that_pin():
    first = create_pin(building="UW1").json()["pin_id"]
    second = create_pin(building="UW2").json()["pin_id"]
    response = client.delete(f"/api/demo/{first}", headers=AUTH)
    assert response.status_code == 200
    assert alert_ids() == [second]


def test_delete_unknown_pin_is_404():
    assert client.delete("/api/demo/demo-missing", headers=AUTH).status_code == 404


def test_clear_removes_all_pins():
    create_pin()
    create_pin()
    assert client.post("/api/demo/clear", headers=AUTH).status_code == 200
    assert alert_ids() == []


# ── Store concurrency ─────────────────────────────────────────────────────────

def test_cap_holds_under_concurrent_adds(clock):
    store = DemoPinStore(clock=clock, max_active=5)
    added: list[int] = []
    start = threading.Barrier(20)

    def add(n: int) -> None:
        start.wait()  # release all threads at once to maximize overlap
        try:
            store.add(f"pin-{n}", object())
            added.append(n)
        except DemoCapacityError:
            pass

    threads = [threading.Thread(target=add, args=(n,)) for n in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(added) == 5
    assert len(store.active()) == 5
