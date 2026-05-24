"""
Test Suite 03: Caption Processing Pipeline

Covers:
- Status transitions: pending → processing → completed
- BUG B1: Orphaned captions persist after video deletion
- BUG B5: processing_complete_at is a string instead of a number
"""

import pytest
from helpers.api_client import ApiClient
from helpers.polling import poll_video_until_status


class TestCaptionProcessingLifecycle:

    @pytest.fixture()
    def processed_video(self, authed_client):
        resp = authed_client.create_video("Caption Lifecycle")
        assert resp.status_code in (200, 201)
        video = resp.json()
        vid = video["id"]
        proc_resp = authed_client.process_captions(vid)
        assert proc_resp.status_code in (200, 202)
        completed = poll_video_until_status(authed_client, vid)
        yield completed
        authed_client.delete_video(vid)

    def test_processing_completes_successfully(self, processed_video):
        assert processed_video["status"] == "completed"

    def test_processing_sets_complete_at(self, processed_video):
        assert processed_video["processing_complete_at"] is not None

    def test_processing_complete_at_is_string_not_number(self, processed_video):
        """BUG B5: processing_complete_at is string instead of number."""
        value = processed_video["processing_complete_at"]
        assert isinstance(value, str), (
            f"Expected BUG: processing_complete_at should be string, got {type(value).__name__}"
        )
        assert value.isdigit(), f"processing_complete_at '{value}' is not numeric"


class TestCaptionRetrieval:

    @pytest.fixture()
    def video_with_captions(self, authed_client):
        resp = authed_client.create_video("Caption Content Test")
        assert resp.status_code in (200, 201)
        vid = resp.json()["id"]
        proc_resp = authed_client.process_captions(vid)
        assert proc_resp.status_code in (200, 202)
        poll_video_until_status(authed_client, vid)
        yield vid
        authed_client.delete_video(vid)

    def test_captions_exist_after_processing(self, authed_client, video_with_captions):
        vid = video_with_captions
        resp = authed_client.get_captions(vid)
        assert resp.status_code == 200
        data = resp.json()
        caption = data if isinstance(data, dict) else data[0]
        assert "text" in caption, "Caption missing 'text' field"
        assert "video_id" in caption, "Caption missing 'video_id' field"

    def test_caption_video_id_matches(self, authed_client, video_with_captions):
        vid = video_with_captions
        resp = authed_client.get_captions(vid)
        data = resp.json()
        caption = data if isinstance(data, dict) else data[0]
        assert caption["video_id"] == vid


class TestCaptionStatusTransitions:

    def test_initial_status_is_pending(self, authed_client):
        resp = authed_client.create_video("Status Test")
        assert resp.status_code in (200, 201)
        video = resp.json()
        assert video["status"] == "pending"
        authed_client.delete_video(video["id"])

    def test_process_returns_success_message(self, authed_client):
        resp = authed_client.create_video("Process Msg Test")
        assert resp.status_code in (200, 201)
        vid = resp.json()["id"]
        proc_resp = authed_client.process_captions(vid)
        assert proc_resp.status_code in (200, 202)
        assert "message" in proc_resp.json()
        authed_client.delete_video(vid)


class TestOrphanedCaptions:
    """BUG B1: Captions persist after video deletion."""

    def test_captions_persist_after_video_delete(self, authed_client):
        resp = authed_client.create_video("Orphan Test")
        assert resp.status_code in (200, 201)
        vid = resp.json()["id"]
        proc = authed_client.process_captions(vid)
        assert proc.status_code in (200, 202)
        poll_video_until_status(authed_client, vid)

        cap_resp = authed_client.get_captions(vid)
        cap_data = cap_resp.json()
        has_captions = (isinstance(cap_data, dict) and "text" in cap_data) or \
                       (isinstance(cap_data, list) and len(cap_data) > 0)
        assert has_captions, "Captions should exist before delete"

        authed_client.delete_video(vid)

        orphan_resp = authed_client.get_captions(vid)
        orphan_data = orphan_resp.json()
        still_has = (isinstance(orphan_data, dict) and "text" in orphan_data) or \
                    (isinstance(orphan_data, list) and len(orphan_data) > 0)
        assert still_has, (
            "Expected BUG: captions should persist after video delete (orphaned)."
        )


class TestCaptionEdgeCases:

    def test_captions_without_video_id_returns_400(self, authed_client):
        resp = authed_client.get_captions_no_video_id()
        assert resp.status_code == 400

    def test_process_nonexistent_video_returns_404(self, authed_client):
        resp = authed_client.process_captions("nonexistent-id-12345")
        assert resp.status_code == 404
