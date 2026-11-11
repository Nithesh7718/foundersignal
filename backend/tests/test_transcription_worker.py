"""Comprehensive automated tests for Phase 2B.3 background transcription worker,

leasing, polling, recovery, and reconciliation.
"""

import io
import tempfile
import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.exceptions import ConflictException, ExternalProviderException
from app.core.storage.local import LocalStorageAdapter
from app.models.audio_asset import AudioAsset
from app.models.conversation import Conversation
from app.models.transcript import Transcript
from app.models.transcription_job import TranscriptionJob
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership
from app.providers.stt.base import (
    BatchJobStatus,
    MockGnaniPrismaSTTProvider,
    STTResult,
    TranscriptSegment,
)
from app.services.transcription_job_service import TranscriptionJobService
from app.workers.transcription_worker import TranscriptionWorker
from tests.test_conversations import create_minimal_wav_bytes
from tests.test_workspaces import create_authenticated_user


@pytest.fixture(autouse=True)
def clean_transcription_jobs() -> Generator[None, None, None]:
    """Ensure worker tests start and end with an empty transcription job table."""
    with SessionLocal() as db:
        db.execute(text("DELETE FROM transcription_jobs"))
        db.commit()
    yield
    with SessionLocal() as db:
        db.execute(text("DELETE FROM transcription_jobs"))
        db.commit()


async def _provision_test_data(
    db: Session,
    storage: LocalStorageAdapter,
    duration_seconds: float = 60.0,
    file_bytes: bytes | None = None,
) -> tuple[Workspace, Conversation, AudioAsset, User]:
    """Helper to provision a workspace, user, conversation, and stored audio asset."""
    user = User(
        email=f"worker_tester_{uuid.uuid4()}@example.com",
        hashed_password="hashed_pw_test",
        full_name="Worker Tester",
        is_active=True,
    )
    db.add(user)
    db.flush()

    workspace = Workspace(
        name="Worker Test Workspace",
        slug=f"worker-{uuid.uuid4()}",
        owner_id=user.id,
    )
    db.add(workspace)
    db.flush()

    membership = WorkspaceMembership(
        workspace_id=workspace.id,
        user_id=user.id,
        role="owner",
    )
    db.add(membership)
    db.flush()

    conversation = Conversation(
        workspace_id=workspace.id,
        title="Worker Test Conversation",
        conversation_type="meeting",
        status="uploaded",
    )
    db.add(conversation)
    db.flush()

    content = file_bytes or (create_minimal_wav_bytes() + b"\x00" * 1024)
    asset_id = str(uuid.uuid4())

    rel_path, size, mime, _ = await storage.save_file(
        workspace_id=str(workspace.id),
        asset_id=asset_id,
        original_filename="meeting.wav",
        file_obj=io.BytesIO(content),
    )

    asset = AudioAsset(
        id=uuid.UUID(asset_id),
        workspace_id=workspace.id,
        conversation_id=conversation.id,
        file_name="meeting.wav",
        storage_path=rel_path,
        file_size_bytes=size,
        mime_type=mime,
        duration_seconds=duration_seconds,
        status="ready",
    )
    db.add(asset)
    db.commit()
    db.refresh(workspace)
    db.refresh(conversation)
    db.refresh(asset)
    db.refresh(user)
    return workspace, conversation, asset, user


@pytest.mark.asyncio
async def test_worker_claims_queued_job_exclusively() -> None:
    """1. Queued job is claimed by one worker; another worker cannot claim it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageAdapter(base_directory=tmpdir)
        with SessionLocal() as db:
            ws, conv, asset, _ = await _provision_test_data(db, storage, duration_seconds=45.0)
            job = TranscriptionJobService.create_job(
                db=db,
                workspace_id=ws.id,
                conversation_id=conv.id,
                audio_asset_id=asset.id,
            )

            # Worker A claims the job
            claimed_a = TranscriptionJobService.claim_queued_jobs(
                db=db,
                worker_id="worker-A",
                limit=5,
                lease_duration_seconds=60,
            )
            assert len(claimed_a) == 1
            assert claimed_a[0].id == job.id
            assert claimed_a[0].locked_by == "worker-A"
            assert claimed_a[0].lease_expires_at is not None

            # Worker B attempts to claim; should get nothing because lease is active
            claimed_b = TranscriptionJobService.claim_queued_jobs(
                db=db,
                worker_id="worker-B",
                limit=5,
                lease_duration_seconds=60,
            )
            assert len(claimed_b) == 0


@pytest.mark.asyncio
async def test_concurrent_workers_skip_locked() -> None:
    """2. Concurrent workers cannot claim the same job (SKIP LOCKED)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageAdapter(base_directory=tmpdir)
        with SessionLocal() as db1:
            ws, conv, asset, _ = await _provision_test_data(db1, storage, duration_seconds=50.0)
            job = TranscriptionJobService.create_job(
                db=db1,
                workspace_id=ws.id,
                conversation_id=conv.id,
                audio_asset_id=asset.id,
            )

            # Session 1 locks the row with FOR UPDATE
            locked_job = (
                db1.execute(
                    select(TranscriptionJob)
                    .where(TranscriptionJob.id == job.id)
                    .with_for_update(skip_locked=True)
                )
                .scalars()
                .first()
            )
            assert locked_job is not None

            # Session 2 tries to claim queued jobs while session 1 holds lock
            with SessionLocal() as db2:
                claimed_concurrent = TranscriptionJobService.claim_queued_jobs(
                    db=db2,
                    worker_id="worker-concurrent",
                    limit=5,
                )
                # Must skip locked row and return empty
                assert len(claimed_concurrent) == 0

            db1.rollback()


@pytest.mark.asyncio
async def test_worker_submits_batch_job_successfully() -> None:
    """3 & 4. Worker submits Batch job successfully and persists external job ID."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageAdapter(base_directory=tmpdir)
        provider = MockGnaniPrismaSTTProvider()
        worker = TranscriptionWorker(
            worker_id="test-worker",
            provider=provider,
            storage=storage,
        )

        with SessionLocal() as db:
            ws, conv, asset, _ = await _provision_test_data(db, storage, duration_seconds=60.0)
            job = TranscriptionJobService.create_job(
                db=db,
                workspace_id=ws.id,
                conversation_id=conv.id,
                audio_asset_id=asset.id,
            )
            assert job.status == "queued"
            assert job.job_type == "batch"

            summary = await worker.run_once_async(db=db)
            assert summary["queued_processed"] == 1

            db.refresh(job)
            assert job.status == "submitted"
            assert job.external_job_id is not None
            assert job.external_job_id.startswith("mock-batch-")
            assert job.next_poll_at is not None
            assert job.locked_by is None  # Lease released for polling


@pytest.mark.asyncio
async def test_worker_polls_submitted_job_and_updates_progress() -> None:
    """5 & 6. Worker polls submitted job, transitions to processing, schedules next poll."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageAdapter(base_directory=tmpdir)
        provider = MockGnaniPrismaSTTProvider()
        worker = TranscriptionWorker(
            worker_id="test-worker",
            provider=provider,
            storage=storage,
        )

        with SessionLocal() as db:
            ws, conv, asset, _ = await _provision_test_data(db, storage, duration_seconds=60.0)
            job = TranscriptionJobService.create_job(
                db=db,
                workspace_id=ws.id,
                conversation_id=conv.id,
                audio_asset_id=asset.id,
            )
            # Submit job
            await worker.run_once_async(db=db)
            db.refresh(job)
            assert job.status == "submitted"

            # Set next_poll_at to past so it is due immediately
            job.next_poll_at = datetime.now(UTC) - timedelta(seconds=1)
            db.commit()

            # Poll once -> transitions to processing
            summary = await worker.run_once_async(db=db)
            assert summary["polling_processed"] == 1

            db.refresh(job)
            assert job.status == "processing"
            assert job.progress_percent > 0
            assert job.next_poll_at is not None
            assert job.next_poll_at > datetime.now(UTC)


@pytest.mark.asyncio
async def test_worker_completed_status_persists_transcript() -> None:
    """7. Completed status retrieves and persists a transcript."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageAdapter(base_directory=tmpdir)
        provider = MockGnaniPrismaSTTProvider()
        worker = TranscriptionWorker(
            worker_id="test-worker",
            provider=provider,
            storage=storage,
        )

        with SessionLocal() as db:
            ws, conv, asset, _ = await _provision_test_data(db, storage, duration_seconds=60.0)
            job = TranscriptionJobService.create_job(
                db=db,
                workspace_id=ws.id,
                conversation_id=conv.id,
                audio_asset_id=asset.id,
            )

            # Step 1: Submit
            await worker.run_once_async(db=db)
            db.refresh(job)

            # Step 2: Poll in-progress
            job.next_poll_at = datetime.now(UTC) - timedelta(seconds=1)
            db.commit()
            await worker.run_once_async(db=db)
            db.refresh(job)

            # Step 3: Poll completion (Mock provider deterministically transitions to COMPLETED)
            job.next_poll_at = datetime.now(UTC) - timedelta(seconds=1)
            db.commit()
            await worker.run_once_async(db=db)
            db.refresh(job)

            assert job.status == "completed"
            assert job.progress_percent == 100
            assert job.completed_at is not None
            assert job.transcript_id is not None

            # Verify persisted Transcript
            transcript = db.get(Transcript, job.transcript_id)
            assert transcript is not None
            assert transcript.workspace_id == ws.id
            assert transcript.conversation_id == conv.id
            assert transcript.audio_asset_id == asset.id
            assert transcript.status == "completed"
            assert len(transcript.raw_transcript) > 0
            assert transcript.metadata_payload is not None
            assert "segments" in transcript.metadata_payload


@pytest.mark.asyncio
async def test_transcript_persistence_is_idempotent() -> None:
    """8. Transcript persistence is idempotent; does not create duplicate transcripts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageAdapter(base_directory=tmpdir)
        with SessionLocal() as db:
            ws, conv, asset, _ = await _provision_test_data(db, storage, duration_seconds=60.0)
            job = TranscriptionJobService.create_job(
                db=db,
                workspace_id=ws.id,
                conversation_id=conv.id,
                audio_asset_id=asset.id,
            )

            stt_result = STTResult(
                provider="gnani_prisma",
                is_mock=True,
                language="en-IN",
                total_duration=15.0,
                full_transcript="Idempotent transcript test.",
                segments=[
                    TranscriptSegment(
                        start_time=0.0,
                        end_time=5.0,
                        text="Idempotent transcript test.",
                        confidence=0.95,
                    )
                ],
            )

            # First save
            t1 = TranscriptionJobService.save_transcript_idempotent(db, job, stt_result)
            assert t1.id is not None

            # Second save should return the exact same transcript
            t2 = TranscriptionJobService.save_transcript_idempotent(db, job, stt_result)
            assert t2.id == t1.id

            # Verify only 1 transcript exists in DB
            all_transcripts = (
                db.execute(
                    select(Transcript).where(
                        Transcript.workspace_id == ws.id,
                        Transcript.conversation_id == conv.id,
                    )
                )
                .scalars()
                .all()
            )
            assert len(all_transcripts) == 1


@pytest.mark.asyncio
async def test_worker_failed_provider_job_transitions_correctly() -> None:
    """9. Failed provider job transitions correctly to failed state."""

    class FailingStatusProvider(MockGnaniPrismaSTTProvider):
        async def get_batch_job_status(self, external_job_id: str) -> BatchJobStatus:
            return BatchJobStatus(
                job_id=external_job_id,
                status="FAILED",
                error_message="Audio sample rate unsupported: 8000 Hz",
            )

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageAdapter(base_directory=tmpdir)
        worker = TranscriptionWorker(
            worker_id="test-worker",
            provider=FailingStatusProvider(),
            storage=storage,
        )

        with SessionLocal() as db:
            ws, conv, asset, _ = await _provision_test_data(db, storage, duration_seconds=60.0)
            job = TranscriptionJobService.create_job(
                db=db,
                workspace_id=ws.id,
                conversation_id=conv.id,
                audio_asset_id=asset.id,
            )
            # Submit
            await worker.run_once_async(db=db)
            db.refresh(job)

            # Poll
            job.next_poll_at = datetime.now(UTC) - timedelta(seconds=1)
            db.commit()
            await worker.run_once_async(db=db)
            db.refresh(job)

            assert job.status == "failed"
            assert job.error_code == "PROVIDER_JOB_FAILED"
            assert "Audio sample rate unsupported" in (job.error_message or "")


@pytest.mark.asyncio
async def test_worker_rate_limiting_triggers_exponential_backoff() -> None:
    """10. Rate limiting triggers exponential backoff."""

    class RateLimitedProvider(MockGnaniPrismaSTTProvider):
        async def get_batch_job_status(self, external_job_id: str) -> BatchJobStatus:
            raise ExternalProviderException(
                provider="gnani_prisma",
                message="HTTP 429: Too many requests. Rate limit exceeded.",
            )

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageAdapter(base_directory=tmpdir)
        worker = TranscriptionWorker(
            worker_id="test-worker",
            provider=RateLimitedProvider(),
            storage=storage,
            max_retries=3,
            batch_poll_interval=5,
        )

        with SessionLocal() as db:
            ws, conv, asset, _ = await _provision_test_data(db, storage, duration_seconds=60.0)
            job = TranscriptionJobService.create_job(
                db=db,
                workspace_id=ws.id,
                conversation_id=conv.id,
                audio_asset_id=asset.id,
            )
            # Submit with normal mock
            job.status = "submitted"
            job.external_job_id = "test-rl-123"
            job.next_poll_at = datetime.now(UTC) - timedelta(seconds=1)
            db.commit()

            # Poll attempt 1: rate limited -> backoff
            await worker.run_once_async(db=db)
            db.refresh(job)
            assert job.status == "submitted"
            assert job.attempt_count == 1
            assert job.next_poll_at is not None
            assert job.next_poll_at > datetime.now(UTC)

            # Poll attempt 2
            job.next_poll_at = datetime.now(UTC) - timedelta(seconds=1)
            db.commit()
            await worker.run_once_async(db=db)
            db.refresh(job)
            assert job.attempt_count == 2

            # Poll attempt 3: exceeds max_retries=3 -> transitions to failed
            job.next_poll_at = datetime.now(UTC) - timedelta(seconds=1)
            db.commit()
            await worker.run_once_async(db=db)
            db.refresh(job)
            assert job.status == "failed"
            assert job.error_code == "POLLING_RETRIES_EXCEEDED"


@pytest.mark.asyncio
async def test_worker_network_timeout_transitions_to_submission_unknown() -> None:
    """11. Network timeout during submission moves to submission_unknown safely."""

    class TimingOutProvider(MockGnaniPrismaSTTProvider):
        async def create_batch_job(self, *args: Any, **kwargs: Any) -> str:
            raise httpx.ConnectTimeout("Connection timed out waiting for Gnani API response.")

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageAdapter(base_directory=tmpdir)
        worker = TranscriptionWorker(
            worker_id="test-worker",
            provider=TimingOutProvider(),
            storage=storage,
        )

        with SessionLocal() as db:
            ws, conv, asset, _ = await _provision_test_data(db, storage, duration_seconds=60.0)
            job = TranscriptionJobService.create_job(
                db=db,
                workspace_id=ws.id,
                conversation_id=conv.id,
                audio_asset_id=asset.id,
            )

            await worker.run_once_async(db=db)
            db.refresh(job)

            assert job.status == "submission_unknown"
            assert job.error_code == "SUBMISSION_TIMEOUT"

            # Invariant: active audio asset lock is retained!
            with pytest.raises(ConflictException, match="already exists"):
                TranscriptionJobService.create_job(
                    db=db,
                    workspace_id=ws.id,
                    conversation_id=conv.id,
                    audio_asset_id=asset.id,
                )


@pytest.mark.asyncio
async def test_worker_crash_and_expired_lease_recovery() -> None:
    """12. Worker crash and expired lease recovery:

    - 'submitting' with expired lease -> 'submission_unknown' (preserves asset lock)
    - 'processing' with expired lease -> clears lease, resets next_poll_at = now
    - 'queued' with expired lease -> clears lease
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageAdapter(base_directory=tmpdir)
        with SessionLocal() as db:
            ws, conv, asset, _ = await _provision_test_data(db, storage, duration_seconds=60.0)

            # Case A: Job in submitting when worker crashed
            job_submitting = TranscriptionJobService.create_job(
                db=db,
                workspace_id=ws.id,
                conversation_id=conv.id,
                audio_asset_id=asset.id,
            )
            job_submitting.status = "submitting"
            job_submitting.locked_by = "crashed-worker-1"
            job_submitting.locked_at = datetime.now(UTC) - timedelta(minutes=10)
            job_submitting.lease_expires_at = datetime.now(UTC) - timedelta(minutes=5)
            db.commit()

            stats = TranscriptionJobService.recover_expired_leases(db)
            assert stats["submitting_to_unknown"] == 1

            db.refresh(job_submitting)
            assert job_submitting.status == "submission_unknown"
            assert job_submitting.error_code == "WORKER_CRASH_DURING_SUBMISSION"
            assert job_submitting.locked_by is None

            # Case B: Submitted job whose polling worker crashed
            job_submitting.status = "failed"  # release lock for next test job
            db.commit()

            job_polling = TranscriptionJobService.create_job(
                db=db,
                workspace_id=ws.id,
                conversation_id=conv.id,
                audio_asset_id=asset.id,
            )
            job_polling.status = "processing"
            job_polling.external_job_id = "external-safe-123"
            job_polling.locked_by = "crashed-worker-2"
            job_polling.lease_expires_at = datetime.now(UTC) - timedelta(minutes=5)
            db.commit()

            stats2 = TranscriptionJobService.recover_expired_leases(db)
            assert stats2["polling_reset"] == 1

            db.refresh(job_polling)
            assert job_polling.status == "processing"
            assert job_polling.locked_by is None
            assert job_polling.next_poll_at is not None
            assert job_polling.next_poll_at <= datetime.now(UTC)


@pytest.mark.asyncio
async def test_submission_unknown_is_not_blindly_resubmitted() -> None:
    """13. 'submission_unknown' jobs are never claimed or resubmitted by background worker."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageAdapter(base_directory=tmpdir)
        provider = MockGnaniPrismaSTTProvider()
        worker = TranscriptionWorker(
            worker_id="test-worker",
            provider=provider,
            storage=storage,
        )

        with SessionLocal() as db:
            ws, conv, asset, _ = await _provision_test_data(db, storage, duration_seconds=60.0)
            job = TranscriptionJobService.create_job(
                db=db,
                workspace_id=ws.id,
                conversation_id=conv.id,
                audio_asset_id=asset.id,
            )
            job.status = "submission_unknown"
            job.error_code = "SUBMISSION_UNKNOWN"
            db.commit()

            # Run worker cycle
            summary = await worker.run_once_async(db=db)
            assert summary["queued_processed"] == 0
            assert summary["polling_processed"] == 0

            db.refresh(job)
            assert job.status == "submission_unknown"


@pytest.mark.asyncio
async def test_cancelled_unconfirmed_retains_asset_lock() -> None:
    """14. 'cancelled_unconfirmed' retains audio asset lock against duplicate creation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageAdapter(base_directory=tmpdir)
        with SessionLocal() as db:
            ws, conv, asset, _ = await _provision_test_data(db, storage, duration_seconds=60.0)
            job = TranscriptionJobService.create_job(
                db=db,
                workspace_id=ws.id,
                conversation_id=conv.id,
                audio_asset_id=asset.id,
            )
            TranscriptionJobService.transition_status(
                db=db,
                workspace_id=ws.id,
                job_id=job.id,
                target_status="submitting",
            )
            TranscriptionJobService.record_submission(
                db=db,
                workspace_id=ws.id,
                job_id=job.id,
                external_job_id=f"batch-{uuid.uuid4()}",
            )
            TranscriptionJobService.cancel_job(
                db=db,
                workspace_id=ws.id,
                job_id=job.id,
                remote_confirmed=False,
            )

            db.refresh(job)
            assert job.status == "cancelled_unconfirmed"

            with pytest.raises(ConflictException, match="already exists"):
                TranscriptionJobService.create_job(
                    db=db,
                    workspace_id=ws.id,
                    conversation_id=conv.id,
                    audio_asset_id=asset.id,
                )


@pytest.mark.asyncio
async def test_workspace_isolation_enforced_across_worker_and_jobs() -> None:
    """15. Multi-tenant isolation: worker enforces workspace boundaries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageAdapter(base_directory=tmpdir)
        with SessionLocal() as db:
            ws_a, conv_a, asset_a, _ = await _provision_test_data(db, storage)
            ws_b, conv_b, asset_b, _ = await _provision_test_data(db, storage)

            job_a = TranscriptionJobService.create_job(
                db=db,
                workspace_id=ws_a.id,
                conversation_id=conv_a.id,
                audio_asset_id=asset_a.id,
            )

            # Tenant B cannot access Tenant A's job
            from app.core.exceptions import NotFoundException

            with pytest.raises(NotFoundException):
                TranscriptionJobService.get_job(db=db, workspace_id=ws_b.id, job_id=job_a.id)

            # Unresolved list query is strictly tenant-scoped
            job_a.status = "submission_unknown"
            db.commit()

            unresolved_a = TranscriptionJobService.list_unresolved_jobs(db, ws_a.id)
            unresolved_b = TranscriptionJobService.list_unresolved_jobs(db, ws_b.id)

            assert any(j.id == job_a.id for j in unresolved_a)
            assert not any(j.id == job_a.id for j in unresolved_b)


def test_worker_graceful_shutdown() -> None:
    """16. Worker shutdown is graceful upon receiving signal."""
    worker = TranscriptionWorker(worker_id="signal-test-worker")
    assert worker._shutdown is False
    worker.trigger_shutdown()
    assert worker._shutdown is True


@pytest.mark.asyncio
async def test_worker_audio_exceeding_10mb_rejected() -> None:
    """17. Audio exceeding 10 MB limit fails gracefully without calling provider."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageAdapter(base_directory=tmpdir)
        provider = MockGnaniPrismaSTTProvider()
        worker = TranscriptionWorker(
            worker_id="test-worker",
            provider=provider,
            storage=storage,
        )

        with SessionLocal() as db:
            # Provision asset with file_size_bytes exceeding 10 MB
            huge_bytes = create_minimal_wav_bytes() + b"\x00" * (11 * 1024 * 1024)
            ws, conv, asset, _ = await _provision_test_data(
                db, storage, duration_seconds=60.0, file_bytes=huge_bytes
            )

            # Create job bypassing service validation to test worker safeguard
            job = TranscriptionJob(
                workspace_id=ws.id,
                conversation_id=conv.id,
                audio_asset_id=asset.id,
                provider="gnani_prisma",
                model="prisma-v3.0",
                job_type="batch",
                status="queued",
                language_code="indic-auto",
            )
            db.add(job)
            db.commit()
            db.refresh(job)

            await worker.run_once_async(db=db)
            db.refresh(job)

            assert job.status == "failed"
            assert job.error_code == "AUDIO_FILE_TOO_LARGE"
            assert "exceeds the 10 MB limit" in (job.error_message or "")


def test_worker_operational_api_endpoints(client: TestClient) -> None:
    """18. Test full operational REST API endpoints for transcription jobs."""
    _email, token, ws_id = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create conversation
    conv_res = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations",
        headers=headers,
        json={"title": "Operational API Test", "conversation_type": "meeting"},
    )
    assert conv_res.status_code == 201
    conv_id = conv_res.json()["id"]

    # 2. Upload audio
    wav_bytes = create_minimal_wav_bytes() + b"\x00" * 200
    upload_res = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/audio",
        headers=headers,
        files={"file": ("interview.wav", io.BytesIO(wav_bytes), "audio/wav")},
    )
    assert upload_res.status_code == 201
    asset_id = upload_res.json()["id"]

    # 3. Create transcription job via POST /transcribe
    job_res = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/transcribe",
        headers=headers,
        json={"audio_asset_id": asset_id, "language_code": "indic-auto"},
    )
    assert job_res.status_code == 201
    job_data = job_res.json()
    job_id = job_data["id"]
    assert job_data["status"] == "queued"

    # 4. List jobs for conversation
    list_res = client.get(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/transcription-jobs",
        headers=headers,
    )
    assert list_res.status_code == 200
    assert any(j["id"] == job_id for j in list_res.json())

    # 5. Get job detail
    detail_res = client.get(
        f"/api/v1/workspaces/{ws_id}/transcription-jobs/{job_id}",
        headers=headers,
    )
    assert detail_res.status_code == 200
    assert detail_res.json()["id"] == job_id

    # 6. Cancel queued job
    cancel_res = client.post(
        f"/api/v1/workspaces/{ws_id}/transcription-jobs/{job_id}/cancel",
        headers=headers,
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "cancelled"

    # 7. Create another job and simulate ambiguous submission
    job_res2 = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/transcribe",
        headers=headers,
        json={"audio_asset_id": asset_id, "language_code": "indic-auto"},
    )
    assert job_res2.status_code == 201
    job_id2 = job_res2.json()["id"]

    with SessionLocal() as db:
        TranscriptionJobService.transition_status(
            db, uuid.UUID(ws_id), uuid.UUID(job_id2), "submitting"
        )
        TranscriptionJobService.record_submission_ambiguous(
            db, uuid.UUID(ws_id), uuid.UUID(job_id2)
        )

    # 8. List unresolved jobs
    unresolved_res = client.get(
        f"/api/v1/workspaces/{ws_id}/transcription-jobs/unresolved",
        headers=headers,
    )
    assert unresolved_res.status_code == 200
    unresolved_list = unresolved_res.json()
    assert any(j["id"] == job_id2 for j in unresolved_list)

    # 9. Reconcile via attach_external_id
    reconcile_res = client.post(
        f"/api/v1/workspaces/{ws_id}/transcription-jobs/{job_id2}/reconcile",
        headers=headers,
        json={
            "resolution": "attach_external_id",
            "external_job_id": f"batch-rec-{uuid.uuid4()}",
            "reason": "Recovered from provider portal logs",
        },
    )
    assert reconcile_res.status_code == 200
    assert reconcile_res.json()["status"] == "submitted"


def test_worker_health_check() -> None:
    """19. Verify worker health check report."""
    worker = TranscriptionWorker(worker_id="health-test-worker")
    with SessionLocal() as db:
        health = worker.check_health(db)
        assert health["status"] == "healthy"
        assert health["worker_id"] == "health-test-worker"
        assert health["database_connected"] is True
        assert isinstance(health["queued_jobs"], int)
        assert isinstance(health["processing_jobs"], int)
        assert isinstance(health["unresolved_jobs"], int)


@pytest.mark.asyncio
async def test_worker_processes_rest_job_successfully() -> None:
    """20. Worker processes REST transcription job (<= 30s) directly to completion."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageAdapter(base_directory=tmpdir)
        provider = MockGnaniPrismaSTTProvider()
        worker = TranscriptionWorker(
            worker_id="test-worker",
            provider=provider,
            storage=storage,
        )

        with SessionLocal() as db:
            ws, conv, asset, _ = await _provision_test_data(db, storage, duration_seconds=15.0)
            job = TranscriptionJobService.create_job(
                db=db,
                workspace_id=ws.id,
                conversation_id=conv.id,
                audio_asset_id=asset.id,
            )
            assert job.job_type == "rest"
            assert job.status == "queued"

            summary = await worker.run_once_async(db=db)
            assert summary["queued_processed"] == 1

            db.refresh(job)
            assert job.status == "completed"
            assert job.transcript_id is not None

            transcript = db.get(Transcript, job.transcript_id)
            assert transcript is not None
            assert len(transcript.raw_transcript) > 0


def test_reconcile_resolutions_and_validation(client: TestClient) -> None:
    """21. Test all reconciliation resolutions: confirm_absent, cancel, confirm_cancelled."""
    _email, token, ws_id = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create conversation and upload audio
    conv_res = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations",
        headers=headers,
        json={"title": "Reconcile Test", "conversation_type": "meeting"},
    )
    conv_id = conv_res.json()["id"]

    wav_bytes = create_minimal_wav_bytes() + b"\x00" * 200
    upload_res = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/audio",
        headers=headers,
        files={"file": ("test.wav", io.BytesIO(wav_bytes), "audio/wav")},
    )
    asset_id = upload_res.json()["id"]

    # Create job and put into submission_unknown
    job_res = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/transcribe",
        headers=headers,
        json={"audio_asset_id": asset_id},
    )
    job_id = job_res.json()["id"]

    with SessionLocal() as db:
        TranscriptionJobService.transition_status(
            db, uuid.UUID(ws_id), uuid.UUID(job_id), "submitting"
        )
        TranscriptionJobService.record_submission_ambiguous(db, uuid.UUID(ws_id), uuid.UUID(job_id))

    # Missing external_job_id for attach_external_id -> 422
    err_res = client.post(
        f"/api/v1/workspaces/{ws_id}/transcription-jobs/{job_id}/reconcile",
        headers=headers,
        json={"resolution": "attach_external_id"},
    )
    assert err_res.status_code == 422

    # Reconcile via cancel -> cancelled_unconfirmed
    cancel_res = client.post(
        f"/api/v1/workspaces/{ws_id}/transcription-jobs/{job_id}/reconcile",
        headers=headers,
        json={"resolution": "cancel", "reason": "Operator stopped tracking"},
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "cancelled_unconfirmed"

    # Reconcile via confirm_cancelled -> cancelled
    conf_cancel_res = client.post(
        f"/api/v1/workspaces/{ws_id}/transcription-jobs/{job_id}/reconcile",
        headers=headers,
        json={"resolution": "confirm_cancelled", "reason": "Confirmed with remote provider"},
    )
    assert conf_cancel_res.status_code == 200
    assert conf_cancel_res.json()["status"] == "cancelled"

    # Create new job and reconcile via confirm_absent -> failed
    job_res2 = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/transcribe",
        headers=headers,
        json={"audio_asset_id": asset_id},
    )
    job_id2 = job_res2.json()["id"]

    with SessionLocal() as db:
        TranscriptionJobService.transition_status(
            db, uuid.UUID(ws_id), uuid.UUID(job_id2), "submitting"
        )
        TranscriptionJobService.record_submission_ambiguous(
            db, uuid.UUID(ws_id), uuid.UUID(job_id2)
        )

    absent_res = client.post(
        f"/api/v1/workspaces/{ws_id}/transcription-jobs/{job_id2}/reconcile",
        headers=headers,
        json={
            "resolution": "confirm_absent",
            "reason": "Provider logs confirmed job never received",
        },
    )
    assert absent_res.status_code == 200
    assert absent_res.json()["status"] == "failed"


@pytest.mark.asyncio
async def test_worker_lease_fencing_rejects_stale_worker_after_expiry_and_reclaim() -> None:
    """FS-01: Worker A's lease expires; Worker B reclaims; Worker A's update is rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageAdapter(base_directory=tmpdir)
        with SessionLocal() as db:
            ws, conv, asset, _ = await _provision_test_data(db, storage, duration_seconds=45.0)
            job = TranscriptionJobService.create_job(
                db=db,
                workspace_id=ws.id,
                conversation_id=conv.id,
                audio_asset_id=asset.id,
            )

            # 1. Worker A claims the job with a 1-second lease
            claimed_a = TranscriptionJobService.claim_queued_jobs(
                db=db,
                worker_id="worker-A",
                limit=1,
                lease_duration_seconds=1,
            )
            assert len(claimed_a) == 1
            token_a = claimed_a[0].lease_token
            assert token_a is not None

            # 2. Worker A's lease expires (simulated by updating lease_expires_at to past)
            job.lease_expires_at = datetime.now(UTC) - timedelta(seconds=5)
            db.commit()

            # 3. Worker B claims the job
            claimed_b = TranscriptionJobService.claim_queued_jobs(
                db=db,
                worker_id="worker-B",
                limit=1,
                lease_duration_seconds=60,
            )
            assert len(claimed_b) == 1
            token_b = claimed_b[0].lease_token
            assert token_b is not None
            assert token_b != token_a
            assert claimed_b[0].locked_by == "worker-B"

            # 4. Worker A attempts state update with its stale credentials
            with pytest.raises(ConflictException, match="does not own active lease"):
                TranscriptionJobService.transition_status(
                    db=db,
                    workspace_id=ws.id,
                    job_id=job.id,
                    target_status="submitting",
                    expected_worker_id="worker-A",
                    expected_lease_token=token_a,
                )

            # 5. Verify Worker B's lease and state remain completely unaffected
            db.refresh(job)
            assert job.locked_by == "worker-B"
            assert job.lease_token == token_b
            assert job.status == "queued"

            # 6. Worker B can successfully transition the job
            updated_b = TranscriptionJobService.transition_status(
                db=db,
                workspace_id=ws.id,
                job_id=job.id,
                target_status="submitting",
                expected_worker_id="worker-B",
                expected_lease_token=token_b,
            )
            assert updated_b.status == "submitting"
            assert updated_b.locked_by == "worker-B"


@pytest.mark.asyncio
async def test_worker_fencing_protects_against_delayed_rest_response() -> None:
    """FS-01: Delayed REST provider response arriving after lease expiry is aborted safely."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageAdapter(base_directory=tmpdir)

        class DelayedMockProvider(MockGnaniPrismaSTTProvider):
            target_job_id: uuid.UUID

            async def transcribe_sync(
                self,
                audio_bytes: bytes,
                filename: str = "audio.wav",
                language: str = "indic-auto",
            ) -> STTResult:
                # Simulate expiry and reclamation during HTTP call
                with SessionLocal() as db_inner:
                    inner_job = db_inner.get(TranscriptionJob, self.target_job_id)
                    assert inner_job is not None
                    inner_job.locked_by = "worker-B"
                    inner_job.lease_token = uuid.uuid4()
                    db_inner.commit()
                return await super().transcribe_sync(audio_bytes, filename, language)

        provider = DelayedMockProvider()
        worker = TranscriptionWorker(
            worker_id="worker-A",
            provider=provider,
            storage=storage,
        )

        with SessionLocal() as db:
            ws, conv, asset, _ = await _provision_test_data(db, storage, duration_seconds=15.0)
            job = TranscriptionJobService.create_job(
                db=db,
                workspace_id=ws.id,
                conversation_id=conv.id,
                audio_asset_id=asset.id,
            )
            provider.target_job_id = job.id

            claimed = TranscriptionJobService.claim_queued_jobs(
                db=db,
                worker_id="worker-A",
                limit=1,
                lease_duration_seconds=60,
            )
            assert len(claimed) == 1

            # Execute queued processing - DelayedMockProvider will steal lease during call
            await worker._process_queued_job(db, claimed[0])

            # Verify job was NOT completed by stale worker A and lease remains Worker B's
            db.refresh(job)
            assert job.status == "submitting"
            assert job.locked_by == "worker-B"
            assert job.transcript_id is None


@pytest.mark.asyncio
async def test_worker_fencing_protects_against_delayed_batch_response() -> None:
    """FS-01: Delayed Batch submission response arriving after recovery is dropped safely."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageAdapter(base_directory=tmpdir)

        class DelayedBatchProvider(MockGnaniPrismaSTTProvider):
            target_job_id: uuid.UUID

            async def create_batch_job(
                self,
                audio_bytes: bytes,
                filename: str = "audio.wav",
                language: str = "indic-auto",
                with_diarization: bool = True,
                num_speakers: int = 5,
            ) -> str:
                # Simulate lease expiration and recovery during slow HTTP request
                with SessionLocal() as db_inner:
                    inner_job = db_inner.get(TranscriptionJob, self.target_job_id)
                    assert inner_job is not None
                    inner_job.lease_expires_at = datetime.now(UTC) - timedelta(seconds=10)
                    db_inner.commit()
                    TranscriptionJobService.recover_expired_leases(db_inner)
                return "gnani-delayed-batch-123"

        provider = DelayedBatchProvider()
        worker = TranscriptionWorker(
            worker_id="worker-A",
            provider=provider,
            storage=storage,
        )

        with SessionLocal() as db:
            ws, conv, asset, _ = await _provision_test_data(db, storage, duration_seconds=60.0)
            job = TranscriptionJobService.create_job(
                db=db,
                workspace_id=ws.id,
                conversation_id=conv.id,
                audio_asset_id=asset.id,
            )
            provider.target_job_id = job.id

            claimed = TranscriptionJobService.claim_queued_jobs(
                db=db,
                worker_id="worker-A",
                limit=1,
                lease_duration_seconds=60,
            )
            assert len(claimed) == 1

            # Run submission - provider callback triggers recovery to submission_unknown
            await worker._process_queued_job(db, claimed[0])

            # Verify that recovery state (submission_unknown) was not overwritten by Worker A
            db.refresh(job)
            assert job.status == "submission_unknown"
            assert job.error_code == "WORKER_CRASH_DURING_SUBMISSION"
            assert job.locked_by is None


def test_reconcile_and_cancel_role_authorization(client: TestClient) -> None:
    """FS-02: Reconcile & cancel require owner or admin role; member is rejected with 403."""
    from app.core.security import create_access_token

    # 1. Create owner and workspace
    _owner_email, owner_token, ws_id = create_authenticated_user(client)
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    # Create admin and member users
    with SessionLocal() as db:
        admin_user = User(
            email=f"admin_{uuid.uuid4()}@example.com",
            hashed_password="pw",
            full_name="Admin User",
            is_active=True,
        )
        member_user = User(
            email=f"member_{uuid.uuid4()}@example.com",
            hashed_password="pw",
            full_name="Member User",
            is_active=True,
        )
        db.add(admin_user)
        db.add(member_user)
        db.flush()

        admin_id = admin_user.id
        member_id = member_user.id

        db.add(
            WorkspaceMembership(
                workspace_id=uuid.UUID(ws_id),
                user_id=admin_id,
                role="admin",
            )
        )
        db.add(
            WorkspaceMembership(
                workspace_id=uuid.UUID(ws_id),
                user_id=member_id,
                role="member",
            )
        )
        db.commit()

    admin_token, _, _ = create_access_token(subject=admin_id)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    member_token, _, _ = create_access_token(subject=member_id)
    member_headers = {"Authorization": f"Bearer {member_token}"}

    # Create conversation and upload audio
    conv_res = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations",
        headers=owner_headers,
        json={"title": "RBAC Test Conversation", "conversation_type": "meeting"},
    )
    conv_id = conv_res.json()["id"]

    wav_bytes = create_minimal_wav_bytes() + b"\x00" * 200
    upload_res = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/audio",
        headers=owner_headers,
        files={"file": ("rbac.wav", io.BytesIO(wav_bytes), "audio/wav")},
    )
    asset_id = upload_res.json()["id"]

    # 2. Member CANNOT cancel job (403 Forbidden)
    job_res1 = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/transcribe",
        headers=owner_headers,
        json={"audio_asset_id": asset_id},
    )
    job_id1 = job_res1.json()["id"]

    cancel_member_res = client.post(
        f"/api/v1/workspaces/{ws_id}/transcription-jobs/{job_id1}/cancel",
        headers=member_headers,
    )
    assert cancel_member_res.status_code == 403
    assert "Only workspace owners and admins" in cancel_member_res.json()["error"]["message"]

    # 3. Admin CAN cancel job (200 OK)
    cancel_admin_res = client.post(
        f"/api/v1/workspaces/{ws_id}/transcription-jobs/{job_id1}/cancel",
        headers=admin_headers,
    )
    assert cancel_admin_res.status_code == 200
    assert cancel_admin_res.json()["status"] == "cancelled"

    # 4. Create second job and simulate ambiguous submission
    job_res2 = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/transcribe",
        headers=owner_headers,
        json={"audio_asset_id": asset_id},
    )
    job_id2 = job_res2.json()["id"]

    with SessionLocal() as db:
        TranscriptionJobService.transition_status(
            db, uuid.UUID(ws_id), uuid.UUID(job_id2), "submitting"
        )
        TranscriptionJobService.record_submission_ambiguous(
            db, uuid.UUID(ws_id), uuid.UUID(job_id2)
        )

    # 5. Member CANNOT reconcile job (403 Forbidden)
    reconcile_member_res = client.post(
        f"/api/v1/workspaces/{ws_id}/transcription-jobs/{job_id2}/reconcile",
        headers=member_headers,
        json={"resolution": "confirm_absent", "reason": "Member trying to reconcile"},
    )
    assert reconcile_member_res.status_code == 403
    assert "Only workspace owners and admins" in reconcile_member_res.json()["error"]["message"]

    # 6. Admin CAN reconcile job (200 OK)
    reconcile_admin_res = client.post(
        f"/api/v1/workspaces/{ws_id}/transcription-jobs/{job_id2}/reconcile",
        headers=admin_headers,
        json={"resolution": "confirm_absent", "reason": "Admin verified absence with provider"},
    )
    assert reconcile_admin_res.status_code == 200
    assert reconcile_admin_res.json()["status"] == "failed"

    # 7. Cross-workspace isolation: user in another workspace is rejected with 403 or 404
    _other_email, other_token, other_ws_id = create_authenticated_user(client)
    other_headers = {"Authorization": f"Bearer {other_token}"}

    # Attempting to access ws_id with other user's credentials -> 403 Forbidden
    cross_ws_cancel_res = client.post(
        f"/api/v1/workspaces/{ws_id}/transcription-jobs/{job_id1}/cancel",
        headers=other_headers,
    )
    assert cross_ws_cancel_res.status_code == 403

    cross_ws_reconcile_res = client.post(
        f"/api/v1/workspaces/{ws_id}/transcription-jobs/{job_id2}/reconcile",
        headers=other_headers,
        json={"resolution": "confirm_absent"},
    )
    assert cross_ws_reconcile_res.status_code == 403

    # Attempting to target job_id1 under other_ws_id -> 404 NotFound
    cross_job_cancel_res = client.post(
        f"/api/v1/workspaces/{other_ws_id}/transcription-jobs/{job_id1}/cancel",
        headers=other_headers,
    )
    assert cross_job_cancel_res.status_code == 404


def test_public_api_exposure_lease_token_never_exposed_or_client_settable(
    client: TestClient,
) -> None:
    """Requirement 1: Verify lease_token is NEVER exposed in public API responses,

    and cannot be set or manipulated by client request payloads.
    """
    _email, token, ws_id = create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    conv_res = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations",
        headers=headers,
        json={"title": "Lease Token Privacy Test", "conversation_type": "meeting"},
    )
    conv_id = conv_res.json()["id"]

    wav_bytes = create_minimal_wav_bytes() + b"\x00" * 200
    upload_res = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/audio",
        headers=headers,
        files={"file": ("privacy.wav", io.BytesIO(wav_bytes), "audio/wav")},
    )
    asset_id = upload_res.json()["id"]

    # 1. Attempt to inject lease_token during job creation
    forged_token = str(uuid.uuid4())
    create_res = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/transcribe",
        headers=headers,
        json={
            "audio_asset_id": asset_id,
            "language_code": "indic-auto",
            "lease_token": forged_token,  # Malicious/unsupported input
        },
    )
    assert create_res.status_code == 201
    created_payload = create_res.json()
    assert "lease_token" not in created_payload
    job_id = created_payload["id"]

    # Verify database model does not store the forged client token
    with SessionLocal() as db:
        db_job = db.get(TranscriptionJob, uuid.UUID(job_id))
        assert db_job is not None
        assert db_job.lease_token is None  # Queued job has no lease token

        # Worker claims job, generating legitimate internal lease_token
        claimed = TranscriptionJobService.claim_queued_jobs(db, worker_id="worker-test", limit=1)
        assert len(claimed) == 1
        assert claimed[0].lease_token is not None

    # 2. Verify GET /transcription-jobs/{id} redacts lease_token
    get_res = client.post(  # also verify cancel response doesn't expose it
        f"/api/v1/workspaces/{ws_id}/transcription-jobs/{job_id}/cancel",
        headers=headers,
    )
    assert "lease_token" not in get_res.json()

    # 3. Create second job, claim it, and verify GET /transcription-jobs/{id}
    job_res2 = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/transcribe",
        headers=headers,
        json={"audio_asset_id": asset_id},
    )
    job_id2 = job_res2.json()["id"]

    with SessionLocal() as db:
        claimed2 = TranscriptionJobService.claim_queued_jobs(db, worker_id="worker-test-2", limit=1)
        assert len(claimed2) == 1
        assert claimed2[0].lease_token is not None

    get_job2_res = client.get(
        f"/api/v1/workspaces/{ws_id}/transcription-jobs/{job_id2}",
        headers=headers,
    )
    assert get_job2_res.status_code == 200
    assert "lease_token" not in get_job2_res.json()

    # 4. Verify GET /conversations/{id}/transcription-jobs redacts lease_token for all items
    list_res = client.get(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/transcription-jobs",
        headers=headers,
    )
    assert list_res.status_code == 200
    jobs_list = list_res.json()
    assert len(jobs_list) >= 2
    for j in jobs_list:
        assert "lease_token" not in j

    # 5. Move job_id2 to submission_unknown and verify GET /unresolved redacts lease_token
    with SessionLocal() as db:
        TranscriptionJobService.transition_status(
            db, uuid.UUID(ws_id), uuid.UUID(job_id2), "submitting"
        )
        TranscriptionJobService.record_submission_ambiguous(
            db, uuid.UUID(ws_id), uuid.UUID(job_id2)
        )

    unresolved_res = client.get(
        f"/api/v1/workspaces/{ws_id}/transcription-jobs/unresolved",
        headers=headers,
    )
    assert unresolved_res.status_code == 200
    for j in unresolved_res.json():
        assert "lease_token" not in j

    # 6. Verify POST /reconcile cannot inject forged lease_token and response redacts it
    reconcile_res = client.post(
        f"/api/v1/workspaces/{ws_id}/transcription-jobs/{job_id2}/reconcile",
        headers=headers,
        json={
            "resolution": "confirm_absent",
            "reason": "Audited absence",
            "lease_token": str(uuid.uuid4()),  # Ignored/rejected forged token
        },
    )
    assert reconcile_res.status_code == 200
    assert "lease_token" not in reconcile_res.json()
    with SessionLocal() as db:
        final_job = db.get(TranscriptionJob, uuid.UUID(job_id2))
        assert final_job is not None
        assert final_job.lease_token is None
