"""Test access tokens signed with a throwaway RSA key (never a real tenant key)."""
import time

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from auth import EMAIL_CLAIM, TokenVerifier

DOMAIN = "campus-test.us.auth0.com"
AUDIENCE = "https://campus-pulse-api"
ISSUER = f"https://{DOMAIN}/"
SUB = "google-oauth2|1234567890"

SIGNING_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def make_token(key=SIGNING_KEY, algorithm="RS256", **overrides) -> str:
    """A token like Auth0 issues; pass claim=None to drop a claim."""
    claims = {
        "sub": SUB,
        "iss": ISSUER,
        "aud": [AUDIENCE, f"{ISSUER}userinfo"],
        "exp": int(time.time()) + 600,
        EMAIL_CLAIM: "student@uw.edu",
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm=algorithm)


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_verifier() -> TokenVerifier:
    """Verifies with the test public key instead of downloading a JWKS."""
    return TokenVerifier(DOMAIN, AUDIENCE, signing_key_for=lambda token: SIGNING_KEY.public_key())


test_verifier.__test__ = False  # not a pytest test, despite the name
