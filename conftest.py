"""
Shared Pytest fixtures for the SignSetu API test suite.

Provides:
- ``api_client``: A fresh ApiClient per test module with a unique candidate ID.
- ``authed_client``: An authenticated client (using a forged long-lived token).
- ``video_factory``: A factory fixture that creates videos and auto-cleans them.
"""

import uuid
import pytest

from config import CANDIDATE_ID
from helpers.api_client import ApiClient


@pytest.fixture(scope="module")
def unique_candidate_id():
    """
    Generate a unique candidate ID for each test module.

    This prevents the 409 re-auth lock from poisoning other modules.
    Each module gets its own isolated namespace.
    """
    return f"{CANDIDATE_ID}-{uuid.uuid4().hex[:6]}"


@pytest.fixture(scope="module")
def api_client(unique_candidate_id):
    """
    Provide an unauthenticated ApiClient bound to a unique candidate ID.

    Scoped per module so all tests in a file share the same candidate
    but different modules are isolated.
    """
    return ApiClient(candidate_id=unique_candidate_id)


@pytest.fixture(scope="module")
def authed_client(unique_candidate_id):
    """
    Provide an ApiClient pre-loaded with a forged long-lived token.

    We intentionally use a forged token (BUG C1) because the real token
    expires in ~2 seconds, making it impractical for multi-step tests.
    The fact that this works IS the vulnerability we are exploiting/testing.
    """
    client = ApiClient(candidate_id=unique_candidate_id)
    client.set_token(ApiClient.forge_token())
    return client


@pytest.fixture()
def video_factory(authed_client):
    """
    Factory fixture: creates videos and tracks them for teardown cleanup.

    Usage in tests:
        video = video_factory("My Title")
        # video is the JSON response dict

    All created videos are deleted after the test completes.
    """
    created_ids = []

    def _create(title: str = "Test Video", **kwargs):
        resp = authed_client.create_video(title=title, **kwargs)
        assert resp.status_code in (200, 201), f"Failed to create video: {resp.status_code} {resp.text}"
        data = resp.json()
        created_ids.append(data["id"])
        return data

    yield _create

    # Teardown: clean up all videos created during the test
    for vid_id in created_ids:
        try:
            authed_client.delete_video(vid_id)
        except Exception:
            pass  # Best-effort cleanup
