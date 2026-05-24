"""
API Client wrapper for the SignSetu Video Caption Processing API.

Encapsulates all HTTP interactions with proper header management,
providing a clean interface for test files.
"""

import base64
import requests

from config import (
    AUTH_ENDPOINT,
    VIDEOS_ENDPOINT,
    CAPTIONS_ENDPOINT,
    video_endpoint,
    process_captions_endpoint,
)


class ApiClient:
    """
    Wrapper around the SignSetu sandbox API.

    Each instance is bound to a specific candidate ID and optionally
    an auth token. Methods return the raw ``requests.Response`` object
    so tests can assert on status codes, headers, and body freely.
    """

    def __init__(self, candidate_id: str, token: str | None = None):
        self.candidate_id = candidate_id
        self.token = token
        self.session = requests.Session()
        # The mandatory header for every request
        self.session.headers.update({"X-Candidate-ID": candidate_id})

    # ── Auth ──────────────────────────────────────────────────────────

    def authenticate(self, username: str = "testuser", password: str = "testpass") -> requests.Response:
        """POST /api/auth — obtain a session token."""
        resp = self.session.post(
            AUTH_ENDPOINT,
            json={"username": username, "password": password},
            timeout=30,
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            self.token = data.get("token")
        return resp

    def set_token(self, token: str):
        """Manually set the bearer token (useful for forged-token tests)."""
        self.token = token

    def clear_token(self):
        """Remove the bearer token from future requests."""
        self.token = None

    # ── Videos ────────────────────────────────────────────────────────

    def create_video(self, title: str = "Test Video", **extra_fields) -> requests.Response:
        """POST /api/videos — create a new video record."""
        body = {"title": title, **extra_fields}
        return self._request("POST", VIDEOS_ENDPOINT, json=body)

    def create_video_raw(self, body=None) -> requests.Response:
        """POST /api/videos — send a raw body (or None) for edge-case tests."""
        if body is None:
            return self._request("POST", VIDEOS_ENDPOINT)
        return self._request("POST", VIDEOS_ENDPOINT, json=body)

    def list_videos(self, limit: int | None = None) -> requests.Response:
        """GET /api/videos — list videos, optionally with a limit."""
        params = {}
        if limit is not None:
            params["limit"] = limit
        return self._request("GET", VIDEOS_ENDPOINT, params=params)

    def get_video(self, video_id: str) -> requests.Response:
        """GET /api/videos/{id} — fetch a specific video."""
        return self._request("GET", video_endpoint(video_id))

    def delete_video(self, video_id: str) -> requests.Response:
        """DELETE /api/videos/{id} — delete a video."""
        return self._request("DELETE", video_endpoint(video_id))

    # ── Captions ──────────────────────────────────────────────────────

    def process_captions(self, video_id: str) -> requests.Response:
        """POST /api/videos/{id}/process-captions — trigger caption generation."""
        return self._request("POST", process_captions_endpoint(video_id))

    def get_captions(self, video_id: str) -> requests.Response:
        """GET /api/captions?videoId={id} — fetch generated captions."""
        return self._request("GET", CAPTIONS_ENDPOINT, params={"videoId": video_id})

    def get_captions_no_video_id(self) -> requests.Response:
        """GET /api/captions — without videoId param (edge case)."""
        return self._request("GET", CAPTIONS_ENDPOINT)

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def forge_token(expire_timestamp_ms: int = 9999999999999) -> str:
        """
        Create a forged bearer token.

        The API uses base64(timestamp) as its token format with no
        server-side validation, so we can craft tokens that never expire.
        """
        return base64.b64encode(str(expire_timestamp_ms).encode()).decode()

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Internal: make a request with optional auth header."""
        headers = kwargs.pop("headers", {})
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        kwargs.setdefault("timeout", 30)
        return self.session.request(method, url, headers=headers, **kwargs)
