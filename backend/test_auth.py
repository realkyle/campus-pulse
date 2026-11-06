"""Tests for access-token authentication (contract: api/recommendations.md)."""
import hashlib
import time

import jwt
import pytest
from fastapi.testclient import TestClient

import events
import main
from auth import EMAIL_CLAIM, TokenVerifier, get_token_verifier
from fixtures.tokens import AUDIENCE, DOMAIN, ISSUER, OTHER_KEY, SUB, bearer, make_token, test_verifier

client = TestClient(main.app)

EVENT = {"id": "live-abc", "title": "Workshop", "category": "business", "building": "UW1",
         "date": "Nov 05, 2026", "description": "", "url": None}


@pytest.fixture(autouse=True)
def verify_with_test_key():
    """Verify with the test public key instead of downloading the tenant's JWKS."""
    main.app.dependency_overrides[get_token_verifier] = test_verifier
    events.update_live_cache([EVENT])
    yield
    main.app.dependency_overrides.clear()
    events.update_live_cache([])


@pytest.fixture
def recorded(monkeypatch) -> dict:
    calls: dict = {}

    def fake_recommendations(user_hash, major=None, limit=10):
        calls["recommendations"] = (user_hash, major, limit)
        return [EVENT], "popularity"

    def fake_log(user_hash, event_id, category, series):
        calls["interaction"] = (user_hash, event_id)
        calls["interaction_details"] = (category, series)
        return True

    monkeypatch.setattr(main, "get_recommendations", fake_recommendations)
    monkeypatch.setattr(main, "log_interaction", fake_log)
    return calls


EXPECTED_HASH = hashlib.sha256(SUB.encode()).hexdigest()


# ── Accepted ──────────────────────────────────────────────────────────────────

def test_valid_token_gets_recommendations_for_its_own_user(recorded):
    response = client.get("/api/recommendations", params={"major": "CS", "limit": 5}, headers=bearer(make_token()))
    assert response.status_code == 200
    assert response.json()["mode"] == "popularity"
    assert recorded["recommendations"] == (EXPECTED_HASH, "CS", 5)


def test_washington_edu_is_accepted(recorded):
    token = make_token(**{EMAIL_CLAIM: "staff@washington.edu"})
    assert client.get("/api/recommendations", headers=bearer(token)).status_code == 200


def test_user_id_in_request_is_ignored(recorded):
    # The old API took ?hashed_netid=...; it must not let a caller pick a user.
    client.get("/api/recommendations", params={"hashed_netid": "someone-else"}, headers=bearer(make_token()))
    assert recorded["recommendations"][0] == EXPECTED_HASH
    client.post("/api/interactions", json={"event_id": "live-abc", "hashed_netid": "someone-else"}, headers=bearer(make_token()))
    assert recorded["interaction"] == (EXPECTED_HASH, "live-abc")


# ── 401: who are you? ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("headers", [{}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer"}])
def test_missing_or_malformed_header(headers, recorded):
    response = client.get("/api/recommendations", headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert "recommendations" not in recorded


def test_token_signed_with_another_key(recorded):
    assert client.get("/api/recommendations", headers=bearer(make_token(key=OTHER_KEY))).status_code == 401


def test_edited_payload_breaks_signature(recorded):
    header, payload, signature = make_token().split(".")
    forged_payload = jwt.utils.base64url_encode(b'{"sub":"admin","iss":"%s","aud":"%s","exp":9999999999}' % (ISSUER.encode(), AUDIENCE.encode())).decode()
    forged = ".".join([header, forged_payload, signature])
    assert client.get("/api/recommendations", headers=bearer(forged)).status_code == 401


@pytest.mark.parametrize("token", [
    jwt.encode({"sub": SUB, "iss": ISSUER, "aud": AUDIENCE, "exp": int(time.time()) + 600}, None, algorithm="none"),
    jwt.encode({"sub": SUB, "iss": ISSUER, "aud": AUDIENCE, "exp": int(time.time()) + 600}, "an-attacker-chosen-secret-at-least-32-bytes", algorithm="HS256"),
])
def test_only_rs256_is_accepted(token, recorded):
    assert client.get("/api/recommendations", headers=bearer(token)).status_code == 401


@pytest.mark.parametrize("overrides", [
    {"exp": int(time.time()) - 10},                    # expired
    {"aud": "https://some-other-api"},                 # token for another API
    {"iss": "https://evil.example.com/"},              # another tenant
    {"sub": None},                                     # no subject
])
def test_invalid_claims(overrides, recorded):
    assert client.get("/api/recommendations", headers=bearer(make_token(**overrides))).status_code == 401


# ── 403: known, not allowed ───────────────────────────────────────────────────

@pytest.mark.parametrize("email", ["someone@gmail.com", "x@uw.edu.evil.com", None])
def test_non_uw_or_missing_email(email, recorded):
    response = client.get("/api/recommendations", headers=bearer(make_token(**{EMAIL_CLAIM: email})))
    assert response.status_code == 403
    assert "recommendations" not in recorded


# ── Inputs ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("limit", [0, 201])
def test_limit_bounds(limit, recorded):
    assert client.get("/api/recommendations", params={"limit": limit}, headers=bearer(make_token())).status_code == 422


def test_unauthenticated_request_gets_401_before_validation(recorded):
    assert client.get("/api/recommendations", params={"limit": 0}).status_code == 401


def test_interaction_is_logged_for_token_user(recorded):
    response = client.post("/api/interactions", json={"event_id": "live-abc"}, headers=bearer(make_token()))
    assert response.status_code == 200
    assert response.json() == {"recorded": True}
    assert recorded["interaction"] == (EXPECTED_HASH, "live-abc")
    assert recorded["interaction_details"] == ("business", "workshop")  # stored with the click


def test_interaction_for_unknown_event_is_404(recorded):
    response = client.post("/api/interactions", json={"event_id": "live-nope"}, headers=bearer(make_token()))
    assert response.status_code == 404
    assert "interaction" not in recorded


def test_interaction_requires_token(recorded):
    assert client.post("/api/interactions", json={"event_id": "live-abc"}).status_code == 401


def test_key_download_failure_is_503_not_401(recorded):
    def unreachable(token):
        raise jwt.PyJWKClientConnectionError("network down")

    main.app.dependency_overrides[get_token_verifier] = lambda: TokenVerifier(DOMAIN, AUDIENCE, signing_key_for=unreachable)
    response = client.get("/api/recommendations", headers=bearer(make_token()))
    assert response.status_code == 503
    assert "recommendations" not in recorded


# ── Not configured ────────────────────────────────────────────────────────────

def test_auth_not_configured_is_503_and_public_routes_still_work(monkeypatch):
    main.app.dependency_overrides.clear()  # use the real get_token_verifier
    monkeypatch.delenv("AUTH0_DOMAIN", raising=False)
    monkeypatch.delenv("AUTH0_AUDIENCE", raising=False)
    assert client.get("/api/recommendations", headers=bearer(make_token())).status_code == 503
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/events").status_code == 200
