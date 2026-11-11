import uuid

import pytest
from sqlalchemy.exc import IntegrityError, ProgrammingError

from app.core.database import SessionLocal
from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.audio_asset import AudioAsset
from app.models.conversation import Conversation
from app.models.transcript import Transcript
from app.models.transcription_job import TranscriptionJob
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership
from app.services.transcription_job_service import (
    TranscriptionJobService,
    sanitize_error_message,
)


def _create_test_workspace_and_conversation(
    db, duration_seconds: float | None = 15.0
) -> tuple[Workspace, Conversation, AudioAsset]:
    """Helper to provision a test workspace, conversation, and audio asset."""
    user = User(
        email=f"tester_{uuid.uuid4()}@example.com",
        hashed_password="hashed_pw_test",
        full_name="Tester",
        is_active=True,
    )
    db.add(user)
    db.flush()

    workspace = Workspace(name="Test Studio", slug=f"test-{uuid.uuid4()}", owner_id=user.id)
    db.add(workspace)
    db.flush()

    membership = WorkspaceMembership(workspace_id=workspace.id, user_id=user.id, role="owner")
    db.add(membership)
    db.flush()

    conversation = Conversation(
        workspace_id=workspace.id,
        title="Weekly Sync",
        conversation_type="meeting",
        status="uploaded",
    )
    db.add(conversation)
    db.flush()

    asset = AudioAsset(
        workspace_id=workspace.id,
        conversation_id=conversation.id,
        file_name="sync.wav",
        storage_path=f"storage/{workspace.id}/sync.wav",
        file_size_bytes=1024 * 100,
        mime_type="audio/wav",
        duration_seconds=duration_seconds,
        status="ready",
    )
    db.add(asset)
    db.commit()
    db.refresh(workspace)
    db.refresh(conversation)
    db.refresh(asset)
    return workspace, conversation, asset


def test_create_transcription_job_rest_when_duration_under_30s() -> None:
    with SessionLocal() as db:
        ws, conv, asset = _create_test_workspace_and_conversation(db, duration_seconds=22.5)

        job = TranscriptionJobService.create_job(
            db=db,
            workspace_id=ws.id,
            conversation_id=conv.id,
            audio_asset_id=asset.id,
            language_code="en-IN",
        )

        assert job.id is not None
        assert job.workspace_id == ws.id
        assert job.conversation_id == conv.id
        assert job.audio_asset_id == asset.id
        assert job.job_type == "rest"
        assert job.status == "queued"
        assert job.attempt_count == 0
        assert job.progress_percent == 0


def test_create_transcription_job_batch_when_duration_over_30s() -> None:
    with SessionLocal() as db:
        ws, conv, asset = _create_test_workspace_and_conversation(db, duration_seconds=120.0)

        job = TranscriptionJobService.create_job(
            db=db,
            workspace_id=ws.id,
            conversation_id=conv.id,
            audio_asset_id=asset.id,
        )

        assert job.job_type == "batch"
        assert job.status == "queued"


def test_create_transcription_job_batch_when_duration_unknown() -> None:
    with SessionLocal() as db:
        ws, conv, asset = _create_test_workspace_and_conversation(db, duration_seconds=None)

        # Safe routing: uncertain duration must route to Batch, never silently to REST
        job = TranscriptionJobService.create_job(
            db=db,
            workspace_id=ws.id,
            conversation_id=conv.id,
            audio_asset_id=asset.id,
        )

        assert job.job_type == "batch"
        assert job.status == "queued"


def test_active_job_duplicate_prevention_service_and_db_constraint() -> None:
    with SessionLocal() as db:
        ws, conv, asset = _create_test_workspace_and_conversation(db, duration_seconds=10.0)

        # First job created successfully
        job1 = TranscriptionJobService.create_job(
            db=db,
            workspace_id=ws.id,
            conversation_id=conv.id,
            audio_asset_id=asset.id,
        )
        assert job1.status == "queued"

        # 1. Service layer check prevents duplicate submission
        with pytest.raises(ConflictException, match="An active transcription job already exists"):
            TranscriptionJobService.create_job(
                db=db,
                workspace_id=ws.id,
                conversation_id=conv.id,
                audio_asset_id=asset.id,
            )

        # 2. Database partial unique index prevents direct raw insertion race conditions
        raw_duplicate_job = TranscriptionJob(
            workspace_id=ws.id,
            conversation_id=conv.id,
            audio_asset_id=asset.id,
            job_type="rest",
            status="submitting",  # also an active status
        )
        db.add(raw_duplicate_job)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_duplicate_allowed_after_previous_job_completed_or_failed() -> None:
    with SessionLocal() as db:
        ws, conv, asset = _create_test_workspace_and_conversation(db, duration_seconds=10.0)

        job1 = TranscriptionJobService.create_job(
            db=db,
            workspace_id=ws.id,
            conversation_id=conv.id,
            audio_asset_id=asset.id,
        )

        # Fail job1 so it is no longer in an active status
        TranscriptionJobService.record_failure(
            db=db,
            workspace_id=ws.id,
            job_id=job1.id,
            error_code="TIMEOUT",
            error_message="Network connection timed out",
        )
        assert job1.status == "failed"

        # Now creating a new job for the same asset is allowed
        job2 = TranscriptionJobService.create_job(
            db=db,
            workspace_id=ws.id,
            conversation_id=conv.id,
            audio_asset_id=asset.id,
        )
        assert job2.id != job1.id
        assert job2.status == "queued"


def test_valid_state_transitions_lifecycle() -> None:
    with SessionLocal() as db:
        ws, conv, asset = _create_test_workspace_and_conversation(db, duration_seconds=45.0)

        job = TranscriptionJobService.create_job(
            db=db,
            workspace_id=ws.id,
            conversation_id=conv.id,
            audio_asset_id=asset.id,
        )
        assert job.status == "queued"

        # 1. queued -> submitting
        TranscriptionJobService.transition_status(
            db=db, workspace_id=ws.id, job_id=job.id, target_status="submitting"
        )
        assert job.status == "submitting"
        assert job.attempt_count == 1
        assert job.started_at is not None

        # 2. submitting -> submitted
        ext_id = f"gnani-batch-{uuid.uuid4()}"
        TranscriptionJobService.record_submission(
            db=db,
            workspace_id=ws.id,
            job_id=job.id,
            external_job_id=ext_id,
            next_poll_seconds=15,
        )
        assert job.status == "submitted"
        assert job.external_job_id == ext_id
        assert job.next_poll_at is not None

        # 3. submitted -> processing
        TranscriptionJobService.transition_status(
            db=db,
            workspace_id=ws.id,
            job_id=job.id,
            target_status="processing",
            progress_percent=55,
            next_poll_seconds=10,
        )
        assert job.status == "processing"
        assert job.progress_percent == 55
        assert job.last_polled_at is not None

        # 4. Create Transcript record before marking job completed
        transcript = Transcript(
            workspace_id=ws.id,
            conversation_id=conv.id,
            audio_asset_id=asset.id,
            provider="gnani_prisma",
            model="prisma-v3.0",
            language_code="en-IN",
            raw_transcript="Meeting transcript text.",
            status="completed",
        )
        db.add(transcript)
        db.commit()

        # 5. processing -> completed
        TranscriptionJobService.record_completion(
            db=db,
            workspace_id=ws.id,
            job_id=job.id,
            transcript_id=transcript.id,
        )
        assert job.status == "completed"
        assert job.progress_percent == 100
        assert job.transcript_id == transcript.id
        assert job.completed_at is not None
        assert job.next_poll_at is None


def test_invalid_state_transitions_raise_conflict() -> None:
    with SessionLocal() as db:
        ws, conv, asset = _create_test_workspace_and_conversation(db, duration_seconds=10.0)

        job = TranscriptionJobService.create_job(
            db=db,
            workspace_id=ws.id,
            conversation_id=conv.id,
            audio_asset_id=asset.id,
        )
        assert job.status == "queued"

        # queued -> processing is invalid
        with pytest.raises(ConflictException, match="Invalid job state transition"):
            TranscriptionJobService.transition_status(
                db=db, workspace_id=ws.id, job_id=job.id, target_status="processing"
            )

        # Cancel job
        TranscriptionJobService.cancel_job(db=db, workspace_id=ws.id, job_id=job.id)
        assert job.status == "cancelled"

        # cancelled is terminal, cannot transition to submitting
        with pytest.raises(ConflictException, match="Invalid job state transition"):
            TranscriptionJobService.transition_status(
                db=db, workspace_id=ws.id, job_id=job.id, target_status="submitting"
            )


def test_cannot_complete_without_persisted_transcript() -> None:
    with SessionLocal() as db:
        ws, conv, asset = _create_test_workspace_and_conversation(db, duration_seconds=10.0)

        job = TranscriptionJobService.create_job(
            db=db,
            workspace_id=ws.id,
            conversation_id=conv.id,
            audio_asset_id=asset.id,
        )
        TranscriptionJobService.transition_status(
            db=db, workspace_id=ws.id, job_id=job.id, target_status="submitting"
        )

        # Attempting to complete without transcript_id fails
        with pytest.raises(ValidationException, match="persisted Transcript record"):
            TranscriptionJobService.transition_status(
                db=db, workspace_id=ws.id, job_id=job.id, target_status="completed"
            )

        # Providing a random non-existent transcript ID fails
        with pytest.raises(ValidationException, match="was not found in this workspace"):
            TranscriptionJobService.record_completion(
                db=db, workspace_id=ws.id, job_id=job.id, transcript_id=uuid.uuid4()
            )


def test_error_message_sanitization() -> None:
    raw_error = (
        "Failed fetching transcript from "
        "https://s3.amazonaws.com/bucket/res.json?"
        "X-Amz-Signature=SECRET_12345&api_key=TOP_SECRET_KEY "
        "Bearer token=abc123secret"
    )
    sanitized = sanitize_error_message(raw_error)
    assert sanitized is not None
    assert "SECRET_12345" not in sanitized
    assert "TOP_SECRET_KEY" not in sanitized
    assert "abc123secret" not in sanitized
    assert "[REDACTED_URL]" in sanitized


def test_cross_workspace_isolation_blocks_access() -> None:
    with SessionLocal() as db:
        ws_a, conv_a, asset_a = _create_test_workspace_and_conversation(db, duration_seconds=10.0)
        ws_b, _conv_b, _asset_b = _create_test_workspace_and_conversation(db, duration_seconds=10.0)

        job_a = TranscriptionJobService.create_job(
            db=db,
            workspace_id=ws_a.id,
            conversation_id=conv_a.id,
            audio_asset_id=asset_a.id,
        )

        # User in Workspace B attempts to access Workspace A's job
        with pytest.raises(NotFoundException):
            TranscriptionJobService.get_job(db=db, workspace_id=ws_b.id, job_id=job_a.id)

        # User in Workspace B attempts to cancel Workspace A's job
        with pytest.raises(NotFoundException):
            TranscriptionJobService.cancel_job(db=db, workspace_id=ws_b.id, job_id=job_a.id)


def test_cross_workspace_resource_binding_rejected() -> None:
    with SessionLocal() as db:
        ws_a, conv_a, asset_a = _create_test_workspace_and_conversation(db, duration_seconds=10.0)
        ws_b, conv_b, asset_b = _create_test_workspace_and_conversation(db, duration_seconds=10.0)

        # Attempt to bind Workspace A job to Workspace B's conversation
        with pytest.raises(NotFoundException):
            TranscriptionJobService.create_job(
                db=db,
                workspace_id=ws_a.id,
                conversation_id=conv_b.id,
                audio_asset_id=asset_a.id,
            )

        # Attempt to bind Workspace A conversation to Workspace B's audio asset
        with pytest.raises(NotFoundException):
            TranscriptionJobService.create_job(
                db=db,
                workspace_id=ws_a.id,
                conversation_id=conv_a.id,
                audio_asset_id=asset_b.id,
            )


def test_cascade_deletion_on_conversation_or_workspace() -> None:
    with SessionLocal() as db:
        ws, conv, asset = _create_test_workspace_and_conversation(db, duration_seconds=10.0)

        job = TranscriptionJobService.create_job(
            db=db,
            workspace_id=ws.id,
            conversation_id=conv.id,
            audio_asset_id=asset.id,
        )
        job_id = job.id

        # Delete conversation
        db.delete(conv)
        db.commit()

        # Job must be cascaded and removed
        job_lookup = db.get(TranscriptionJob, job_id)
        assert job_lookup is None


def test_ambiguous_submission_blocks_duplicate_and_allows_manual_recovery() -> None:
    """Simulates a Batch job submission where the response is lost after provider received bytes."""
    with SessionLocal() as db:
        ws, conv, asset = _create_test_workspace_and_conversation(db, duration_seconds=60.0)

        job = TranscriptionJobService.create_job(
            db=db,
            workspace_id=ws.id,
            conversation_id=conv.id,
            audio_asset_id=asset.id,
        )
        assert job.status == "queued"

        # Transition to submitting
        TranscriptionJobService.transition_status(
            db=db, workspace_id=ws.id, job_id=job.id, target_status="submitting"
        )
        assert job.status == "submitting"

        # Network timeout / dropped connection after sending bytes:
        # We record as ambiguous (submission_unknown) rather than assuming failed
        ambiguous_job = TranscriptionJobService.record_submission_ambiguous(
            db=db,
            workspace_id=ws.id,
            job_id=job.id,
            error_code="NET_READ_TIMEOUT",
            error_message="HTTP request timed out waiting for provider batch ack",
        )
        assert ambiguous_job.status == "submission_unknown"
        assert ambiguous_job.next_poll_at is None
        assert ambiguous_job.error_code == "NET_READ_TIMEOUT"

        # 1. Service layer blocks new job creation while submission is unknown
        with pytest.raises(ConflictException, match="An active transcription job already exists"):
            TranscriptionJobService.create_job(
                db=db,
                workspace_id=ws.id,
                conversation_id=conv.id,
                audio_asset_id=asset.id,
            )

        # 2. Database partial unique index blocks concurrent insertions for the same asset
        raw_duplicate = TranscriptionJob(
            workspace_id=ws.id,
            conversation_id=conv.id,
            audio_asset_id=asset.id,
            job_type="batch",
            status="queued",
        )
        db.add(raw_duplicate)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        # 3. Manual recovery: Operator reconciles with provider and attaches discovered job ID
        ext_id = f"gnani-recon-{uuid.uuid4()}"
        recovered_job = TranscriptionJobService.resolve_ambiguous_submission(
            db=db,
            workspace_id=ws.id,
            job_id=job.id,
            resolution="attach_external_id",
            external_job_id=ext_id,
        )
        assert recovered_job.status == "submitted"
        assert recovered_job.external_job_id == ext_id
        assert recovered_job.next_poll_at is not None


def test_ambiguous_submission_cancellation_preserves_lock_and_blocks_duplicate() -> None:
    """A local cancellation request must NOT release uniqueness protection while
    remote is unconfirmed."""
    with SessionLocal() as db:
        ws, conv, asset = _create_test_workspace_and_conversation(db, duration_seconds=60.0)

        job1 = TranscriptionJobService.create_job(
            db=db,
            workspace_id=ws.id,
            conversation_id=conv.id,
            audio_asset_id=asset.id,
        )
        TranscriptionJobService.transition_status(
            db=db, workspace_id=ws.id, job_id=job1.id, target_status="submitting"
        )
        TranscriptionJobService.record_submission_ambiguous(
            db=db, workspace_id=ws.id, job_id=job1.id
        )
        assert job1.status == "submission_unknown"

        # 1. Local cancellation requested on ambiguous submission
        cancelled_job = TranscriptionJobService.cancel_job(
            db=db, workspace_id=ws.id, job_id=job1.id
        )
        assert cancelled_job.status == "cancelled_unconfirmed"
        assert cancelled_job.error_code == "CANCELLED_UNCONFIRMED"

        # 2. Uniqueness protection is NOT released: duplicate submission is blocked
        with pytest.raises(ConflictException, match="An active transcription job already exists"):
            TranscriptionJobService.create_job(
                db=db,
                workspace_id=ws.id,
                conversation_id=conv.id,
                audio_asset_id=asset.id,
            )

        # 3. Direct DB insert is blocked by partial unique index
        raw_duplicate = TranscriptionJob(
            workspace_id=ws.id,
            conversation_id=conv.id,
            audio_asset_id=asset.id,
            job_type="batch",
            status="queued",
        )
        db.add(raw_duplicate)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        # 4. Only definitive confirmation that provider never received job releases the lock
        resolved_failed = TranscriptionJobService.resolve_ambiguous_submission(
            db=db,
            workspace_id=ws.id,
            job_id=job1.id,
            resolution="confirm_absent",
            reason="Checked provider support logs: request never arrived",
        )
        assert resolved_failed.status == "failed"
        assert resolved_failed.error_code == "SUBMISSION_CONFIRMED_ABSENT"

        # 5. Now that absence was confirmed and job marked failed, new transcription can be queued
        job2 = TranscriptionJobService.create_job(
            db=db,
            workspace_id=ws.id,
            conversation_id=conv.id,
            audio_asset_id=asset.id,
        )
        assert job2.id != job1.id
        assert job2.status == "queued"


def test_ambiguous_submission_resolutions_validation() -> None:
    with SessionLocal() as db:
        ws, conv, asset = _create_test_workspace_and_conversation(db, duration_seconds=60.0)

        job = TranscriptionJobService.create_job(
            db=db,
            workspace_id=ws.id,
            conversation_id=conv.id,
            audio_asset_id=asset.id,
        )
        TranscriptionJobService.transition_status(
            db=db, workspace_id=ws.id, job_id=job.id, target_status="submitting"
        )
        TranscriptionJobService.record_submission_ambiguous(
            db=db, workspace_id=ws.id, job_id=job.id
        )

        # Validation checks
        with pytest.raises(ValidationException, match="requires a valid external_job_id"):
            TranscriptionJobService.resolve_ambiguous_submission(
                db=db,
                workspace_id=ws.id,
                job_id=job.id,
                resolution="attach_external_id",
                external_job_id="",
            )

        with pytest.raises(ValidationException, match="Unsupported resolution"):
            TranscriptionJobService.resolve_ambiguous_submission(
                db=db, workspace_id=ws.id, job_id=job.id, resolution="retry_blindly"
            )

        # Cancel resolution via resolve_ambiguous_submission
        cancelled_job = TranscriptionJobService.resolve_ambiguous_submission(
            db=db, workspace_id=ws.id, job_id=job.id, resolution="cancel"
        )
        assert cancelled_job.status == "cancelled_unconfirmed"

        # Calling resolution on already resolved failed job raises ConflictException
        TranscriptionJobService.resolve_ambiguous_submission(
            db=db, workspace_id=ws.id, job_id=job.id, resolution="confirm_absent"
        )
        with pytest.raises(ConflictException, match="Manual reconciliation is only allowed"):
            TranscriptionJobService.resolve_ambiguous_submission(
                db=db, workspace_id=ws.id, job_id=job.id, resolution="cancel"
            )


def test_external_job_id_uniqueness_scoped_per_provider() -> None:
    """External job ID uniqueness is scoped to (provider, external_job_id)."""
    with SessionLocal() as db:
        ws1, conv1, asset1 = _create_test_workspace_and_conversation(db, duration_seconds=60.0)
        ws2, conv2, asset2 = _create_test_workspace_and_conversation(db, duration_seconds=60.0)
        ws3, conv3, asset3 = _create_test_workspace_and_conversation(db, duration_seconds=60.0)

        shared_external_id = f"batch-shared-{uuid.uuid4()}"

        # 1. Job 1 gets shared_external_id under provider 'gnani_prisma'
        job1 = TranscriptionJobService.create_job(
            db=db,
            workspace_id=ws1.id,
            conversation_id=conv1.id,
            audio_asset_id=asset1.id,
            provider="gnani_prisma",
        )
        TranscriptionJobService.transition_status(
            db=db, workspace_id=ws1.id, job_id=job1.id, target_status="submitting"
        )
        TranscriptionJobService.record_submission(
            db=db,
            workspace_id=ws1.id,
            job_id=job1.id,
            external_job_id=shared_external_id,
        )

        # 2. Job 2 under the SAME provider 'gnani_prisma' attempts duplicate
        # external_job_id -> FAILS
        job2 = TranscriptionJobService.create_job(
            db=db,
            workspace_id=ws2.id,
            conversation_id=conv2.id,
            audio_asset_id=asset2.id,
            provider="gnani_prisma",
        )
        TranscriptionJobService.transition_status(
            db=db, workspace_id=ws2.id, job_id=job2.id, target_status="submitting"
        )
        job2.external_job_id = shared_external_id
        job2.status = "submitted"
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        # 3. Job 3 under a DIFFERENT provider 'timbre_stt' uses the SAME external_job_id -> SUCCEEDS
        job3 = TranscriptionJobService.create_job(
            db=db,
            workspace_id=ws3.id,
            conversation_id=conv3.id,
            audio_asset_id=asset3.id,
            provider="timbre_stt",
        )
        TranscriptionJobService.transition_status(
            db=db, workspace_id=ws3.id, job_id=job3.id, target_status="submitting"
        )
        job3.external_job_id = shared_external_id
        job3.status = "submitted"
        db.commit()
        db.refresh(job3)
        assert job3.external_job_id == shared_external_id
        assert job3.provider == "timbre_stt"


def test_database_composite_relationship_integrity() -> None:
    """Database constraints physically block cross-workspace or cross-conversation bindings."""
    with SessionLocal() as db:
        ws_a, conv_a, asset_a = _create_test_workspace_and_conversation(db, duration_seconds=30.0)
        ws_b, conv_b, asset_b = _create_test_workspace_and_conversation(db, duration_seconds=30.0)

        # 1. AudioAsset bound to conv_a but with workspace_id=ws_b -> rejected by DB composite FK
        mismatched_asset = AudioAsset(
            workspace_id=ws_b.id,
            conversation_id=conv_a.id,
            file_name="bad.wav",
            storage_path="storage/bad.wav",
            file_size_bytes=1000,
            mime_type="audio/wav",
            status="ready",
        )
        db.add(mismatched_asset)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        # 2. TranscriptionJob bound to conv_a but with workspace_id=ws_b -> rejected
        # by DB composite FK
        mismatched_job_conv = TranscriptionJob(
            workspace_id=ws_b.id,
            conversation_id=conv_a.id,
            audio_asset_id=asset_b.id,
            job_type="batch",
            status="queued",
        )
        db.add(mismatched_job_conv)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        # 3. TranscriptionJob bound to conv_a and ws_a, but with audio_asset_id=asset_b -> rejected
        mismatched_job_asset = TranscriptionJob(
            workspace_id=ws_a.id,
            conversation_id=conv_a.id,
            audio_asset_id=asset_b.id,
            job_type="batch",
            status="queued",
        )
        db.add(mismatched_job_asset)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        # 4. TranscriptionJob referencing a transcript from another workspace/conversation
        # -> rejected by DB trigger
        transcript_b = Transcript(
            workspace_id=ws_b.id,
            conversation_id=conv_b.id,
            audio_asset_id=asset_b.id,
            provider="gnani_prisma",
            raw_transcript="Remote text",
            status="completed",
        )
        db.add(transcript_b)
        db.commit()

        job_a = TranscriptionJobService.create_job(
            db=db,
            workspace_id=ws_a.id,
            conversation_id=conv_a.id,
            audio_asset_id=asset_a.id,
        )
        # Attempt direct update to cross-tenant transcript_id bypassing service layer
        job_a.transcript_id = transcript_b.id
        with pytest.raises(ProgrammingError, match="does not belong to workspace"):
            db.commit()
        db.rollback()


def test_terminal_states_cannot_be_reopened() -> None:
    with SessionLocal() as db:
        ws, conv, asset = _create_test_workspace_and_conversation(db, duration_seconds=15.0)

        job = TranscriptionJobService.create_job(
            db=db,
            workspace_id=ws.id,
            conversation_id=conv.id,
            audio_asset_id=asset.id,
        )
        TranscriptionJobService.cancel_job(db=db, workspace_id=ws.id, job_id=job.id)
        assert job.status == "cancelled"

        # cancelled cannot transition anywhere
        for invalid_target in [
            "queued",
            "submitting",
            "submitted",
            "processing",
            "completed",
            "failed",
        ]:
            with pytest.raises(ConflictException, match="Invalid job state transition"):
                TranscriptionJobService.transition_status(
                    db=db, workspace_id=ws.id, job_id=job.id, target_status=invalid_target
                )


def test_create_job_rejects_audio_above_10mb() -> None:
    """Verify that audio assets exceeding the 10 MB limit are rejected before submitting."""
    with SessionLocal() as db:
        ws, conv, asset = _create_test_workspace_and_conversation(db, duration_seconds=120.0)
        # Update asset file size to 15 MB
        asset.file_size_bytes = 15 * 1024 * 1024
        db.commit()

        with pytest.raises(ValidationException, match="exceeds the supported limit of 10 MB"):
            TranscriptionJobService.create_job(
                db=db,
                workspace_id=ws.id,
                conversation_id=conv.id,
                audio_asset_id=asset.id,
            )


def test_cancellation_timeout_preserves_lock_and_blocks_duplicate() -> None:
    """If cancellation times out, job must remain in cancelled_unconfirmed holding the lock."""
    with SessionLocal() as db:
        ws, conv, asset = _create_test_workspace_and_conversation(db, duration_seconds=60.0)

        # 1. Create job and transition to submitted
        job = TranscriptionJobService.create_job(
            db=db,
            workspace_id=ws.id,
            conversation_id=conv.id,
            audio_asset_id=asset.id,
        )
        TranscriptionJobService.transition_status(
            db=db, workspace_id=ws.id, job_id=job.id, target_status="submitting"
        )
        TranscriptionJobService.record_submission(
            db=db, workspace_id=ws.id, job_id=job.id, external_job_id=f"batch-{uuid.uuid4()}"
        )

        # 2. Local cancellation without remote confirmation (e.g. timeout)
        # moves to cancelled_unconfirmed
        unconfirmed_job = TranscriptionJobService.cancel_job(
            db=db,
            workspace_id=ws.id,
            job_id=job.id,
            remote_confirmed=False,
        )
        assert unconfirmed_job.status == "cancelled_unconfirmed"

        # 3. Audio asset lock MUST still be held! Attempting a new job raises ConflictException
        with pytest.raises(ConflictException, match="An active transcription job already exists"):
            TranscriptionJobService.create_job(
                db=db,
                workspace_id=ws.id,
                conversation_id=conv.id,
                audio_asset_id=asset.id,
            )

        # 4. Also verify record_cancellation_ambiguous helper preserves the lock directly
        ws2, conv2, asset2 = _create_test_workspace_and_conversation(db, duration_seconds=60.0)
        job2 = TranscriptionJobService.create_job(
            db=db,
            workspace_id=ws2.id,
            conversation_id=conv2.id,
            audio_asset_id=asset2.id,
        )
        TranscriptionJobService.transition_status(
            db=db, workspace_id=ws2.id, job_id=job2.id, target_status="submitting"
        )
        TranscriptionJobService.record_submission(
            db=db, workspace_id=ws2.id, job_id=job2.id, external_job_id=f"batch-{uuid.uuid4()}"
        )
        TranscriptionJobService.record_cancellation_ambiguous(
            db=db,
            workspace_id=ws2.id,
            job_id=job2.id,
            error_message="Gateway timeout waiting for cancel confirmation",
        )
        assert job2.status == "cancelled_unconfirmed"
        assert job2.error_code == "CANCELLATION_TIMEOUT"

        with pytest.raises(ConflictException, match="An active transcription job already exists"):
            TranscriptionJobService.create_job(
                db=db,
                workspace_id=ws2.id,
                conversation_id=conv2.id,
                audio_asset_id=asset2.id,
            )

        # 5. When remote cancellation is finally confirmed, resolve to terminal cancelled
        reconciled_job = TranscriptionJobService.resolve_ambiguous_submission(
            db=db,
            workspace_id=ws.id,
            job_id=job.id,
            resolution="confirm_cancelled",
        )
        assert reconciled_job.status == "cancelled"

        # 6. Now that the job is definitively cancelled, the audio asset lock is released!
        new_job = TranscriptionJobService.create_job(
            db=db,
            workspace_id=ws.id,
            conversation_id=conv.id,
            audio_asset_id=asset.id,
        )
        assert new_job.id is not None
        assert new_job.status == "queued"


def test_confirmed_remote_cancellation_releases_lock() -> None:
    """When remote cancellation is confirmed (HTTP 200/409), job transitions to cancelled."""
    with SessionLocal() as db:
        ws, conv, asset = _create_test_workspace_and_conversation(db, duration_seconds=45.0)

        job = TranscriptionJobService.create_job(
            db=db,
            workspace_id=ws.id,
            conversation_id=conv.id,
            audio_asset_id=asset.id,
        )
        TranscriptionJobService.transition_status(
            db=db, workspace_id=ws.id, job_id=job.id, target_status="submitting"
        )
        TranscriptionJobService.record_submission(
            db=db, workspace_id=ws.id, job_id=job.id, external_job_id=f"batch-{uuid.uuid4()}"
        )

        # Confirmed cancellation
        cancelled_job = TranscriptionJobService.cancel_job(
            db=db,
            workspace_id=ws.id,
            job_id=job.id,
            remote_confirmed=True,
        )
        assert cancelled_job.status == "cancelled"

        # Lock is released: new job can be queued
        job2 = TranscriptionJobService.create_job(
            db=db,
            workspace_id=ws.id,
            conversation_id=conv.id,
            audio_asset_id=asset.id,
        )
        assert job2.status == "queued"


def test_persisted_errors_redact_credentials_and_signed_urls() -> None:
    """Ensure error messages with signed URLs and credentials are automatically sanitized."""
    with SessionLocal() as db:
        ws, conv, asset = _create_test_workspace_and_conversation(db, duration_seconds=15.0)

        job = TranscriptionJobService.create_job(
            db=db,
            workspace_id=ws.id,
            conversation_id=conv.id,
            audio_asset_id=asset.id,
        )

        raw_leak_msg = (
            "Error downloading from https://storage.googleapis.com/audio/bucket/sample.wav"
            "?X-Goog-Signature=abcdef123456&X-Goog-Algorithm=GOOG4-RSA-SHA256: "
            "api_key=gnani_secret_key_8888 failed with status 403"
        )

        TranscriptionJobService.record_failure(
            db=db,
            workspace_id=ws.id,
            job_id=job.id,
            error_code="DOWNLOAD_FAILED",
            error_message=raw_leak_msg,
        )

        assert "gnani_secret_key_8888" not in job.error_message
        assert "X-Goog-Signature" not in job.error_message
        assert "[REDACTED_URL]" in job.error_message
        assert "api_key=[REDACTED]" in job.error_message
