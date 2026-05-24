"""
Test Suite 04: Authentication Bypass & Security Vulnerabilities

Covers:
- BUG C1: Forged tokens (base64 timestamp) are accepted as valid
- BUG C2: Multiple endpoints work without any auth token
"""

import uuid
import base64
import time
import pytest
from helpers.api_client import ApiClient


class TestForgedTokenAccepted:
    """BUG C1: The API accepts fabricated tokens with no server-side validation."""

    def test_forged_token_can_read_video(self):
        cid = f"forge-read-{uuid.uuid4().hex[:8]}"
        client = ApiClient(candidate_id=cid)
        client.set_token(ApiClient.forge_token(expire_timestamp_ms=9999999999999))

        resp = client.create_video("Forged Token Test")
        assert resp.status_code in (200, 201), f"Forged token should create video, got {resp.status_code}"
        vid = resp.json()["id"]

        get_resp = client.get_video(vid)
        assert get_resp.status_code == 200, (
            f"BUG C1: Forged token should be accepted. Got {get_resp.status_code}"
        )
        client.delete_video(vid)

    def test_any_future_timestamp_works_as_token(self):
        cid = f"forge-any-{uuid.uuid4().hex[:8]}"
        client = ApiClient(candidate_id=cid)

        future_ms = int(time.time() * 1000) + 3600000
        token = base64.b64encode(str(future_ms).encode()).decode()
        client.set_token(token)

        resp = client.create_video("Custom Forged Token")
        assert resp.status_code in (200, 201)
        vid = resp.json()["id"]

        get_resp = client.get_video(vid)
        assert get_resp.status_code == 200, "Custom forged token should work"
        client.delete_video(vid)


@pytest.mark.security
class TestAuthBypassOnEndpoints:
    """BUG C2: Several endpoints work without any authentication token."""

    @pytest.fixture(autouse=True)
    def setup_video(self):
        cid = f"bypass-{uuid.uuid4().hex[:8]}"
        self.creator = ApiClient(candidate_id=cid)
        self.creator.set_token(ApiClient.forge_token())

        resp = self.creator.create_video("Auth Bypass Test")
        assert resp.status_code in (200, 201)
        self.video_id = resp.json()["id"]
        self.no_auth = ApiClient(candidate_id=cid)

        yield

        try:
            self.creator.delete_video(self.video_id)
        except Exception:
            pass

    def test_process_captions_no_auth(self):
        """BUG C2: POST /process-captions works without a token."""
        resp = self.no_auth.process_captions(self.video_id)
        assert resp.status_code in (200, 202), (
            f"Expected BUG: process-captions should work without auth. Got {resp.status_code}"
        )

    def test_list_videos_no_auth(self):
        """BUG C2: GET /api/videos works without a token."""
        resp = self.no_auth.list_videos()
        assert resp.status_code == 200

    def test_delete_video_no_auth(self):
        """BUG C2: DELETE /api/videos/{id} works without a token."""
        resp = self.no_auth.delete_video(self.video_id)
        assert resp.status_code in (200, 204)

    def test_get_single_video_requires_auth(self):
        """Contrast: GET /api/videos/{id} correctly requires auth."""
        resp = self.no_auth.get_video(self.video_id)
        assert resp.status_code == 401
