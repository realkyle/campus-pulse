"""Verifies Auth0 access tokens and identifies the signed-in UW user (api/recommendations.md)."""
import hashlib
import logging
import os
import ssl
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import certifi
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

# Set by the Auth0 post-login Action (auth0/actions/uw-only-login.js).
EMAIL_CLAIM = "https://campus-pulse/email"
UW_EMAIL_DOMAINS = ("uw.edu", "washington.edu")


class InvalidToken(Exception):
    """The token isn't a valid access token for this API (→ 401)."""


class NotAllowed(Exception):
    """The token is valid, but the user isn't a UW account (→ 403)."""


class VerificationUnavailable(Exception):
    """The tenant's public keys couldn't be downloaded: a server-side problem (→ 503)."""


@dataclass(frozen=True)
class AuthenticatedUser:
    sub: str
    email: str
    # From the token's "permissions" claim (Auth0 RBAC), e.g. {"demo:write"}.
    permissions: frozenset[str] = frozenset()

    @property
    def user_hash(self) -> str:
        """sha256(sub) as hex: the opaque ID stored with interactions.

        Matches what the browser used to compute from user.sub, so clicks
        recorded before backend verification stay linked to the same user.
        """
        return hashlib.sha256(self.sub.encode()).hexdigest()


def is_uw_email(email: Any) -> bool:
    if not isinstance(email, str):
        return False
    normalized = email.strip().lower()
    return any(normalized.endswith(f"@{domain}") for domain in UW_EMAIL_DOMAINS)


class TokenVerifier:
    """Checks an Auth0 access token's signature and claims.

    By default the signing key is looked up in the tenant's JWKS (its published
    public keys), which PyJWKClient downloads once and caches. Tests pass
    `signing_key_for` to use their own key pair instead.
    """

    def __init__(
        self,
        domain: str,
        audience: str,
        signing_key_for: Callable[[str], Any] | None = None,
    ) -> None:
        self._issuer = f"https://{domain}/"
        self._audience = audience
        if signing_key_for is None:
            # certifi's CA bundle (the one httpx uses), so the download works on
            # any machine; python.org Python on macOS fails with the system default.
            jwks = jwt.PyJWKClient(
                f"https://{domain}/.well-known/jwks.json",
                cache_keys=True,
                timeout=5,
                ssl_context=ssl.create_default_context(cafile=certifi.where()),
            )
            signing_key_for = lambda token: jwks.get_signing_key_from_jwt(token).key  # noqa: E731
        self._signing_key_for = signing_key_for

    def verify(self, token: str) -> AuthenticatedUser:
        try:
            claims = jwt.decode(
                token,
                self._signing_key_for(token),
                # Only RS256: rejects "none" and HS256 tokens whatever their header says.
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except jwt.PyJWKClientConnectionError as e:
            raise VerificationUnavailable(str(e)) from e
        except jwt.PyJWTError as e:  # bad signature, claims, or unknown key ID
            raise InvalidToken(str(e)) from e

        email = claims.get(EMAIL_CLAIM)
        if not is_uw_email(email):
            raise NotAllowed("Only UW accounts can use this feature")
        permissions = claims.get("permissions") or []
        return AuthenticatedUser(
            sub=claims["sub"],
            email=email.strip().lower(),
            permissions=frozenset(p for p in permissions if isinstance(p, str)),
        )


@lru_cache(maxsize=1)
def _verifier(domain: str, audience: str) -> TokenVerifier:
    # One verifier per configuration, so the JWKS cache is shared across requests.
    return TokenVerifier(domain, audience)


def get_token_verifier() -> TokenVerifier:
    """FastAPI dependency. 503 if the server isn't configured for sign-in."""
    domain = os.environ.get("AUTH0_DOMAIN")
    audience = os.environ.get("AUTH0_AUDIENCE")
    if not domain or not audience:
        raise HTTPException(status_code=503, detail="Sign-in features are unavailable")
    return _verifier(domain, audience)


_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    verifier: TokenVerifier = Depends(get_token_verifier),
) -> AuthenticatedUser:
    """FastAPI dependency for protected routes: the user, taken only from the token."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Sign in required", headers={"WWW-Authenticate": "Bearer"})
    try:
        return verifier.verify(credentials.credentials)
    except VerificationUnavailable as e:
        logger.error("Can't verify tokens, key download failed: %s", e)
        # "from None": the client gets a clean HTTP error; the cause is in the log above.
        raise HTTPException(status_code=503, detail="Sign-in verification is temporarily unavailable") from None
    except InvalidToken as e:
        # The reason only, never the token itself.
        logger.info("Rejected access token: %s", e)
        raise HTTPException(
            status_code=401, detail="Invalid or expired token", headers={"WWW-Authenticate": "Bearer"}
        ) from None
    except NotAllowed as e:
        logger.info("Refused non-UW access token")
        raise HTTPException(status_code=403, detail=str(e)) from None
