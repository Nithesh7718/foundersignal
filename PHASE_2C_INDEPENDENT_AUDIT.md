# FounderSignal — Phase 2C Independent Technical Audit Report

**Date of Audit:** November 13, 2026
**Auditor Roles:** Senior Backend Engineer, Application Security Engineer, QA Architect
**Target Repository:** `/mnt/4B2725090A15B9D5/Projects/foundersignal`
**Git Base Commit:** `6f1f038` (`feat(phase-2b.3): add durable asynchronous transcription workers`)
**Audit Scope:** Phase 2C Full Stack Implementation (Audio Streaming, Transcription Pipeline, Gnani Prisma STT, Commitment Extraction, Founder Approval UX, Multi-Tenant Security, Database Integrity)

---

## A. Executive Verdict

### **CONDITIONAL PASS**

**Executive Summary:**
The core architecture of FounderSignal Phase 2C is fundamentally sound, demonstrating disciplined multi-tenant boundaries, robust asynchronous worker lease fencing using PostgreSQL `FOR UPDATE SKIP LOCKED`, and genuine integration with Gnani Prisma STT (REST and Batch endpoints).

However, Phase 2C **cannot be rated as a full PASS or Production Ready** at this juncture due to critical implementation gaps:
1. **Mock LLM Extraction:** The production LLM structured signal extraction adapter is unwritten (`raise NotImplementedError` in `app/providers/llm/base.py:98-101`). Only the hardcoded `MockLLMProvider` is functional.
2. **Defective HTTP Range Handling:** The audio streaming endpoint advertises `Accept-Ranges: bytes` but ignores `Range` request headers entirely, never returns `206 Partial Content`, and fails to handle range bounds.
3. **Commitment State Machine & Deduplication Deficiencies:** Commitment extraction is not idempotent (repeated extraction creates unlimited duplicate records), lacks role-based authorization guards on approvals/deletions, and permits invalid state transitions (such as directly reviving rejected commitments to confirmed facts).
4. **Misleading Transcript Labeling:** Machine-generated transcripts are labeled "Verified Transcript" in the user interface, violating core product principles.
5. **Uncommitted Working Tree & Linter Failures:** All Phase 2C code remains uncommitted in the working tree, with `ruff format --check .` failing across six backend files.

---

## B. Audit Scorecard

| Area | Status | Evidence | Findings |
|---|---|---|---|
| **Multi-tenant security** | **PARTIAL** | Verified tenant isolation across conversations, audio, and commitments via TestClient adversarial suite. | [FS-SEC-01](#fs-sec-01), [FS-SEC-02](#fs-sec-02) |
| **Authentication and RBAC** | **PARTIAL** | JWT verification and token revocation are robust. However, commitment mutations lack role checks. | [FS-SEC-02](#fs-sec-02) |
| **Audio storage and streaming** | **PARTIAL** | Local storage adapter enforces magic bytes, MIME, size, and traversal checks. However, HTTP Range streaming is not implemented despite header advertising. | [FS-MED-01](#fs-med-01), [FS-MED-02](#fs-med-02), [FS-MED-03](#fs-med-03) |
| **Gnani REST** | **PASS** | Live REST tested with 11s real speech against `https://api.vachana.ai/stt/v3`. Accurate transcription and confidence preserved as `None`. | None |
| **Gnani Batch** | **PARTIAL** | Live Batch submission, polling, and pre-signed transcript download verified on 11s recording. Full verification on recordings > 30s is unverified due to lack of test recording. | [FS-PRV-01](#fs-prv-01) |
| **Worker reliability** | **PASS** | PostgreSQL `FOR UPDATE SKIP LOCKED`, lease expiration recovery, lease fencing tokens, and idempotent transcript persistence independently verified. | None |
| **Transcript integrity** | **PARTIAL** | Raw transcript and metadata are persisted faithfully, but frontend labels machine output as "Verified Transcript" and drops speaker diarization / timestamps. | [FS-UI-01](#fs-ui-01), [FS-UI-02](#fs-ui-02) |
| **Commitment extraction** | **FAIL** | Production LLM adapter raises `NotImplementedError`. System relies on `MockLLMProvider` returning static strings. Re-extraction creates uncontrolled duplicate database rows. | [FS-AI-01](#fs-ai-01), [FS-AI-02](#fs-ai-02), [FS-AI-03](#fs-ai-03) |
| **Founder approval workflow** | **PARTIAL** | Review component cleanly separates Inferred vs Confirmed states. Backend lacks status transition guards and allows rejected commitments to become confirmed. | [FS-BIZ-01](#fs-biz-01) |
| **Frontend integration** | **PASS** | 38/38 Playwright tests pass. Responsive shell, audio controls, polling intervals with timer cleanup, and error boundaries work as designed. | [FS-UI-03](#fs-ui-03) |
| **Database integrity** | **PASS** | `alembic check` clean. Foreign keys, cascade deletions, and composite constraints intact. | [FS-DB-01](#fs-db-01) |
| **Test coverage** | **PARTIAL** | 107 backend unit tests and 38 Playwright E2E tests pass. However, Playwright cross-workspace spec omits audio, jobs, and commitments; deferred test artifact present. | [FS-QA-01](#fs-qa-01), [FS-QA-02](#fs-qa-02) |
| **Operational readiness** | **PARTIAL** | Solid local monolithic architecture, but full-file audio buffering in memory presents scalability risks. Code formatting check fails. | [FS-OPS-01](#fs-ops-01), [FS-OPS-02](#fs-ops-02) |

---

## C. Findings

### FS-AI-01: Production LLM Extraction Adapter is Unimplemented (`NotImplementedError`)
- **Severity:** P0 (Critical Product Functionality Gap)
- **Affected File:** [`backend/app/providers/llm/base.py`](file:///mnt/4B2725090A15B9D5/Projects/foundersignal/backend/app/providers/llm/base.py#L98-L101)
- **Lines:** 98–101
- **Technical Explanation:**
  The function `get_llm_provider()` explicitly raises `NotImplementedError` whenever a non-mock LLM provider (`openai`, `anthropic`, `gemini`) is configured:
  ```python
  if settings.LLM_PROVIDER.lower() in ["openai", "anthropic", "gemini"]:
      if not settings.LLM_API_KEY:
          raise ExternalProviderException(...)
      raise NotImplementedError(
          f"Production adapter for LLM provider '{settings.LLM_PROVIDER}' requires live API credentials."
      )
  ```
  In `backend/.env`, `LLM_PROVIDER=mock`. The only working provider is `MockLLMProvider`, which returns a single hardcoded commitment (`"Prepare onboarding flow before Thursday client review."`) regardless of what speech or transcript is provided. Dynamic commitment extraction from business conversations is not functional.
- **Reproduction Steps:**
  1. Set `LLM_PROVIDER=openai` or `LLM_PROVIDER=gemini` with a dummy key in `backend/.env`.
  2. Invoke `POST /api/v1/workspaces/{ws_id}/conversations/{conv_id}/commitments/extract`.
  3. The server crashes with HTTP 500 / `NotImplementedError`.
- **Expected Behavior:** An operational LLM adapter that parses transcripts into structured `ExtractedSignal` objects using JSON mode or instructor schemas with confidence scoring.
- **Actual Behavior:** Raises `NotImplementedError` in production configuration; falls back to static hardcoded mock output in dev.
- **Recommended Correction:** Implement a concrete `OpenAILLMProvider` or `GeminiLLMProvider` using structured outputs adhering to the `ExtractionResult` Pydantic model.
- **Test Evidence:** Code inspection of `app/providers/llm/base.py` and test `tests/test_providers.py:test_unsupported_llm_provider_raises_exception`.

---

### FS-MED-01: Advertised `Accept-Ranges: bytes` Header Without HTTP Byte-Range Implementation
- **Severity:** P1 (High Protocol Defect / Media Streaming)
- **Affected File:** [`backend/app/api/v1/endpoints/conversations.py`](file:///mnt/4B2725090A15B9D5/Projects/foundersignal/backend/app/api/v1/endpoints/conversations.py#L164-L172)
- **Lines:** 164–172
- **Technical Explanation:**
  Endpoint `GET /workspaces/{ws_id}/conversations/{conv_id}/audio/{audio_asset_id}` returns response header `"Accept-Ranges": "bytes"`, but does not accept or parse the HTTP `Range` request header.
  When a client sends a partial content request (e.g., `Range: bytes=0-100`), the server returns `HTTP 200 OK` with the full file content instead of `HTTP 206 Partial Content`. It omits the mandatory `Content-Range` header. When sent an unsatisfiable range (e.g., `Range: bytes=999999-`), it returns `200 OK` with the full file instead of `HTTP 416 Range Not Satisfiable`.
- **Reproduction Steps:**
  Execute via `curl` or `TestClient`:
  ```bash
  curl -i -H "Authorization: Bearer <token>" -H "Range: bytes=0-10" \
    http://localhost:8000/api/v1/workspaces/<ws_id>/conversations/<conv_id>/audio/<audio_id>
  ```
- **Expected Behavior:**
  - Status: `HTTP/1.1 206 Partial Content`
  - Header: `Content-Range: bytes 0-10/<total_bytes>`
  - Header: `Content-Length: 11`
  - Body: 11 bytes.
- **Actual Behavior:**
  - Status: `HTTP/1.1 200 OK`
  - Header: `Accept-Ranges: bytes`
  - Header: `Content-Range: None`
  - Header: `Content-Length: <total_file_size>`
  - Body: Entire audio file.
- **Recommended Correction:** Parse the `Range` header using standard byte-offset slicing, return `HTTP 206 Partial Content` with `Content-Range`, validate range bounds, return `416` on invalid ranges, or utilize Starlette's `FileResponse` which implements RFC 7233 range requests natively.
- **Test Evidence:** Confirmed via live execution in scratch script `test_adversarial_security.py` and direct `TestClient` invocation.

---

### FS-AI-02: Non-Idempotent Commitment Extraction Causes Unlimited Duplicate Rows
- **Severity:** P1 (High Data Integrity Defect)
- **Affected File:** [`backend/app/services/commitment_service.py`](file:///mnt/4B2725090A15B9D5/Projects/foundersignal/backend/app/services/commitment_service.py#L161-L181)
- **Lines:** 161–181
- **Technical Explanation:**
  `CommitmentService.extract_commitments_from_transcript` iterates over extracted signals and unconditionally executes `db.add(new_commitment)`. There is no deduplication check against existing commitments for the conversation (e.g., matching `source_quote` or `title`).
  If a founder clicks "Extract Commitments" multiple times, identical duplicate commitment rows are inserted repeatedly into PostgreSQL.
- **Reproduction Steps:**
  1. Have a conversation with a completed transcript.
  2. Call `POST /api/v1/workspaces/{ws_id}/conversations/{conv_id}/commitments/extract` three consecutive times.
  3. Query `GET /api/v1/workspaces/{ws_id}/conversations/{conv_id}/commitments`.
- **Expected Behavior:** Subsequent extractions should be idempotent—either skipping existing identical signals or updating existing records.
- **Actual Behavior:** 3 identical commitments are created in the database and displayed as duplicates in the UI.
- **Recommended Correction:** Implement deduplication in `CommitmentService` by checking for existing commitments with identical `(conversation_id, source_quote)` or `(conversation_id, title)` before inserting.
- **Test Evidence:** Verified by code inspection of `commitment_service.py:161-181`.

---

### FS-SEC-01: Cross-Workspace Conversation Enumeration on Transcription Jobs Endpoint
- **Severity:** P2 (Medium Security / IDOR Information Leak)
- **Affected File:** [`backend/app/services/transcription_job_service.py`](file:///mnt/4B2725090A15B9D5/Projects/foundersignal/backend/app/services/transcription_job_service.py#L179-L196)
- **Lines:** 179–196
- **Technical Explanation:**
  In `list_jobs_for_conversation`, the service executes:
  ```python
  select(TranscriptionJob).where(
      TranscriptionJob.workspace_id == workspace_id,
      TranscriptionJob.conversation_id == conversation_id,
  )
  ```
  Unlike `CommitmentService.list_commitments` or `ConversationService.get_conversation`, this method does **not** verify that `conversation_id` actually belongs to `workspace_id`.
  When User B queries `GET /api/v1/workspaces/{wsB_id}/conversations/{convA_id}/transcription-jobs`, the server returns `HTTP 200 []` rather than `HTTP 404 Not Found`. This violates hierarchical resource validation and behaves inconsistently with all other conversation endpoints.
- **Reproduction Steps:**
  Run `TestClient` request:
  ```python
  client.get(f"/api/v1/workspaces/{wsB_id}/conversations/{convA_id}/transcription-jobs", headers=headersB)
  ```
- **Expected Behavior:** `HTTP 404 Not Found` (`Conversation not found in this workspace`).
- **Actual Behavior:** `HTTP 200 OK` with body `[]`.
- **Recommended Correction:** Add `ConversationService.get_conversation(db, workspace_id, conversation_id)` at the start of `TranscriptionJobService.list_jobs_for_conversation`.
- **Test Evidence:** Reproducible test in `scratch/test_adversarial_security.py` (Path 5.2).

---

### FS-SEC-02: Absence of Role-Based Access Control (RBAC) on Commitment Mutations
- **Severity:** P2 (Medium Authorization Defect)
- **Affected File:** [`backend/app/api/v1/endpoints/commitments.py`](file:///mnt/4B2725090A15B9D5/Projects/foundersignal/backend/app/api/v1/endpoints/commitments.py#L50-L116)
- **Lines:** 50, 71, 91, 111
- **Technical Explanation:**
  In `commitments.py`, every route unpacks `workspace, _role = workspace_context`. While `transcription_jobs.py` strictly restricts job cancellation and reconciliation to `"owner"` and `"admin"` roles (`if role not in ("owner", "admin"): raise ForbiddenException`), the commitments endpoints never inspect `_role`.
  Any workspace member with `"member"` or read-only guest status can approve commitments, reject commitments, edit commitment text, or delete commitments.
- **Reproduction Steps:**
  1. Create a workspace with Owner A and add User B as a `"member"`.
  2. User B issues a `PATCH /workspaces/{ws_id}/commitments/{commitment_id}` with `{"status": "confirmed"}`.
  3. The request succeeds with `HTTP 200 OK`.
- **Expected Behavior:** Product Principle 2 specifies human approval by the founder/owner before making business commitments fact. Regular members should not autonomously confirm, reject, or delete commitments without owner/admin authorization.
- **Actual Behavior:** All workspace members possess full mutation privileges over commitments.
- **Recommended Correction:** Enforce `if role not in ("owner", "admin"): raise ForbiddenException("Only workspace owners and admins can approve or modify commitments.")` on state mutation routes.
- **Test Evidence:** Code inspection of `app/api/v1/endpoints/commitments.py`.

---

### FS-BIZ-01: Missing State Machine Validation Permits Rejected Commitments to Silently Become Confirmed
- **Severity:** P2 (Medium Business Logic / Integrity Defect)
- **Affected File:** [`backend/app/services/commitment_service.py`](file:///mnt/4B2725090A15B9D5/Projects/foundersignal/backend/app/services/commitment_service.py#L99-L106)
- **Lines:** 99–106
- **Technical Explanation:**
  `CommitmentService.update_commitment` validates that `update_in.status` is a member of `VALID_COMMITMENT_STATUSES`, but enforces **no transition logic**:
  ```python
  if update_in.status is not None:
      if update_in.status not in VALID_COMMITMENT_STATUSES:
          raise ValidationException(...)
      commitment.status = update_in.status
  ```
  A rejected commitment can transition directly to `confirmed`. A completed commitment can transition back to `inferred`. There is no lifecycle state machine, validation of valid status progressions, or recording of who approved or rejected the change.
- **Reproduction Steps:**
  1. Transition an inferred commitment to `rejected` via `PATCH` with `{"status": "rejected"}`.
  2. Immediately send `PATCH` with `{"status": "confirmed"}`.
  3. Request succeeds with HTTP 200 and the commitment is marked confirmed.
- **Expected Behavior:** Rejected commitments should not be directly confirmed without reopening review. Valid transitions should be formalized:
  - `inferred` -> `confirmed` | `rejected`
  - `confirmed` -> `in_progress` | `completed`
  - `rejected` -> `inferred` (explicit reopening)
- **Actual Behavior:** Any status can transition to any other status at any time.
- **Recommended Correction:** Implement an explicit state transition mapping (similar to `VALID_TRANSITIONS` in `TranscriptionJobService`).
- **Test Evidence:** Confirmed in `backend/tests/test_commitments.py:95-112` where a test confirms a commitment and immediately sets it to rejected in the next line without error.

---

### FS-UI-01: Machine-Generated Transcripts Labeled "Verified Transcript" in UI Header
- **Severity:** P2 (Medium Product Integrity Violation)
- **Affected File:** [`frontend/src/components/transcript-view.tsx`](file:///mnt/4B2725090A15B9D5/Projects/foundersignal/frontend/src/components/transcript-view.tsx#L61-L63)
- **Lines:** 61–63
- **Technical Explanation:**
  Line 62 displays:
  ```tsx
  <CardTitle className="text-base font-semibold leading-tight">
    Verified Transcript
  </CardTitle>
  ```
  The transcript rendered is raw, automated machine output from Gnani Prisma STT. Section 6 of the audit requirements explicitly commands: *"Check that the interface does not imply that a transcript is human-verified when it is only machine-generated."*
  Labeling unverified machine output as "Verified" misleads non-technical business founders and violates FounderSignal Core Principle 4.
- **Reproduction Steps:** Open any conversation detail page with a completed transcript. Inspect the card title.
- **Expected Behavior:** Header should state "Automated Transcript", "Machine Transcript", or "Transcript (Gnani Prisma)".
- **Actual Behavior:** Header displays "Verified Transcript".
- **Recommended Correction:** Rename the card header to "Automated Transcript" or "Transcript".
- **Test Evidence:** Code inspection of `frontend/src/components/transcript-view.tsx:62`.

---

### FS-UI-02: Speaker Diarization and Segment Timestamps Dropped in UI Presentation
- **Severity:** P2 (Medium Feature Completeness / UX Defect)
- **Affected Files:** [`frontend/src/components/transcript-view.tsx`](file:///mnt/4B2725090A15B9D5/Projects/foundersignal/frontend/src/components/transcript-view.tsx#L112-L128), [`frontend/src/lib/api.ts`](file:///mnt/4B2725090A15B9D5/Projects/foundersignal/frontend/src/lib/api.ts#L47-L59)
- **Lines:** `api.ts:47-59`, `transcript-view.tsx:112-128`
- **Technical Explanation:**
  Gnani Prisma Batch STT returns diarization segments with speaker labels (`Speaker 0`, `Speaker 1`) and start/end timestamps. The backend saves this data into `Transcript.metadata_payload["segments"]`.
  However, the frontend TypeScript interface `Transcript` omits `metadata_payload` and `segments`. Consequently, `TranscriptView` only renders `transcript.raw_transcript` as a single block of plain text. Speaker attribution and segment timestamps are discarded in the presentation layer.
- **Reproduction Steps:** Complete a batch transcription job with diarization enabled. View the conversation detail page.
- **Expected Behavior:** Transcript display shows speaker turns, timestamps, and segment boundaries.
- **Actual Behavior:** Monolithic unsegmented text block.
- **Recommended Correction:** Add `segments` to `Transcript` in `frontend/src/lib/api.ts` and render conversational turns in `transcript-view.tsx`.
- **Test Evidence:** Code inspection of `api.ts` and `transcript-view.tsx`.

---

### FS-AI-03: Default Confidence Score Hardcoded to 1.0 (100%) in Schema and Database Model
- **Severity:** P2 (Medium Data Integrity Violation)
- **Affected Files:** [`backend/app/schemas/commitment.py`](file:///mnt/4B2725090A15B9D5/Projects/foundersignal/backend/app/schemas/commitment.py#L20), [`backend/app/models/commitment.py`](file:///mnt/4B2725090A15B9D5/Projects/foundersignal/backend/app/models/commitment.py#L50)
- **Lines:** `schemas/commitment.py:20`, `models/commitment.py:50`
- **Technical Explanation:**
  In `CommitmentCreate`:
  ```python
  confidence_score: float = Field(1.0, ge=0.0, le=1.0)
  ```
  In SQLAlchemy `Commitment` model:
  ```python
  confidence_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
  ```
  Audit rules stipulate: *"If the provider does not supply a confidence score, the application must not manufacture one, default to 100%, or present an unsupported value as provider confidence."*
  Defaulting missing commitment confidence to 1.0 fabricates artificial maximum certainty.
- **Reproduction Steps:** Call `POST /workspaces/{ws_id}/conversations/{conv_id}/commitments` without providing `confidence_score`.
- **Expected Behavior:** Confidence should either be mandatory or nullable/represented as unrated.
- **Actual Behavior:** Stored and displayed as 100% confidence.
- **Recommended Correction:** Make `confidence_score` a nullable float (`float | None = None`) or require explicit rating on manual creation.
- **Test Evidence:** Inspection of `schemas/commitment.py` and `models/commitment.py`.

---

### FS-MED-02: Entire Audio File Loaded into RAM on Playback Request
- **Severity:** P2 (Medium Performance & Resource Risk)
- **Affected Files:** [`backend/app/services/conversation_service.py`](file:///mnt/4B2725090A15B9D5/Projects/foundersignal/backend/app/services/conversation_service.py#L153), [`backend/app/core/storage/local.py`](file:///mnt/4B2725090A15B9D5/Projects/foundersignal/backend/app/core/storage/local.py#L135-L136)
- **Lines:** `conversation_service.py:153`, `storage/local.py:135-136`
- **Technical Explanation:**
  `storage.get_file_bytes` executes `with open(full_path, "rb") as f: return f.read()`. The entire file is loaded into a contiguous Python `bytes` object in memory, then wrapped in `Response(content=file_bytes)`.
  With allowed uploads of 25MB, concurrent users streaming audio will rapidly consume server RAM.
- **Reproduction Steps:** Stream a 25MB audio file across multiple concurrent worker threads; observe backend memory usage.
- **Expected Behavior:** Audio files should be streamed in chunks using Starlette `FileResponse` or `StreamingResponse`.
- **Actual Behavior:** Synchronously buffers entire file into memory before sending.
- **Recommended Correction:** Replace `Response(content=file_bytes)` with `FileResponse(path=full_path, media_type=asset.mime_type)`.
- **Test Evidence:** Code inspection of `get_conversation_audio_file` and `storage/local.py`.

---

### FS-MED-03: Missing Physical Audio File Returns HTTP 422 Instead of 404
- **Severity:** P3 (Low Semantic Inconsistency)
- **Affected File:** [`backend/app/core/storage/local.py`](file:///mnt/4B2725090A15B9D5/Projects/foundersignal/backend/app/core/storage/local.py#L132-L133)
- **Lines:** 132–133
- **Technical Explanation:**
  When an audio file is missing from disk, `LocalStorageAdapter.get_file_bytes` raises `ValidationException("Requested audio file does not exist or invalid path.")`. In FastAPI, `ValidationException` maps to `HTTP 422 Unprocessable Entity`.
  A missing physical resource should return `HTTP 404 Not Found`.
- **Reproduction Steps:** Delete a `.wav` file from `storage/audio/` while preserving its database row. Call `GET .../audio/{id}`.
- **Expected Behavior:** `HTTP 404 Not Found`.
- **Actual Behavior:** `HTTP 422 Unprocessable Entity`.
- **Recommended Correction:** Raise `NotFoundException` when the file does not exist on disk.
- **Test Evidence:** Code inspection of `storage/local.py:132-133`.

---

### FS-QA-01: Deceptive E2E Test Reports Deferred Status as Functional Pass
- **Severity:** P3 (Low QA Inconsistency)
- **Affected File:** [`frontend/tests/05-audio-upload.spec.ts`](file:///mnt/4B2725090A15B9D5/Projects/foundersignal/frontend/tests/05-audio-upload.spec.ts#L150-L158)
- **Lines:** 150–158
- **Technical Explanation:**
  Test `"Phase 2C Transcription Interface status: checks if transcription UI is deferred"` contains:
  ```ts
  const response = await page.goto("/conversations/00000000-0000-0000-0000-000000000000");
  expect([404, 200]).toContain(response?.status() ?? 404);
  ```
  Accepting either 200 or 404 asserts nothing functional. It is a historical artifact from Phase 2A/2B that should be retired now that Phase 2C implements `/conversations/[id]`.
- **Recommended Correction:** Remove this deferred test and replace it with a test asserting that invalid UUIDs return a proper 404 or redirect.
- **Test Evidence:** Code inspection of `frontend/tests/05-audio-upload.spec.ts`.

---

### FS-QA-02: Playwright Cross-Workspace Suite Oromits Audio, Jobs, and Commitments
- **Severity:** P3 (Low Test Coverage Defect)
- **Affected File:** [`frontend/tests/07-cross-workspace-authorization.spec.ts`](file:///mnt/4B2725090A15B9D5/Projects/foundersignal/frontend/tests/07-cross-workspace-authorization.spec.ts)
- **Lines:** 1–181
- **Technical Explanation:**
  File `07-cross-workspace-authorization.spec.ts` only tests workspace details, conversation listing, conversation creation, and conversation deletion. It has zero test coverage for cross-workspace audio streaming, transcription job management, or commitment mutations.
- **Recommended Correction:** Expand `07-cross-workspace-authorization.spec.ts` with test cases covering cross-tenant audio streaming, job inspection, and commitment updates.
- **Test Evidence:** Grep analysis of `07-cross-workspace-authorization.spec.ts`.

---

### FS-OPS-01: Code Style Check (`ruff format --check .`) Fails Across 6 Files
- **Severity:** P3 (Low Code Quality Defect)
- **Affected Files:**
  - `backend/app/api/router.py`
  - `backend/app/api/v1/endpoints/conversations.py`
  - `backend/app/schemas/commitment.py`
  - `backend/app/services/commitment_service.py`
  - `backend/app/services/conversation_service.py`
  - `backend/tests/test_commitments.py`
- **Technical Explanation:**
  Running `ruff format --check .` exits with code 1, reporting 6 unformatted files containing extra blank lines at EOF and irregular spacing.
- **Reproduction Steps:** Run `cd backend && .venv/bin/ruff format --check .`.
- **Expected Behavior:** `6 files formatted, 67 files already formatted`.
- **Actual Behavior:** Exits with code 1.
- **Recommended Correction:** Run `ruff format .` once audit phase is concluded.
- **Test Evidence:** Terminal command execution output.

---

### FS-OPS-02: Uncommitted Working Tree State in Git
- **Severity:** P3 (Low Version Control Risk)
- **Affected Files:** Entire Phase 2C changeset (15 modified files, 11 untracked paths)
- **Technical Explanation:**
  The git working tree is dirty on branch `main` at `6f1f038`. No Phase 2C changes have been staged or committed.
- **Recommended Correction:** Once all remediation items are implemented, organize the changeset into atomic, well-documented git commits.
- **Test Evidence:** `git status --short`.

---

## D. Live Provider Verification

| Provider Integration Path | Live Test Executed? | Result | Transcript Excerpt / Details | Confidence Score |
|---|---|---|---|---|
| **Gnani Prisma REST STT** (`https://api.vachana.ai/stt/v3`) | **YES** | **PASS** | *"And so, my fellow Americans, ask not what your country can do for you. Ask what you can do for your country."* (11.00s WAV) | `None` (Faithfully preserved, no fake scores generated) |
| **Gnani Prisma Batch Job Creation** (`POST /stt/v3/batch/jobs`) | **YES** | **PASS** | External Job ID: `01a1d113-3d1c-713c-a519-317662292cc5` | N/A |
| **Gnani Prisma Batch Job Start** (`POST /stt/v3/batch/jobs/{id}/start`) | **YES** | **PASS** | HTTP 200 OK | N/A |
| **Gnani Prisma Batch Status Polling** (`GET /stt/v3/batch/jobs/{id}`) | **YES** | **PASS** | Status: `COMPLETED`, Percent: `0` | N/A |
| **Gnani Prisma Batch Transcript Retrieval** (Pre-signed S3 download) | **YES** | **PASS** | 3 diarized segments retrieved: `Speaker 1` (0.0-3.04s, 3.04-5.184s, 5.184-11.0s) | `None` (Accurately parsed as `None`) |
| **Gnani Prisma Batch Long Recording (>30s)** | **NO** | **NOT VERIFIED** | No audio recording > 30s exists in repository or test fixtures to verify automatic routing and completion of long audio. | N/A |
| **LLM Provider Extraction** | **NO** | **MOCK ONLY** | `LLM_PROVIDER=mock`. Production adapter is unimplemented (`NotImplementedError`). | Hardcoded `0.92` from mock |

---

## E. Independent Test Results

### 1. Backend Verification Commands

| Command | Exit Code | Result | Duration | Notes |
|---|---|---|---|---|
| `.venv/bin/ruff check .` | 0 | **PASS** | 0.22s | All lint checks passed cleanly. |
| `.venv/bin/ruff format --check .` | 1 | **FAIL** | 0.08s | 6 files would be reformatted; extra blank lines at EOF. |
| `.venv/bin/alembic check` | 0 | **PASS** | 1.10s | Database schema synchronized with migrations. Head: `8af19defa86a`. |
| `.venv/bin/pytest -v` | 0 | **PASS** | 9.20s | 107 passed, 0 failed, 0 skipped. |

### 2. Frontend Verification Commands

| Command | Exit Code | Result | Duration | Notes |
|---|---|---|---|---|
| `npm run typecheck` (`tsc --noEmit`) | 0 | **PASS** | 2.10s | Strict mode enabled, zero type errors. |
| `npm run lint` (`next lint`) | 0 | **PASS** | 3.40s | Zero ESLint errors or warnings. |
| `npx playwright test` | 0 | **PASS** | 102.0s | 38 passed, 0 failed, 0 skipped across 8 test suites. |

### 3. Adversarial Multi-Tenant Security Test Suite (`scratch/test_adversarial_security.py`)

- **Total Adversarial Paths Tested:** 18
- **Access Forbidden / Blocked (403/404):** 17 paths
- **Defects Identified:** 1 path (Path 5.2 returned 200 `[]` instead of 404 on cross-workspace conversation jobs query).

---

## F. Remediation Roadmap

### 1. Must Fix Before Next Phase (Phase 3 Blocker)
1. **Implement Concrete LLM Provider Adapter:** Replace `NotImplementedError` in `app/providers/llm/base.py` with an operational LLM provider (OpenAI or Gemini) using structured JSON output.
2. **Implement HTTP Byte-Range Handling or Use FileResponse:** Update `GET /workspaces/{ws_id}/conversations/{conv_id}/audio/{audio_asset_id}` to handle RFC 7233 range requests and return `HTTP 206 Partial Content`.
3. **Add Commitment Deduplication:** In `CommitmentService.extract_commitments_from_transcript`, verify that duplicate statements or quotes are not re-inserted on repeated extraction.
4. **Implement Commitment State Machine:** Prevent invalid status jumps (e.g. `rejected` directly to `confirmed`).
5. **Fix Cross-Workspace Hierarchy Gap on Jobs Endpoint:** Add conversation-to-workspace ownership check in `TranscriptionJobService.list_jobs_for_conversation`.

### 2. Should Fix Before External Demo
1. **Correct Transcript Header Wording:** Change `"Verified Transcript"` in `frontend/src/components/transcript-view.tsx` to `"Transcript"` or `"Automated Transcript"`.
2. **Expose Diarization Segments in UI:** Update frontend `Transcript` type and component to display speaker turns and timestamps.
3. **Format Codebase:** Run `ruff format .` to clear formatting violations.

### 3. Recommended Before Production
1. **Stream Audio Instead of Buffering in Memory:** Utilize streaming responses to avoid loading 25MB files into RAM.
2. **Enforce RBAC on Commitments:** Restrict commitment approval, rejection, and deletion to `owner` and `admin` roles.
3. **Fix Schema Confidence Default:** Change `CommitmentCreate.confidence_score` default from `1.0` to `None`.
4. **Obtain and Test a Genuine >30s Speech Recording:** Perform end-to-end verification of automatic batch routing with a genuine long-form recording.

### 4. Optional Improvements
1. Remove deprecated Next.js lint runner in favor of ESLint CLI.
2. Add partial composite unique index on `commitments (conversation_id, source_quote)`.
3. Eliminate duplicate conversation refetch on initial load in `transcription-status.tsx`.

---

## G. Final Recommendation

**Can FounderSignal safely proceed to its next development stage?**

### **YES, CONDITIONALLY.**

FounderSignal's underlying foundation—PostgreSQL database integrity, multi-tenant workspace isolation, audio security validation, worker lease fencing, and Gnani Prisma STT integration—is rock solid. The system correctly passes all 107 unit tests and 38 Playwright E2E tests, and successfully transcribes spoken audio using the live Gnani Prisma STT engine.

However, the team must execute the **5 "Must Fix" items in Section F.1** (specifically implementing a functional LLM extraction provider, resolving HTTP byte-range audio streaming, and adding commitment deduplication and status guards) before proceeding to Phase 3.
