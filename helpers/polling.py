"""
Polling utility for async caption processing.

The API processes captions asynchronously — status transitions from
``pending`` → ``processing`` → ``completed``. This module provides
a helper to poll until completion or timeout.
"""

import time

from helpers.api_client import ApiClient


def poll_video_until_status(
    client: ApiClient,
    video_id: str,
    target_status: str = "completed",
    timeout: float = 15.0,
    interval: float = 1.0,
) -> dict:
    """
    Poll ``GET /api/videos/{id}`` until the video reaches *target_status*.

    Parameters
    ----------
    client : ApiClient
        An authenticated (or forged-token) API client.
    video_id : str
        The video to poll.
    target_status : str
        The status to wait for (default ``"completed"``).
    timeout : float
        Maximum seconds to wait before raising ``TimeoutError``.
    interval : float
        Seconds between poll attempts.

    Returns
    -------
    dict
        The video payload once it reaches the target status.

    Raises
    ------
    TimeoutError
        If the video does not reach the target status in time.
    """
    start = time.time()
    last_status = None

    while time.time() - start < timeout:
        resp = client.get_video(video_id)
        if resp.status_code == 200:
            data = resp.json()
            last_status = data.get("status")
            if last_status == target_status:
                return data
        time.sleep(interval)

    raise TimeoutError(
        f"Video {video_id} did not reach status '{target_status}' "
        f"within {timeout}s. Last observed status: '{last_status}'"
    )
