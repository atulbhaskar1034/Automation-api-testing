"""
Test Suite 02: Video CRUD Operations

Covers:
- BUG C4: Title field is silently ignored (always "New Video")
- BUG C5: limit query parameter is ignored
- BUG C2: Inconsistent auth enforcement
- BUG B2: Double DELETE returns success instead of 404
- BUG B3: No input validation — empty body creates a video
- BUG B6: Inconsistent list response shape
"""

import uuid
import pytest
from helpers.api_client import ApiClient


class TestVideoCreate:

    def test_create_video_returns_expected_fields(self, authed_client, video_factory):
        video = video_factory("My Test Video")
        assert "id" in video
        assert "status" in video
        assert "title" in video
        assert "candidate_id" in video
        assert video["status"] == "pending"

    def test_create_video_title_is_ignored(self, authed_client, video_factory):
        """BUG C4: The API ignores the title field. Always returns 'New Video'."""
        custom_title = f"Unique Title {uuid.uuid4().hex[:8]}"
        video = video_factory(custom_title)
        assert video["title"] != custom_title, (
            "Expected BUG: title should be ignored. If this fails, bug may be fixed."
        )
        assert video["title"] == "New Video"

    def test_create_video_no_body_validation(self, authed_client):
        """BUG B3: API creates a video even with an empty body."""
        resp = authed_client.create_video_raw(body={})
        assert resp.status_code in (200, 201), f"Expected success with empty body, got {resp.status_code}"
        video = resp.json()
        assert "id" in video
        authed_client.delete_video(video["id"])

    def test_create_video_processing_complete_at_is_null(self, video_factory):
        video = video_factory()
        assert video.get("processing_complete_at") is None


class TestVideoGet:

    def test_get_video_returns_correct_data(self, authed_client, video_factory):
        video = video_factory()
        resp = authed_client.get_video(video["id"])
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == video["id"]
        assert data["status"] == "pending"

    def test_get_video_requires_auth(self, unique_candidate_id, video_factory):
        """GET /api/videos/{id} correctly requires auth."""
        video = video_factory()
        no_auth = ApiClient(candidate_id=unique_candidate_id)
        resp = no_auth.get_video(video["id"])
        assert resp.status_code == 401

    def test_get_nonexistent_video_returns_404(self, authed_client):
        resp = authed_client.get_video("nonexistent-fake-id-12345")
        assert resp.status_code == 404


class TestVideoList:

    def test_list_videos_returns_created_videos(self, authed_client, video_factory):
        v1 = video_factory("Video A")
        v2 = video_factory("Video B")
        resp = authed_client.list_videos()
        assert resp.status_code == 200
        data = resp.json()
        if isinstance(data, dict) and "id" in data:
            videos = [data]
        elif isinstance(data, list):
            videos = data
        else:
            videos = []
        video_ids = [v["id"] for v in videos]
        assert v1["id"] in video_ids
        assert v2["id"] in video_ids

    def test_list_videos_no_auth_required(self, unique_candidate_id, video_factory):
        """BUG C2: GET /api/videos works WITHOUT an auth token."""
        video_factory()
        no_auth = ApiClient(candidate_id=unique_candidate_id)
        resp = no_auth.list_videos()
        assert resp.status_code == 200, (
            f"Expected BUG: list should work without auth. Got {resp.status_code}"
        )

    def test_list_videos_limit_ignored(self, authed_client, video_factory):
        """BUG C5: The limit query parameter is completely ignored."""
        video_factory("Limit Test A")
        video_factory("Limit Test B")
        resp = authed_client.list_videos(limit=1)
        assert resp.status_code == 200
        data = resp.json()
        if isinstance(data, list):
            count = len(data)
        elif isinstance(data, dict) and "id" in data:
            count = 1
        else:
            count = 0
        assert count > 1, (
            f"Expected BUG: limit=1 should be ignored. Got {count} video(s)."
        )

    def test_list_response_shape_inconsistency(self):
        """BUG B6: Single-item list returns object instead of array."""
        client = ApiClient(candidate_id=f"shape-test-{uuid.uuid4().hex[:8]}")
        client.set_token(ApiClient.forge_token())
        resp1 = client.create_video("Shape Test")
        assert resp1.status_code in (200, 201)
        vid = resp1.json()["id"]
        try:
            resp = client.list_videos()
            data = resp.json()
            is_array = isinstance(data, list)
            is_object = isinstance(data, dict) and "id" in data
            if not is_array and is_object:
                pytest.fail(
                    "BUG B6: List endpoint returned a bare object instead of an array."
                )
        finally:
            client.delete_video(vid)


class TestVideoDelete:

    def test_delete_video_removes_it(self, authed_client):
        resp = authed_client.create_video("Delete Test")
        assert resp.status_code in (200, 201)
        vid = resp.json()["id"]
        del_resp = authed_client.delete_video(vid)
        assert del_resp.status_code in (200, 204)
        get_resp = authed_client.get_video(vid)
        assert get_resp.status_code == 404

    def test_double_delete_returns_success_instead_of_404(self, authed_client):
        """BUG B2: Deleting an already-deleted video returns 200/204 instead of 404."""
        resp = authed_client.create_video("Double Delete Test")
        vid = resp.json()["id"]
        del1 = authed_client.delete_video(vid)
        assert del1.status_code in (200, 204)

        # BUG: should be 404 but returns success
        del2 = authed_client.delete_video(vid)
        assert del2.status_code in (200, 204), (
            f"Expected BUG: double delete should return success. Got {del2.status_code}."
        )

    def test_delete_no_auth_required(self):
        """BUG C2: DELETE works without an auth token."""
        cid = f"del-noauth-{uuid.uuid4().hex[:8]}"
        creator = ApiClient(candidate_id=cid)
        creator.set_token(ApiClient.forge_token())
        resp = creator.create_video("No Auth Delete Test")
        vid = resp.json()["id"]
        creator.clear_token()
        del_resp = creator.delete_video(vid)
        assert del_resp.status_code in (200, 204), (
            f"Expected BUG: delete should work without auth. Got {del_resp.status_code}"
        )
