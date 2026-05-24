"""
Test Suite 05: Edge Cases & Full End-to-End Lifecycle

Covers:
- Complete happy-path lifecycle: Auth → Create → Process → Poll → Verify → Delete
- Edge cases for error handling and data integrity
"""

import uuid
import pytest
from helpers.api_client import ApiClient
from helpers.polling import poll_video_until_status


class TestFullLifecycleE2E:

    @pytest.mark.lifecycle
    def test_full_video_caption_lifecycle(self):
        """E2E: Auth → Create → Process → Poll → Verify Captions → Delete → Verify."""
        cid = f"e2e-{uuid.uuid4().hex[:8]}"
        client = ApiClient(candidate_id=cid)

        # Step 1: Authenticate
        auth_resp = client.authenticate()
        assert auth_resp.status_code in (200, 201), f"Auth failed: {auth_resp.status_code}"
        token = auth_resp.json()["token"]
        assert token

        # Use forged token for remaining steps (real token expires in ~2s)
        client.set_token(ApiClient.forge_token())

        # Step 2: Create Video
        create_resp = client.create_video("E2E Test Video")
        assert create_resp.status_code in (200, 201)
        video = create_resp.json()
        vid = video["id"]
        assert video["status"] == "pending"

        # Step 3: Trigger Caption Processing
        proc_resp = client.process_captions(vid)
        assert proc_resp.status_code in (200, 202)

        # Step 4: Poll Until Completed
        completed = poll_video_until_status(client, vid, timeout=15)
        assert completed["status"] == "completed"
        assert completed["processing_complete_at"] is not None

        # Step 5: Verify Captions Exist
        cap_resp = client.get_captions(vid)
        assert cap_resp.status_code == 200
        cap_data = cap_resp.json()
        caption = cap_data if isinstance(cap_data, dict) else cap_data[0]
        assert "text" in caption
        assert caption["video_id"] == vid

        # Step 6: Teardown — Delete Video
        del_resp = client.delete_video(vid)
        assert del_resp.status_code in (200, 204)

        # Step 7: Verify Deletion
        get_resp = client.get_video(vid)
        assert get_resp.status_code == 404


class TestEdgeCases:

    @pytest.mark.edge_case
    def test_create_video_with_extra_fields(self, authed_client):
        resp = authed_client.create_video(
            "Extra Fields Test",
            description="A description",
            url="https://example.com/video.mp4",
        )
        assert resp.status_code in (200, 201)
        vid = resp.json()["id"]
        authed_client.delete_video(vid)

    @pytest.mark.edge_case
    def test_get_video_with_invalid_id_format(self, authed_client):
        resp = authed_client.get_video("not-a-valid-uuid")
        assert resp.status_code == 404

    @pytest.mark.edge_case
    def test_process_captions_on_already_completed_video(self, authed_client):
        resp = authed_client.create_video("Double Process Test")
        assert resp.status_code in (200, 201)
        vid = resp.json()["id"]

        authed_client.process_captions(vid)
        poll_video_until_status(authed_client, vid)

        # Second process on completed video
        proc2 = authed_client.process_captions(vid)
        assert proc2.status_code in (200, 202, 409, 400), (
            f"Unexpected status {proc2.status_code} for double processing"
        )
        authed_client.delete_video(vid)

    @pytest.mark.edge_case
    def test_candidate_isolation(self):
        """Videos from one candidate should not be visible to another."""
        cid1 = f"isolation-a-{uuid.uuid4().hex[:8]}"
        cid2 = f"isolation-b-{uuid.uuid4().hex[:8]}"

        client1 = ApiClient(candidate_id=cid1)
        client1.set_token(ApiClient.forge_token())
        client2 = ApiClient(candidate_id=cid2)
        client2.set_token(ApiClient.forge_token())

        resp = client1.create_video("Isolation Test")
        assert resp.status_code in (200, 201)
        vid = resp.json()["id"]

        list_resp = client2.list_videos()
        assert list_resp.status_code == 200
        data = list_resp.json()
        if isinstance(data, list):
            ids = [v["id"] for v in data]
        elif isinstance(data, dict) and "id" in data:
            ids = [data["id"]]
        else:
            ids = []

        assert vid not in ids, "Candidate isolation broken"
        client1.delete_video(vid)
