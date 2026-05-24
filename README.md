# SignSetu Video Caption Processing API — Automated Test Suite

> QA Analyst Intern Technical Assessment  
> **Candidate:** Atul Bhaskar  
> **Framework:** Python 3.11 + Pytest + Requests  
> **Target API:** `https://qa-testing-navy.vercel.app`

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the full test suite
python -m pytest tests/ -v

# Run a specific test category
python -m pytest tests/test_04_auth_bypass.py -v       # Security tests only
python -m pytest -m security -v                         # By marker
python -m pytest -m lifecycle -v                         # E2E lifecycle only
```

---

## Testing Strategy

### Architecture

```
├── config.py                 # Base URL, unique candidate ID generation
├── conftest.py               # Shared Pytest fixtures (auth, video factory)
├── helpers/
│   ├── api_client.py         # API wrapper class (DRY HTTP interactions)
│   └── polling.py            # Async polling helper for caption processing
├── tests/
│   ├── test_01_auth.py               # Authentication (11 tests)
│   ├── test_02_video_crud.py          # Video CRUD operations (14 tests)
│   ├── test_03_caption_processing.py  # Caption pipeline (11 tests)
│   ├── test_04_auth_bypass.py         # Security vulnerabilities (6 tests)
│   └── test_05_edge_cases.py          # Edge cases & full E2E (4 tests)
```

### Handling Asynchronous Processing

The caption processing pipeline is asynchronous — triggering `POST /api/videos/{id}/process-captions` returns immediately with a `202 Accepted`, and the video status transitions through `pending → processing → completed` over time.

**Solution:** I built a dedicated **polling helper** (`helpers/polling.py`) that:
- Repeatedly calls `GET /api/videos/{id}` at configurable intervals (default: 1s)
- Checks if `status == "completed"`
- Times out after a configurable duration (default: 15s) with a clear error message
- Returns the full video payload once complete for further assertions

### Ensuring Repeatability (The 409 Trap)

The API has a critical trap: once you authenticate with a `X-Candidate-ID`, that ID is **permanently locked** — re-authenticating always returns `409 Conflict`, even after the token expires.

**Solution:** Each test run generates a **unique `X-Candidate-ID`** using a UUID suffix:
```python
CANDIDATE_ID = f"atul-bhaskar-{uuid.uuid4().hex[:8]}"
```
This guarantees that Run 1, Run 2, Run N all pass identically.

### Token Strategy

The real auth token expires in ~2-3 seconds — too short for multi-step test flows. Since the token is just `base64(timestamp)` with no server-side validation (Bug C1), tests use **forged long-lived tokens** for authenticated operations, which itself proves the vulnerability.

---

## Bugs & Vulnerabilities Discovered

### 🔴 5 Critical Bugs

| ID | Bug | Test That Catches It |
|----|-----|---------------------|
| **C1** | **Forged Tokens Accepted** — Token is `base64(timestamp)` with no signing. Any crafted future-timestamp token is accepted. | `test_04::test_forged_token_can_read_video`, `test_04::test_any_future_timestamp_works_as_token` |
| **C2** | **Inconsistent Auth Enforcement** — `POST /process-captions`, `GET /videos` (list), and `DELETE /videos/{id}` all work without any auth token. Only `GET /videos/{id}` requires auth. | `test_04::test_process_captions_no_auth`, `test_04::test_list_videos_no_auth`, `test_04::test_delete_video_no_auth` |
| **C3** | **409 Re-Auth Lock** — After first auth, the candidate ID is permanently locked. Re-authentication returns 409 even after the token expires (~2s TTL). Breaks test repeatability. | `test_01::test_reauth_returns_409`, `test_01::test_reauth_still_409_after_token_expires` |
| **C4** | **Title Field Silently Ignored** — `POST /api/videos` with any title always returns `"title": "New Video"`. User input is silently dropped. | `test_02::test_create_video_title_is_ignored` |
| **C5** | **`limit` Query Parameter Ignored** — `GET /api/videos?limit=1` returns all videos regardless. Pagination is non-functional. | `test_02::test_list_videos_limit_ignored` |

### 🟡 Bonus Bugs

| ID | Bug | Test That Catches It |
|----|-----|---------------------|
| **B1** | **Orphaned Captions After DELETE** — Deleting a video does not cascade-delete its captions. Caption data persists (data leak). | `test_03::test_captions_persist_after_video_delete` |
| **B2** | **Double DELETE Returns Success** — Deleting an already-deleted video returns 200/204 instead of 404. | `test_02::test_double_delete_returns_success_instead_of_404` |
| **B3** | **No Input Validation** — Videos can be created with an empty body `{}`. No required field validation. | `test_02::test_create_video_no_body_validation` |
| **B4** | **Token = base64(timestamp)** — Token is trivially decodable and forgeable. No secrets, no JWT, no session ID. | `test_01::test_token_is_base64_encoded_timestamp`, `test_01::test_decoded_token_matches_expiry` |
| **B5** | **`processing_complete_at` is String** — Returned as `"1779602036051"` (string) instead of a number. Inconsistent with `expiresAt` which is a number. | `test_03::test_processing_complete_at_is_string_not_number` |
| **B6** | **Inconsistent List Response Shape** — `GET /api/videos` returns a bare object when there's 1 video, but an array when there are multiple. Breaks client parsers. | `test_02::test_list_response_shape_inconsistency` |
| **B7** | **Auth Accepts Any Credentials** — Any username/password combination returns a valid token. No credential validation. | `test_01::test_auth_accepts_any_credentials` (parametrized × 4) |

---

## Test Results

```
======================== 46 passed in 73.63s (0:01:13) ========================
```

✅ **Run 1:** 46 passed, 0 failed  
✅ **Run 2:** 46 passed, 0 failed  
✅ **Fully repeatable** — verified across consecutive runs with unique candidate IDs.

---

## Design Decisions

1. **ApiClient wrapper** — All HTTP logic is centralized in `helpers/api_client.py`. Tests stay clean and focused on assertions.
2. **Module-scoped fixtures** — Candidate IDs and clients are created per test module to prevent cross-module pollution while minimizing API calls.
3. **Factory pattern for videos** — `video_factory` fixture auto-tracks created videos and cleans them up in teardown.
4. **30s request timeout** — Prevents tests from hanging indefinitely on network issues.
5. **Bug assertions are explicit** — Each bug-detection test includes a clear comment explaining *what the expected behavior should be* vs *what actually happens*.