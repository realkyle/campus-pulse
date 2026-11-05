"""Tests for the admin-only demo alert endpoints (contract: api/demo.md)."""
import threading
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import main
from demo_pins import DemoCapacityError, DemoPinStore
from nlp_summarizer import AlertTriage

TOKEN = "test-admin-token"
AUTH = {"X-Admin-Token": TOKEN}

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


@pytest.fixture
def feature_on(monkeypatch):
    monkeypatch.setenv("DEMO_ADMIN_TOKEN", TOKEN)


@pytest.fixture
def feature_off(monkeypatch):
    monkeypatch.delenv("DEMO_ADMIN_TOKEN", raising=False)


def create_pin(**params):
    return client.post("/api/demo", params=params, headers=AUTH)


def alert_ids() -> list[str]:
    return [a["id"] for a in client.get("/api/alerts").json()["alerts"]]


# ── Feature off ───────────────────────────────────────────────────────────────

def test_feature_off_hides_every_endpoint(feature_off):
    assert create_pin().status_code == 404
    assert client.delete("/api/demo/demo-abc", headers=AUTH).status_code == 404
    assert client.post("/api/demo/clear", headers=AUTH).status_code == 404


def test_empty_token_setting_counts_as_off(monkeypatch):
    # .env.example ships DEMO_ADMIN_TOKEN= (empty); that must not enable the feature.
    monkeypatch.setenv("DEMO_ADMIN_TOKEN", "")
    assert client.post("/api/demo", headers={"X-Admin-Token": ""}).status_code == 404


# ── Authentication ────────────────────────────────────────────────────────────

def test_missing_token_is_rejected(feature_on):
    assert client.post("/api/demo").status_code == 401


def test_wrong_token_is_rejected(feature_on):
    response = client.post("/api/demo", headers={"X-Admin-Token": "wrong"})
    assert response.status_code == 401


def test_auth_is_checked_before_input_validation(feature_on):
    response = client.post("/api/demo", params={"severity": "extreme"})
    assert response.status_code == 401


def test_delete_and_clear_require_token(feature_on):
    assert client.delete("/api/demo/demo-abc").status_code == 401
    assert client.post("/api/demo/clear").status_code == 401


# ── Creating pins ─────────────────────────────────────────────────────────────

def test_admin_creates_pin_visible_in_alerts(feature_on):
    response = create_pin(building="uw2", severity="medium")
    assert response.status_code == 200
    body = response.json()
    assert body["building"] == "UW2"
    assert body["severity"] == "medium"
    assert body["expires_in"] == 60
    assert body["pin_id"] in alert_ids()


def test_unknown_building_is_rejected(feature_on):
    assert create_pin(building="NOT-A-BUILDING").status_code == 422


def test_invalid_severity_is_rejected(feature_on):
    assert create_pin(severity="extreme").status_code == 422


def test_high_severity_uses_triage(feature_on, triage_calls):
    pin_id = create_pin(building="DISC", severity="high").json()["pin_id"]
    assert triage_calls == ["DISC"]
    pin = next(a for a in client.get("/api/alerts").json()["alerts"] if a["id"] == pin_id)
    assert pin["headline"] == "Test headline"


def test_low_severity_skips_triage(feature_on, triage_calls):
    create_pin(severity="low")
    assert triage_calls == []


def test_sixth_active_pin_is_rejected(feature_on):
    for _ in range(5):
        assert create_pin().status_code == 200
    assert create_pin().status_code == 429


# ── Expiry and removal ────────────────────────────────────────────────────────

def test_pin_expires_after_sixty_seconds(feature_on, clock):
    pin_id = create_pin().json()["pin_id"]
    clock.advance(59)
    assert pin_id in alert_ids()
    clock.advance(1)
    assert pin_id not in alert_ids()


def test_expired_pins_free_up_capacity(feature_on, clock):
    for _ in range(5):
        create_pin()
    clock.advance(60)
    assert create_pin().status_code == 200


def test_delete_removes_only_that_pin(feature_on):
    first = create_pin(building="UW1").json()["pin_id"]
    second = create_pin(building="UW2").json()["pin_id"]
    response = client.delete(f"/api/demo/{first}", headers=AUTH)
    assert response.status_code == 200
    assert alert_ids() == [second]


def test_delete_unknown_pin_is_404(feature_on):
    assert client.delete("/api/demo/demo-missing", headers=AUTH).status_code == 404


def test_clear_removes_all_pins(feature_on):
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
