"""
Central configuration for the SignSetu API test suite.

Uses a unique candidate ID per test run (UUID suffix) to avoid
the 409 re-auth lock trap, ensuring full repeatability.
"""

import uuid

# ─── API Configuration ───────────────────────────────────────────────
BASE_URL = "https://qa-testing-navy.vercel.app"

# Generate a unique candidate ID per run to bypass the 409 re-auth trap.
# The API locks a candidate ID after first auth and never releases it,
# even after the token expires. Using a fresh ID each run ensures
# the suite is fully repeatable.
RUN_ID = uuid.uuid4().hex[:8]
CANDIDATE_ID = f"atul-bhaskar-{RUN_ID}"

# ─── Polling Configuration ───────────────────────────────────────────
POLL_TIMEOUT_SECONDS = 15
POLL_INTERVAL_SECONDS = 1

# ─── Endpoints ────────────────────────────────────────────────────────
AUTH_ENDPOINT = f"{BASE_URL}/api/auth"
VIDEOS_ENDPOINT = f"{BASE_URL}/api/videos"
CAPTIONS_ENDPOINT = f"{BASE_URL}/api/captions"


def video_endpoint(video_id: str) -> str:
    """Return the URL for a specific video."""
    return f"{VIDEOS_ENDPOINT}/{video_id}"


def process_captions_endpoint(video_id: str) -> str:
    """Return the URL to trigger caption processing for a video."""
    return f"{VIDEOS_ENDPOINT}/{video_id}/process-captions"
