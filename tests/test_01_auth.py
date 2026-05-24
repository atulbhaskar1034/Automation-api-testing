"""
Test Suite 01: Authentication

Covers:
- Happy-path token generation
- BUG C3: 409 re-auth lock (can't re-authenticate even after token expires)
- BUG B4: Token is base64-encoded timestamp (trivially forgeable)
- BUG B7: Any credentials are accepted
- Token expiry timing (~2-3 seconds)
"""

import base64
import time
import uuid

import pytest

from helpers.api_client import ApiClient


def _fresh_client() -> ApiClient:
    """Create an ApiClient with a completely fresh candidate ID."""
    cid = f"auth-test-{uuid.uuid4().hex[:10]}"
    return ApiClient(candidate_id=cid)


class TestAuthHappyPath:
    """Verify that authentication works and returns expected fields."""

    def test_auth_returns_token_and_expiry(self):
        """POST /api/auth should return a token and expiresAt field."""
        client = _fresh_client()
        resp = client.authenticate()

        assert resp.status_code in (200, 201), f"Auth failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "token" in data, "Response missing 'token' field"
        assert "expiresAt" in data, "Response missing 'expiresAt' field"
        assert isinstance(data["token"], str) and len(data["token"]) > 0

    def test_auth_expiry_is_in_the_future(self):
        """The expiresAt timestamp should be in the future."""
        client = _fresh_client()
        resp = client.authenticate()
        data = resp.json()

        now_ms = int(time.time() * 1000)
        expires_at = int(data["expiresAt"])
        assert expires_at > now_ms, (
            f"Token expiresAt ({expires_at}) is not in the future (now: {now_ms})"
        )


class TestAuthBugAcceptsAnyCredentials:
    """BUG B7: The API accepts any username/password combination."""

    @pytest.mark.parametrize("username,password", [
        ("", ""),
        ("nonexistent_user", "wrong_password"),
        ("admin", "admin"),
        ("'; DROP TABLE users;--", "hack"),
    ])
    def test_auth_accepts_any_credentials(self, username, password):
        """Auth should reject invalid credentials but accepts anything."""
        client = _fresh_client()
        resp = client.authenticate(username=username, password=password)

        # BUG: This SHOULD fail (401) but succeeds (200/201)
        assert resp.status_code in (200, 201), (
            "Expected BUG: API should accept any creds but didn't"
        )


class TestAuthBugTokenIsForgeable:
    """BUG B4 / C1: The token is just base64(timestamp)."""

    def test_token_is_base64_encoded_timestamp(self):
        """The token should decode to a numeric timestamp."""
        client = _fresh_client()
        resp = client.authenticate()
        token = resp.json()["token"]

        decoded = base64.b64decode(token).decode("utf-8")
        assert decoded.isdigit(), (
            f"Token decoded to '{decoded}' which is not a pure timestamp"
        )

    def test_decoded_token_matches_expiry(self):
        """The decoded token value should match the expiresAt field."""
        client = _fresh_client()
        resp = client.authenticate()
        data = resp.json()

        decoded_ts = int(base64.b64decode(data["token"]).decode("utf-8"))
        expires_at = int(data["expiresAt"])

        assert decoded_ts == expires_at, (
            f"Decoded token ({decoded_ts}) != expiresAt ({expires_at})"
        )


class TestAuthBugTokenExpiresQuickly:
    """The token TTL is only ~2-3 seconds — unreasonably short."""

    def test_token_ttl_is_under_5_seconds(self):
        """Token should expire within a few seconds (abnormally short)."""
        client = _fresh_client()
        resp = client.authenticate()
        data = resp.json()

        now_ms = int(time.time() * 1000)
        expires_at = int(data["expiresAt"])
        ttl_seconds = (expires_at - now_ms) / 1000

        assert ttl_seconds < 5, f"Token TTL is {ttl_seconds:.1f}s — expected < 5s"
        assert ttl_seconds > 0, "Token already expired at creation time"


class TestAuthBug409ReAuthLock:
    """BUG C3: Re-authenticating returns 409 even after token expires."""

    def test_reauth_returns_409(self):
        """Second auth call with same candidate ID should return 409."""
        client = _fresh_client()

        resp1 = client.authenticate()
        assert resp1.status_code in (200, 201)

        resp2 = client.authenticate()
        assert resp2.status_code == 409, (
            f"Expected 409 on re-auth, got {resp2.status_code}"
        )

    def test_reauth_still_409_after_token_expires(self):
        """Even after the token expires, re-auth still returns 409."""
        client = _fresh_client()

        resp1 = client.authenticate()
        assert resp1.status_code in (200, 201)
        data = resp1.json()

        # Wait for the token to expire
        now_ms = int(time.time() * 1000)
        expires_at = int(data["expiresAt"])
        wait_time = max(0, (expires_at - now_ms) / 1000) + 1.0
        time.sleep(wait_time)

        # BUG: still 409
        resp2 = client.authenticate()
        assert resp2.status_code == 409, (
            f"Expected 409 even after token expiry, got {resp2.status_code}"
        )
