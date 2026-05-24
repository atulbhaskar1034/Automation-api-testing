# 🔍 SignSetu Video Caption Processing API — Automated Test Suite

> **QA Analyst Intern — Final Technical Assessment**  
> **Candidate:** Atul Bhaskar  
> **Framework:** Python 3.11 + Pytest + Requests  
> **Target API:** `https://qa-testing-navy.vercel.app`  
> **Results:** ✅ 46 tests passing | 12 bugs found (5 critical + 7 bonus) | 100% repeatable

---

## 📋 Table of Contents

- [Quick Start](#-quick-start)
- [Project Structure](#-project-structure)
- [Testing Strategy](#-testing-strategy)
- [Handling Asynchronous Processing](#-handling-asynchronous-processing)
- [Ensuring Repeatability — The 409 Trap](#-ensuring-repeatability--the-409-trap)
- [Token Strategy](#-token-strategy)
- [Bugs & Vulnerabilities Discovered](#-bugs--vulnerabilities-discovered)
- [Test Results](#-test-results)
- [Test File Breakdown](#-test-file-breakdown)
- [Design Decisions & Trade-offs](#-design-decisions--trade-offs)
- [Running Specific Test Subsets](#-running-specific-test-subsets)

---

## 🚀 Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/atulbhaskar1034/Automation-api-testing.git
cd Automation-api-testing

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the full test suite
python -m pytest tests/ -v

# 4. Run it again — it passes every time (fully repeatable)
python -m pytest tests/ -v
```

---

## 📁 Project Structure

```
Automation-api-testing/
│
├── config.py                 # Central configuration: base URL, unique candidate ID,
│                             # polling settings, and endpoint URL construction
│
├── conftest.py               # Shared Pytest fixtures available to all test files:
│                             # • unique_candidate_id — fresh ID per test module
│                             # • api_client — unauthenticated client
│                             # • authed_client — client with forged long-lived token
│                             # • video_factory — create videos with auto-cleanup
│
├── helpers/
│   ├── __init__.py
│   ├── api_client.py         # ApiClient class — wraps all 8 API endpoints:
│   │                         # authenticate, create/list/get/delete videos,
│   │                         # process captions, get captions, plus forge_token()
│   └── polling.py            # poll_video_until_status() — handles async processing
│                             # by polling GET /videos/{id} until status == "completed"
│
├── tests/
│   ├── __init__.py
│   ├── test_01_auth.py               # 11 tests — Authentication & token security
│   ├── test_02_video_crud.py          # 14 tests — Video Create/Read/Update/Delete
│   ├── test_03_caption_processing.py  # 11 tests — Async caption pipeline & data integrity
│   ├── test_04_auth_bypass.py         #  6 tests — Security: forged tokens & auth bypass
│   └── test_05_edge_cases.py          #  4 tests — E2E lifecycle & edge cases
│
├── requirements.txt          # Pinned dependencies: pytest, requests, python-dotenv
├── pytest.ini                # Pytest config: test paths, custom markers, verbose output
├── .gitignore                # Git ignore rules for __pycache__, .pytest_cache, etc.
└── README.md                 # This file
```

---

## 🧪 Testing Strategy

### Philosophy: "Explore, Break, Automate"

My approach was **not** to simply verify the happy path. The assignment specifically asks us to find hidden bugs, so I:

1. **Manually probed every endpoint** before writing any code — testing with valid data, invalid data, missing headers, empty bodies, fake tokens, and SQL injection strings
2. **Decoded the auth token** (base64) to understand its structure and discover it was forgeable
3. **Tested the temporal behavior** — token expiry, re-authentication locks, async processing timing
4. **Converted every discovery into an automated test** with clear assertions and comments explaining expected vs. actual behavior

### Test Layering Strategy

The 5 test files are ordered intentionally — each layer builds on and assumes the previous:

```
Layer 1: Authentication     → Can we get in?
Layer 2: Video CRUD         → Can we use the core features?
Layer 3: Caption Processing → Does the async pipeline work?
Layer 4: Security Bypass    → Can we break the auth system?
Layer 5: Edge Cases & E2E   → Does the full lifecycle hold up?
```

### Tools & Libraries

| Tool | Purpose | Why Chosen |
|------|---------|------------|
| **Python 3.11** | Test language | Industry standard for QA automation |
| **Pytest 8.3** | Test framework | Fixtures, parametrize, markers, rich assertion messages |
| **Requests 2.32** | HTTP client | Clean API, Session support, connection pooling |
| **UUID (stdlib)** | Unique ID generation | Solves the 409 repeatability trap |
| **Base64 (stdlib)** | Token analysis | Decoding and forging tokens |

---

## ⏳ Handling Asynchronous Processing

The caption processing pipeline is **asynchronous**. When you call `POST /api/videos/{id}/process-captions`, the API returns `202 Accepted` immediately, but the captions aren't ready yet. The video transitions through states over time:

```
pending  →  processing  →  completed
   ↑                          ↑
 (created)              (captions ready)
```

### Solution: Polling with Timeout

I built a dedicated polling helper (`helpers/polling.py`) that:

```python
def poll_video_until_status(client, video_id, target_status="completed",
                            timeout=15.0, interval=1.0):
    start = time.time()
    while time.time() - start < timeout:
        resp = client.get_video(video_id)
        if resp.status_code == 200:
            if resp.json().get("status") == target_status:
                return resp.json()
        time.sleep(interval)
    raise TimeoutError(...)
```

**Why polling instead of `time.sleep(10)`?**
- Processing might take 2 seconds or 10 — we don't know in advance
- A fixed sleep is either **wasteful** (too long) or **flaky** (too short)
- Polling **adapts** to actual processing time
- On timeout, it raises a `TimeoutError` with the last observed status — much more debuggable than a mystery assertion failure

---

## 🔒 Ensuring Repeatability — The 409 Trap

> This is the single most important design decision in the entire project.

### The Problem

The API has **Bug C3**: once you authenticate with a `X-Candidate-ID`, that ID is **permanently locked**. Attempting to re-authenticate returns `409 Conflict` — even after the token expires (~2 seconds). This means:

```
Run 1: POST /api/auth with X-Candidate-ID: "atul" → 201 ✅
Run 2: POST /api/auth with X-Candidate-ID: "atul" → 409 ❌ LOCKED FOREVER
```

If you hardcode the candidate ID, your tests pass on Run 1 and **fail on every subsequent run**.

### The Solution

Generate a **unique candidate ID per test run** using Python's `uuid` module:

```python
# config.py
RUN_ID = uuid.uuid4().hex[:8]                    # e.g., "a3f7b2c1"
CANDIDATE_ID = f"atul-bhaskar-{RUN_ID}"           # e.g., "atul-bhaskar-a3f7b2c1"
```

Each run gets a fresh ID → fresh auth → no 409 → **fully repeatable**.

Additionally, each test **module** appends its own UUID suffix via the `unique_candidate_id` fixture, providing double isolation:

```
Run 1, Module 1: "atul-bhaskar-a3f7b2c1-d2de55"
Run 1, Module 2: "atul-bhaskar-a3f7b2c1-7f8a12"
Run 2, Module 1: "atul-bhaskar-e5f6g7h8-b3c4d5"  ← completely fresh
```

---

## 🔑 Token Strategy

### The Discovery

By decoding the auth token with `base64.b64decode()`, I discovered it's just a **plaintext timestamp**:

```
Token:   "MTc3OTYwMjAzNjA5MA=="
Decoded: "1779602036090"  ← Unix timestamp in milliseconds
```

This is the `expiresAt` value. The API only checks: *"Is this base64 string a timestamp in the future?"* — no signing, no session ID, no secret.

### The Strategy

For tests that need authentication, I use **forged tokens** with far-future timestamps:

```python
# Creates base64("9999999999999") — expires in year 2286
token = ApiClient.forge_token(expire_timestamp_ms=9999999999999)
```

This serves **dual purpose**:
1. **Proves the vulnerability** — the fact that forged tokens work IS Bug C1
2. **Makes tests practical** — the real token expires in ~2 seconds, which is too short for multi-step tests

For auth-specific tests (testing token expiry, re-auth locks), I use real tokens and test their actual behavior.

---

## 🐛 Bugs & Vulnerabilities Discovered

### 🔴 5 Critical Bugs

| ID | Bug Name | Severity | Description | Test Evidence |
|----|----------|----------|-------------|---------------|
| **C1** | **Forged Tokens Accepted** | 🔴 Critical | Token = `base64(timestamp)` with no signing. Any crafted future-timestamp is accepted as valid. No server-side session validation. | [test_04::test_forged_token_can_read_video](tests/test_04_auth_bypass.py), [test_04::test_any_future_timestamp_works_as_token](tests/test_04_auth_bypass.py) |
| **C2** | **Inconsistent Auth Enforcement** | 🔴 Critical | `POST /process-captions`, `GET /videos` (list), and `DELETE /videos/{id}` all work without any auth token. Only `GET /videos/{id}` (single) enforces auth. | [test_04::test_process_captions_no_auth](tests/test_04_auth_bypass.py), [test_04::test_list_videos_no_auth](tests/test_04_auth_bypass.py), [test_04::test_delete_video_no_auth](tests/test_04_auth_bypass.py) |
| **C3** | **409 Re-Auth Lock** | 🔴 Critical | After first auth, the candidate ID is permanently locked. Re-authentication returns `409 Conflict` even after the token expires (~2s TTL). Breaks any reusable testing workflow. | [test_01::test_reauth_returns_409](tests/test_01_auth.py), [test_01::test_reauth_still_409_after_token_expires](tests/test_01_auth.py) |
| **C4** | **Title Field Silently Ignored** | 🔴 Critical | `POST /api/videos` with any `title` value always returns `"title": "New Video"`. User input is silently dropped — a data integrity failure. | [test_02::test_create_video_title_is_ignored](tests/test_02_video_crud.py) |
| **C5** | **`limit` Query Parameter Ignored** | 🔴 Critical | `GET /api/videos?limit=1` returns ALL videos regardless. The pagination mechanism is non-functional. | [test_02::test_list_videos_limit_ignored](tests/test_02_video_crud.py) |

### 🟡 7 Bonus Bugs

| ID | Bug Name | Category | Description | Test Evidence |
|----|----------|----------|-------------|---------------|
| **B1** | **Orphaned Captions After DELETE** | Data Integrity | Deleting a video does NOT cascade-delete its captions. Caption data persists and remains accessible — a data leak/privacy concern. | [test_03::test_captions_persist_after_video_delete](tests/test_03_caption_processing.py) |
| **B2** | **Double DELETE Returns Success** | REST Compliance | Deleting an already-deleted video returns `200/204` instead of `404 Not Found`. Violates HTTP idempotency semantics. | [test_02::test_double_delete_returns_success_instead_of_404](tests/test_02_video_crud.py) |
| **B3** | **No Input Validation on Create** | Robustness | Videos can be created with a completely empty body `{}`. No required-field validation, no schema enforcement. | [test_02::test_create_video_no_body_validation](tests/test_02_video_crud.py) |
| **B4** | **Token = base64(timestamp)** | Security | Token is trivially decodable and forgeable. No JWT, no HMAC signing, no session binding. | [test_01::test_token_is_base64_encoded_timestamp](tests/test_01_auth.py), [test_01::test_decoded_token_matches_expiry](tests/test_01_auth.py) |
| **B5** | **`processing_complete_at` is String** | Data Type | This field is returned as a string `"1779602036051"` instead of a number. Inconsistent with `expiresAt` from auth which IS a number. | [test_03::test_processing_complete_at_is_string_not_number](tests/test_03_caption_processing.py) |
| **B6** | **Inconsistent List Response Shape** | API Contract | `GET /api/videos` returns a bare object `{...}` when there's 1 video but an array `[{...}]` when there are multiple. Breaks client-side parsing. | [test_02::test_list_response_shape_inconsistency](tests/test_02_video_crud.py) |
| **B7** | **Auth Accepts Any Credentials** | Security | No credential validation — any username/password combination (including empty strings, SQL injection) returns a valid token. | [test_01::test_auth_accepts_any_credentials](tests/test_01_auth.py) (parametrized × 4 inputs) |

### Impact Visualization

```
                        SECURITY                     DATA INTEGRITY              API CONTRACT
                   ┌─────────────────┐          ┌─────────────────┐       ┌─────────────────┐
   Critical        │ C1: Forged      │          │ C4: Title       │       │ C5: Limit       │
                   │    Tokens       │          │    Ignored      │       │    Ignored      │
                   │ C2: Auth        │          │                 │       │                 │
                   │    Bypass       │          │                 │       │                 │
                   │ C3: 409 Lock    │          │                 │       │                 │
                   └─────────────────┘          └─────────────────┘       └─────────────────┘
   Bonus           │ B4: Token=ts    │          │ B1: Orphaned    │       │ B2: Double DEL  │
                   │ B7: Any Creds   │          │    Captions     │       │ B6: Shape       │
                   │                 │          │ B5: String Type │       │    Inconsistency│
                   │                 │          │ B3: No Valid.   │       │                 │
                   └─────────────────┘          └─────────────────┘       └─────────────────┘
```

---

## ✅ Test Results

```
======================== 46 passed in 73.63s (0:01:13) ========================
```

| Run | Result | Duration |
|-----|--------|----------|
| Run 1 | ✅ 46 passed, 0 failed | 73.63s |
| Run 2 | ✅ 46 passed, 0 failed | 75.36s |

**Fully repeatable** — verified across consecutive runs. Each run generates fresh candidate IDs, preventing the 409 re-auth lock from causing failures.

---

## 📝 Test File Breakdown

### `test_01_auth.py` — Authentication (11 tests)

| Test | Bug | What It Verifies |
|------|-----|-----------------|
| `test_auth_returns_token_and_expiry` | — | Happy path: auth returns `token` and `expiresAt` |
| `test_auth_expiry_is_in_the_future` | — | `expiresAt` timestamp is after current time |
| `test_auth_accepts_any_credentials` ×4 | B7 | Empty, wrong, admin, SQL injection all return 201 |
| `test_token_is_base64_encoded_timestamp` | B4 | Base64-decoded token is a pure numeric string |
| `test_decoded_token_matches_expiry` | B4 | Decoded token value === `expiresAt` field |
| `test_token_ttl_is_under_5_seconds` | — | Token TTL is abnormally short (~2-3s) |
| `test_reauth_returns_409` | C3 | Second auth with same candidate ID → 409 |
| `test_reauth_still_409_after_token_expires` | C3 | 409 persists AFTER token expires — permanent lock |

### `test_02_video_crud.py` — Video CRUD (14 tests)

| Test | Bug | What It Verifies |
|------|-----|-----------------|
| `test_create_video_returns_expected_fields` | — | Response has id, status, title, candidate_id |
| `test_create_video_title_is_ignored` | C4 | Any title → always "New Video" |
| `test_create_video_no_body_validation` | B3 | Empty body `{}` creates a valid video |
| `test_create_video_processing_complete_at_is_null` | — | New video has null processing_complete_at |
| `test_get_video_returns_correct_data` | — | GET returns matching video data |
| `test_get_video_requires_auth` | — | GET single video correctly requires auth (401) |
| `test_get_nonexistent_video_returns_404` | — | Non-existent ID → 404 |
| `test_list_videos_returns_created_videos` | — | Created videos appear in list |
| `test_list_videos_no_auth_required` | C2 | List works without auth token |
| `test_list_videos_limit_ignored` | C5 | `?limit=1` returns all videos |
| `test_list_response_shape_inconsistency` | B6 | 1 video → object; 2+ → array |
| `test_delete_video_removes_it` | — | DELETE → subsequent GET returns 404 |
| `test_double_delete_returns_success_instead_of_404` | B2 | Delete already-deleted → 200/204 (not 404) |
| `test_delete_no_auth_required` | C2 | DELETE works without auth token |

### `test_03_caption_processing.py` — Async Caption Pipeline (11 tests)

| Test | Bug | What It Verifies |
|------|-----|-----------------|
| `test_processing_completes_successfully` | — | Status reaches "completed" after polling |
| `test_processing_sets_complete_at` | — | `processing_complete_at` is non-null after completion |
| `test_processing_complete_at_is_string_not_number` | B5 | Type is string, not number |
| `test_captions_exist_after_processing` | — | Captions have `text` and `video_id` fields |
| `test_caption_video_id_matches` | — | Caption's `video_id` matches the source video |
| `test_initial_status_is_pending` | — | New video starts with `status: "pending"` |
| `test_process_returns_success_message` | — | Trigger returns `{"message": "Processing started"}` |
| `test_captions_persist_after_video_delete` | B1 | Captions still accessible after video deletion |
| `test_captions_without_video_id_returns_400` | — | Missing `videoId` param → 400 |
| `test_process_nonexistent_video_returns_404` | — | Non-existent video → 404 |

### `test_04_auth_bypass.py` — Security Vulnerabilities (6 tests)

| Test | Bug | What It Verifies |
|------|-----|-----------------|
| `test_forged_token_can_read_video` | C1 | Hand-crafted base64 token is accepted |
| `test_any_future_timestamp_works_as_token` | C1 | Any future timestamp works as valid token |
| `test_process_captions_no_auth` | C2 | POST /process-captions works without token |
| `test_list_videos_no_auth` | C2 | GET /api/videos works without token |
| `test_delete_video_no_auth` | C2 | DELETE /api/videos/{id} works without token |
| `test_get_single_video_requires_auth` | — | Contrast: GET single correctly requires auth |

### `test_05_edge_cases.py` — E2E & Edge Cases (4 tests)

| Test | Bug | What It Verifies |
|------|-----|-----------------|
| `test_full_video_caption_lifecycle` | — | Complete 7-step E2E: Auth → Create → Process → Poll → Captions → Delete → Verify |
| `test_create_video_with_extra_fields` | — | Extra body fields don't break the API |
| `test_get_video_with_invalid_id_format` | — | Invalid ID format → 404 |
| `test_process_captions_on_already_completed_video` | — | Double-processing doesn't crash |
| `test_candidate_isolation` | — | Videos from candidate A invisible to candidate B |

---

## 🏗️ Design Decisions & Trade-offs

### 1. ApiClient Wrapper Pattern
All HTTP logic is centralized in `helpers/api_client.py`. Tests never call `requests.get()` directly. This means:
- Changing the auth scheme (Bearer → API-key) requires editing **one method**, not 46 tests
- Adding logging or retries is a single-point change
- Tests stay clean and focused on assertions

### 2. Module-Scoped Fixtures
Candidate IDs and API clients are created once per test **file**, not per test. This reduces API calls while maintaining isolation between test files.

### 3. Factory Pattern with Auto-Cleanup
`video_factory` tracks created video IDs and deletes them all after each test — even if the test fails (thanks to `yield` + teardown). This prevents test pollution.

### 4. 30-Second Request Timeout
Every HTTP call has a 30-second timeout to prevent the test suite from hanging on network issues. Without this, a single dropped connection could freeze the entire CI pipeline.

### 5. Bug Assertions Are Self-Documenting
Each bug-detection test includes comments explaining:
- What the **correct behavior** should be
- What **actually happens** (the bug)
- What would happen **if the bug is fixed** (the test would fail, alerting us to the change)

---

## 🎯 Running Specific Test Subsets

```bash
# Run everything
python -m pytest tests/ -v

# Run only authentication tests
python -m pytest tests/test_01_auth.py -v

# Run only security tests (by marker)
python -m pytest -m security -v

# Run the full E2E lifecycle test
python -m pytest -m lifecycle -v

# Run edge cases only
python -m pytest -m edge_case -v

# Run with detailed failure output
python -m pytest tests/ -v --tb=long

# Run and stop on first failure
python -m pytest tests/ -v -x
```