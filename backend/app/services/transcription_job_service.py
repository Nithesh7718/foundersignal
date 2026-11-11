import re
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.audio_asset import AudioAsset
from app.models.conversation import Conversation
from app.models.transcript import Transcript
from app.models.transcription_job import TranscriptionJob

# Valid lifecycle state transitions
VALID_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"submitting", "failed", "cancelled"},
    "submitting": {"submitted", "submission_unknown", "completed", "failed"},
    "submission_unknown": {"submitted", "cancelled_unconfirmed", "failed"},
    "cancelled_unconfirmed": {"submitted", "failed", "cancelled", "cancelled_unconfirmed"},
    "submitted": {"processing", "failed", "cancelled", "cancelled_unconfirmed"},
    "processing": {"completed", "failed", "cancelled", "cancelled_unconfirmed"},
    "completed": set(),  # Terminal state
    "failed": set(),  # Terminal state
    "cancelled": set(),  # Terminal state
}

ACTIVE_STATUSES: set[str] = {
    "queued",
    "submitting",
    "submitted",
    "submission_unknown",
    "cancelled_unconfirmed",
    "processing",
}


def sanitize_error_message(raw_msg: str | None) -> str | None:
    """Sanitize provider error messages to prevent credential, token, or signed-URL leakage."""
    if not raw_msg:
        return None

    # Strip query parameters from URLs (e.g. ?X-Amz-Signature=..., ?key=..., ?token=...)
    sanitized = re.sub(r"https?://[^\s\?]+(\?[^\s]*)?", r"[REDACTED_URL]", raw_msg)

    # Redact common key/secret patterns
    sanitized = re.sub(
        r"(?i)(api[_-]?key|secret|token|password)[\s:=]+([^\s,;]+)", r"\1=[REDACTED]", sanitized
    )

    # Truncate to maximum 500 characters to prevent log/DB bloat
    if len(sanitized) > 500:
        sanitized = sanitized[:497] + "..."

    return sanitized


class TranscriptionJobService:
    @staticmethod
    def create_job(
        db: Session,
        workspace_id: uuid.UUID,
        conversation_id: uuid.UUID,
        audio_asset_id: uuid.UUID,
        language_code: str = "indic-auto",
        provider: str = "gnani_prisma",
        model: str = "prisma-v3.0",
    ) -> TranscriptionJob:
        """Create a durable transcription job scoped to workspace and asset.

        Enforces duplicate active job prevention and duration routing rules.
        """
        # 1. Multi-tenant validation: Conversation must belong to the workspace
        conv = db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.workspace_id == workspace_id,
            )
        ).scalar_one_or_none()

        if not conv:
            raise NotFoundException("Conversation", conversation_id)

        # 2. Multi-tenant validation: Audio asset must belong to the workspace AND conversation
        asset = db.execute(
            select(AudioAsset).where(
                AudioAsset.id == audio_asset_id,
                AudioAsset.workspace_id == workspace_id,
                AudioAsset.conversation_id == conversation_id,
            )
        ).scalar_one_or_none()

        if not asset:
            raise NotFoundException("AudioAsset", audio_asset_id)

        # 3. Check for existing active job for this audio asset
        existing_active = db.execute(
            select(TranscriptionJob).where(
                TranscriptionJob.audio_asset_id == audio_asset_id,
                TranscriptionJob.status.in_(ACTIVE_STATUSES),
            )
        ).scalar_one_or_none()

        if existing_active:
            raise ConflictException(
                "An active transcription job already exists for this audio asset.",
                details={
                    "existing_job_id": str(existing_active.id),
                    "status": existing_active.status,
                },
            )

        # 4. Strict provider direct batch limit validation (10 MB):
        # Reject audio files exceeding 10 MB before submitting to provider, ensuring
        # large files cannot create unprocessable jobs without clear user-facing error.
        if asset.file_size_bytes and asset.file_size_bytes > 10 * 1024 * 1024:
            raise ValidationException(
                f"Audio asset '{asset.file_name}' ({asset.file_size_bytes / (1024 * 1024):.1f} MB) "
                "exceeds the supported limit of 10 MB for direct batch transcription. "
                "Please upload a recording under 10 MB or split the file."
            )

        # 5. Strict duration routing:
        # Only use REST when the duration is reliably known to be at most 30 seconds.
        # Use Batch for longer or uncertain-duration (None) recordings.
        if asset.duration_seconds is not None and asset.duration_seconds <= 30.0:
            job_type = "rest"
        else:
            job_type = "batch"

        job = TranscriptionJob(
            workspace_id=workspace_id,
            conversation_id=conversation_id,
            audio_asset_id=audio_asset_id,
            provider=provider,
            model=model,
            job_type=job_type,
            status="queued",
            language_code=language_code,
            attempt_count=0,
            progress_percent=0,
        )

        try:
            db.add(job)
            db.commit()
            db.refresh(job)
            return job
        except IntegrityError as exc:
            db.rollback()
            raise ConflictException(
                "Concurrent submission prevented: an active transcription job already exists "
                "for this audio asset."
            ) from exc

    @staticmethod
    def get_job(
        db: Session,
        workspace_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> TranscriptionJob:
        """Retrieve a transcription job ensuring workspace isolation."""
        job = db.execute(
            select(TranscriptionJob).where(
                TranscriptionJob.id == job_id,
                TranscriptionJob.workspace_id == workspace_id,
            )
        ).scalar_one_or_none()

        if not job:
            raise NotFoundException("TranscriptionJob", job_id)
        return job

    @staticmethod
    def list_jobs_for_conversation(
        db: Session,
        workspace_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> list[TranscriptionJob]:
        """List all transcription jobs for a conversation scoped to workspace."""
        return list(
            db.execute(
                select(TranscriptionJob)
                .where(
                    TranscriptionJob.workspace_id == workspace_id,
                    TranscriptionJob.conversation_id == conversation_id,
                )
                .order_by(TranscriptionJob.created_at.desc())
            )
            .scalars()
            .all()
        )

    @staticmethod
    def transition_status(
        db: Session,
        workspace_id: uuid.UUID,
        job_id: uuid.UUID,
        target_status: str,
        *,
        external_job_id: str | None = None,
        transcript_id: uuid.UUID | None = None,
        progress_percent: int | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        next_poll_seconds: int | None = None,
    ) -> TranscriptionJob:
        """Validate and apply a state transition with lifecycle timestamps and safety invariants."""
        job = TranscriptionJobService.get_job(db, workspace_id, job_id)
        current_status = job.status

        # Enforce state transition rules
        allowed = VALID_TRANSITIONS.get(current_status, set())
        if target_status not in allowed:
            raise ConflictException(
                f"Invalid job state transition from '{current_status}' to '{target_status}'."
            )

        now = datetime.now(UTC)

        if target_status == "submitting":
            job.attempt_count += 1
            if not job.started_at:
                job.started_at = now

        elif target_status == "submitted":
            if external_job_id:
                job.external_job_id = external_job_id
            if next_poll_seconds:
                job.next_poll_at = now + timedelta(seconds=next_poll_seconds)

        elif target_status == "submission_unknown":
            job.error_code = error_code or "SUBMISSION_UNKNOWN"
            job.error_message = sanitize_error_message(error_message)
            job.next_poll_at = None

        elif target_status == "cancelled_unconfirmed":
            job.error_code = error_code or "CANCELLED_UNCONFIRMED"
            job.error_message = sanitize_error_message(
                error_message
                or "Local cancellation requested; remote submission remains unconfirmed."
            )
            job.next_poll_at = None

        elif target_status == "processing":
            if progress_percent is not None:
                job.progress_percent = progress_percent
            job.last_polled_at = now
            if next_poll_seconds:
                job.next_poll_at = now + timedelta(seconds=next_poll_seconds)

        elif target_status == "completed":
            # Invariant: Job cannot be marked completed without an existing persisted Transcript
            if not transcript_id and not job.transcript_id:
                raise ValidationException(
                    "A transcription job cannot be marked completed without a persisted "
                    "Transcript record."
                )

            target_tid = transcript_id or job.transcript_id
            transcript_record = db.execute(
                select(Transcript).where(
                    Transcript.id == target_tid,
                    Transcript.workspace_id == workspace_id,
                    Transcript.conversation_id == job.conversation_id,
                )
            ).scalar_one_or_none()

            if not transcript_record:
                raise ValidationException(
                    f"Transcript with id '{target_tid}' was not found in this "
                    "workspace/conversation."
                )

            job.transcript_id = transcript_record.id
            job.progress_percent = 100
            job.completed_at = now
            job.next_poll_at = None

        elif target_status == "failed":
            job.error_code = error_code or "TRANSCRIPTION_FAILED"
            job.error_message = sanitize_error_message(error_message)
            job.completed_at = now
            job.next_poll_at = None

        elif target_status == "cancelled":
            job.completed_at = now
            job.next_poll_at = None

        job.status = target_status
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def record_submission(
        db: Session,
        workspace_id: uuid.UUID,
        job_id: uuid.UUID,
        external_job_id: str,
        next_poll_seconds: int = 10,
    ) -> TranscriptionJob:
        return TranscriptionJobService.transition_status(
            db=db,
            workspace_id=workspace_id,
            job_id=job_id,
            target_status="submitted",
            external_job_id=external_job_id,
            next_poll_seconds=next_poll_seconds,
        )

    @staticmethod
    def record_completion(
        db: Session,
        workspace_id: uuid.UUID,
        job_id: uuid.UUID,
        transcript_id: uuid.UUID,
    ) -> TranscriptionJob:
        return TranscriptionJobService.transition_status(
            db=db,
            workspace_id=workspace_id,
            job_id=job_id,
            target_status="completed",
            transcript_id=transcript_id,
        )

    @staticmethod
    def record_failure(
        db: Session,
        workspace_id: uuid.UUID,
        job_id: uuid.UUID,
        error_code: str,
        error_message: str,
    ) -> TranscriptionJob:
        return TranscriptionJobService.transition_status(
            db=db,
            workspace_id=workspace_id,
            job_id=job_id,
            target_status="failed",
            error_code=error_code,
            error_message=error_message,
        )

    @staticmethod
    def cancel_job(
        db: Session,
        workspace_id: uuid.UUID,
        job_id: uuid.UUID,
        *,
        remote_confirmed: bool = False,
    ) -> TranscriptionJob:
        """Cancel a transcription job.

        Rules:
        - If 'queued' (never sent to external provider): safely cancels directly to 'cancelled'.
        - If 'submitted' or 'processing': requires remote confirmation (remote_confirmed=True).
          Without remote confirmation, moves to 'cancelled_unconfirmed' to preserve the active
          asset lock so duplicate submissions cannot occur while remote status is unknown.
        - If 'submission_unknown' or 'cancelled_unconfirmed': preserves 'cancelled_unconfirmed'
          and active asset lock until explicit reconciliation.
        """
        job = TranscriptionJobService.get_job(db, workspace_id, job_id)
        if job.status == "queued":
            return TranscriptionJobService.transition_status(
                db=db,
                workspace_id=workspace_id,
                job_id=job_id,
                target_status="cancelled",
            )

        if job.status in ("submitted", "processing"):
            if not remote_confirmed:
                return TranscriptionJobService.transition_status(
                    db=db,
                    workspace_id=workspace_id,
                    job_id=job_id,
                    target_status="cancelled_unconfirmed",
                    error_message="Cancellation requested; awaiting remote provider confirmation.",
                )
            return TranscriptionJobService.transition_status(
                db=db,
                workspace_id=workspace_id,
                job_id=job_id,
                target_status="cancelled",
            )

        if job.status in ("submission_unknown", "cancelled_unconfirmed"):
            if job.status == "cancelled_unconfirmed":
                return job
            return TranscriptionJobService.transition_status(
                db=db,
                workspace_id=workspace_id,
                job_id=job_id,
                target_status="cancelled_unconfirmed",
                error_message="Local cancellation requested; remote submission unconfirmed.",
            )

        raise ConflictException(f"Cannot cancel job in terminal status '{job.status}'.")

    @staticmethod
    def record_cancellation_ambiguous(
        db: Session,
        workspace_id: uuid.UUID,
        job_id: uuid.UUID,
        error_message: str = "Cancellation request timed out. Remote job status unconfirmed.",
    ) -> TranscriptionJob:
        """Record cancellation timeout while preserving the active-job asset lock."""
        return TranscriptionJobService.transition_status(
            db=db,
            workspace_id=workspace_id,
            job_id=job_id,
            target_status="cancelled_unconfirmed",
            error_code="CANCELLATION_TIMEOUT",
            error_message=error_message,
        )

    @staticmethod
    def confirm_cancellation(
        db: Session,
        workspace_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> TranscriptionJob:
        """Confirm remote cancellation was verified and release audio asset lock."""
        return TranscriptionJobService.transition_status(
            db=db,
            workspace_id=workspace_id,
            job_id=job_id,
            target_status="cancelled",
        )

    @staticmethod
    def record_submission_ambiguous(
        db: Session,
        workspace_id: uuid.UUID,
        job_id: uuid.UUID,
        error_code: str = "SUBMISSION_UNKNOWN",
        error_message: str = "Network timeout waiting for provider response. Receipt unknown.",
    ) -> TranscriptionJob:
        """Mark job in ambiguous submission state due to network drop or timeout."""
        return TranscriptionJobService.transition_status(
            db=db,
            workspace_id=workspace_id,
            job_id=job_id,
            target_status="submission_unknown",
            error_code=error_code,
            error_message=error_message,
        )

    @staticmethod
    def resolve_ambiguous_submission(
        db: Session,
        workspace_id: uuid.UUID,
        job_id: uuid.UUID,
        resolution: str,
        *,
        external_job_id: str | None = None,
        reason: str | None = None,
    ) -> TranscriptionJob:
        """Controlled manual/admin recovery for ambiguous submissions.

        Resolutions:
        - 'attach_external_id': Attaches discovered provider job ID, transitions to 'submitted'.
        - 'confirm_absent' (or 'mark_failed'): Confirms provider never accepted or processed
          the request. Transitions to 'failed' and releases active-job asset lock.
        - 'cancel': Stops local tracking of ambiguous job. Transitions to 'cancelled_unconfirmed'
          and PRESERVES the active-job asset lock to prevent duplicate remote submissions.
        - 'confirm_cancelled': Confirms remote job was definitively cancelled by provider.
          Transitions to 'cancelled' and safely releases active-job asset lock.
        """
        job = TranscriptionJobService.get_job(db, workspace_id, job_id)
        if job.status not in ("submission_unknown", "cancelled_unconfirmed"):
            raise ConflictException(
                f"Job is in status '{job.status}'. Manual reconciliation is only allowed for "
                "'submission_unknown' or 'cancelled_unconfirmed' jobs."
            )

        if resolution == "attach_external_id":
            if not external_job_id or not external_job_id.strip():
                raise ValidationException(
                    "Resolution 'attach_external_id' requires a valid external_job_id."
                )
            return TranscriptionJobService.transition_status(
                db=db,
                workspace_id=workspace_id,
                job_id=job_id,
                target_status="submitted",
                external_job_id=external_job_id.strip(),
                next_poll_seconds=10,
            )
        elif resolution in ("confirm_absent", "mark_failed"):
            return TranscriptionJobService.transition_status(
                db=db,
                workspace_id=workspace_id,
                job_id=job_id,
                target_status="failed",
                error_code="SUBMISSION_CONFIRMED_ABSENT",
                error_message=reason
                or "Reconciliation confirmed provider never received or processed this job.",
            )
        elif resolution == "cancel":
            if job.status == "cancelled_unconfirmed":
                return job
            return TranscriptionJobService.transition_status(
                db=db,
                workspace_id=workspace_id,
                job_id=job_id,
                target_status="cancelled_unconfirmed",
                error_message=reason
                or "Local tracking stopped; remote provider status remains unconfirmed.",
            )
        elif resolution in ("confirm_cancelled",):
            return TranscriptionJobService.transition_status(
                db=db,
                workspace_id=workspace_id,
                job_id=job_id,
                target_status="cancelled",
            )
        else:
            raise ValidationException(
                f"Unsupported resolution '{resolution}'. "
                "Must be 'attach_external_id', 'confirm_absent' ('mark_failed'), 'cancel', "
                "or 'confirm_cancelled'."
            )
