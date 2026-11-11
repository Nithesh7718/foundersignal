"""Standalone background worker for asynchronous transcription processing and polling.

Coordination: PostgreSQL FOR UPDATE SKIP LOCKED.
No Redis, Celery, or RabbitMQ required.
"""

import argparse
import asyncio
import logging
import os
import signal
import uuid
from collections.abc import Callable
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal, check_db_connection
from app.core.exceptions import ConflictException, ExternalProviderException
from app.core.storage.base import StorageAdapter
from app.core.storage.local import LocalStorageAdapter
from app.models.audio_asset import AudioAsset
from app.models.transcription_job import TranscriptionJob
from app.providers.stt.base import STTProvider, get_stt_provider
from app.services.transcription_job_service import TranscriptionJobService

logger = logging.getLogger(__name__)


class TranscriptionWorker:
    """PostgreSQL-coordinated background worker for speech-to-text processing."""

    def __init__(
        self,
        worker_id: str | None = None,
        session_factory: Callable[[], Session] | None = None,
        provider: STTProvider | None = None,
        storage: StorageAdapter | None = None,
        poll_interval: float | None = None,
        batch_poll_interval: int | None = None,
        batch_size: int | None = None,
        lease_duration: int | None = None,
        max_retries: int | None = None,
        max_backoff: int | None = None,
    ) -> None:
        self.worker_id = worker_id or f"worker-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self._session_factory = session_factory or SessionLocal
        self._provider = provider
        self._storage = storage or LocalStorageAdapter()
        self.poll_interval = (
            poll_interval if poll_interval is not None else settings.WORKER_POLL_INTERVAL_SECONDS
        )
        self.batch_poll_interval = (
            batch_poll_interval
            if batch_poll_interval is not None
            else settings.BATCH_STATUS_POLL_INTERVAL_SECONDS
        )
        self.batch_size = batch_size if batch_size is not None else settings.WORKER_BATCH_SIZE
        self.lease_duration = (
            lease_duration if lease_duration is not None else settings.WORKER_LEASE_DURATION_SECONDS
        )
        self.max_retries = max_retries if max_retries is not None else settings.MAX_JOB_RETRIES
        self.max_backoff = max_backoff if max_backoff is not None else settings.MAX_BACKOFF_SECONDS
        self._shutdown = False

    @property
    def provider(self) -> STTProvider:
        if self._provider is None:
            self._provider = get_stt_provider()
        return self._provider

    @property
    def storage(self) -> StorageAdapter:
        return self._storage

    def trigger_shutdown(self, signum: int | None = None, frame: Any = None) -> None:
        """Signal handler to initiate graceful shutdown."""
        logger.info(
            "Worker %s received termination signal. Initiating graceful shutdown...",
            self.worker_id,
        )
        self._shutdown = True

    def check_health(self, db: Session) -> dict[str, Any]:
        """Check worker and database operational status."""
        db_connected = check_db_connection()
        unresolved_count = (
            db.execute(
                select(func.count(TranscriptionJob.id)).where(
                    TranscriptionJob.status.in_(["submission_unknown", "cancelled_unconfirmed"])
                )
            ).scalar_one()
            or 0
        )
        queued_count = (
            db.execute(
                select(func.count(TranscriptionJob.id)).where(TranscriptionJob.status == "queued")
            ).scalar_one()
            or 0
        )
        processing_count = (
            db.execute(
                select(func.count(TranscriptionJob.id)).where(
                    TranscriptionJob.status.in_(["submitting", "submitted", "processing"])
                )
            ).scalar_one()
            or 0
        )

        return {
            "status": "healthy" if db_connected else "degraded",
            "worker_id": self.worker_id,
            "database_connected": db_connected,
            "queued_jobs": queued_count,
            "processing_jobs": processing_count,
            "unresolved_jobs": unresolved_count,
        }

    async def run_once_async(self, db: Session | None = None) -> dict[str, Any]:
        """Execute a single processing and polling cycle."""
        owns_session = db is None
        session = self._session_factory() if owns_session else db
        assert session is not None

        try:
            # 1. Recover any expired worker leases
            recovered_stats = TranscriptionJobService.recover_expired_leases(
                session, recovery_worker_id=self.worker_id
            )

            # 2. Claim and process queued jobs
            queued_jobs = TranscriptionJobService.claim_queued_jobs(
                db=session,
                worker_id=self.worker_id,
                limit=self.batch_size,
                lease_duration_seconds=self.lease_duration,
            )

            for job in queued_jobs:
                if self._shutdown:
                    break
                await self._process_queued_job(session, job)

            # 3. Claim and poll submitted/processing jobs
            polling_jobs = TranscriptionJobService.claim_polling_jobs(
                db=session,
                worker_id=self.worker_id,
                limit=self.batch_size,
                lease_duration_seconds=self.lease_duration,
            )

            for job in polling_jobs:
                if self._shutdown:
                    break
                await self._process_polling_job(session, job)

            return {
                "recovered": recovered_stats,
                "queued_processed": len(queued_jobs),
                "polling_processed": len(polling_jobs),
            }
        finally:
            if owns_session:
                session.close()

    def run_once(self, db: Session | None = None) -> dict[str, Any]:
        """Synchronous wrapper for run_once_async."""
        return asyncio.run(self.run_once_async(db))

    async def run_async(self) -> None:
        """Run continuous worker loop until termination signal is received."""
        logger.info("Starting TranscriptionWorker %s...", self.worker_id)

        # Register signal handlers if running in main thread
        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, self.trigger_shutdown)
        except (ValueError, NotImplementedError):
            # In non-main thread or environments without signal support
            pass

        while not self._shutdown:
            try:
                cycle_result = await self.run_once_async()
                has_work = (
                    cycle_result["queued_processed"] > 0 or cycle_result["polling_processed"] > 0
                )
                if not has_work and not self._shutdown:
                    await asyncio.sleep(self.poll_interval)
            except Exception as exc:
                logger.error(
                    "Worker %s encountered unexpected loop error: %s",
                    self.worker_id,
                    exc,
                    exc_info=True,
                )
                if not self._shutdown:
                    await asyncio.sleep(self.poll_interval)

        logger.info("TranscriptionWorker %s exited cleanly.", self.worker_id)

    def run(self) -> None:
        """Entrypoint for standalone worker process."""
        asyncio.run(self.run_async())

    async def _process_queued_job(self, db: Session, job: TranscriptionJob) -> None:
        """Submit a claimed queued job to the provider."""
        logger.info(
            "Worker %s submitting queued job %s (type=%s)",
            self.worker_id,
            job.id,
            job.job_type,
        )

        try:
            # 1. Verify audio asset
            asset = db.get(AudioAsset, job.audio_asset_id)
            if not asset:
                TranscriptionJobService.record_failure(
                    db=db,
                    workspace_id=job.workspace_id,
                    job_id=job.id,
                    error_code="AUDIO_ASSET_NOT_FOUND",
                    error_message="Referenced AudioAsset record was not found.",
                    expected_worker_id=self.worker_id,
                    expected_lease_token=job.lease_token,
                )
                return

            if (
                asset.workspace_id != job.workspace_id
                or asset.conversation_id != job.conversation_id
            ):
                TranscriptionJobService.record_failure(
                    db=db,
                    workspace_id=job.workspace_id,
                    job_id=job.id,
                    error_code="ASSET_RELATIONSHIP_MISMATCH",
                    error_message="AudioAsset does not match conversation or workspace.",
                    expected_worker_id=self.worker_id,
                    expected_lease_token=job.lease_token,
                )
                return

            # 2. Strict 10 MB direct batch limit enforcement
            if asset.file_size_bytes and asset.file_size_bytes > 10 * 1024 * 1024:
                mb_size = asset.file_size_bytes / (1024 * 1024)
                TranscriptionJobService.record_failure(
                    db=db,
                    workspace_id=job.workspace_id,
                    job_id=job.id,
                    error_code="AUDIO_FILE_TOO_LARGE",
                    error_message=(
                        f"Audio file '{asset.file_name}' ({mb_size:.1f} MB) "
                        "exceeds the 10 MB limit for direct batch transcription."
                    ),
                    expected_worker_id=self.worker_id,
                    expected_lease_token=job.lease_token,
                )
                return

            # 3. Read stored audio file
            try:
                audio_bytes = await self.storage.get_file_bytes(asset.storage_path)
            except Exception as exc:
                logger.error("Failed to read audio file for job %s: %s", job.id, exc)
                TranscriptionJobService.record_failure(
                    db=db,
                    workspace_id=job.workspace_id,
                    job_id=job.id,
                    error_code="AUDIO_FILE_READ_ERROR",
                    error_message="Unable to read stored audio file from storage.",
                    expected_worker_id=self.worker_id,
                    expected_lease_token=job.lease_token,
                )
                return

            if len(audio_bytes) > 10 * 1024 * 1024:
                TranscriptionJobService.record_failure(
                    db=db,
                    workspace_id=job.workspace_id,
                    job_id=job.id,
                    error_code="AUDIO_FILE_TOO_LARGE",
                    error_message=(
                        "Audio byte stream exceeds 10 MB limit for direct batch transcription."
                    ),
                    expected_worker_id=self.worker_id,
                    expected_lease_token=job.lease_token,
                )
                return

            # 4. Transition to submitting state (retaining worker lease)
            TranscriptionJobService.transition_status(
                db=db,
                workspace_id=job.workspace_id,
                job_id=job.id,
                target_status="submitting",
                expected_worker_id=self.worker_id,
                expected_lease_token=job.lease_token,
            )

            filename = asset.file_name or "audio.wav"

            # 5. Route: REST vs Batch
            if job.job_type == "rest":
                await self._execute_rest_transcription(db, job, audio_bytes, filename)
            else:
                await self._execute_batch_submission(db, job, audio_bytes, filename)
        except ConflictException as exc:
            logger.warning(
                "Worker %s lost lease on queued job %s: %s. Aborting processing.",
                self.worker_id,
                job.id,
                exc,
            )
            return

    async def _execute_rest_transcription(
        self,
        db: Session,
        job: TranscriptionJob,
        audio_bytes: bytes,
        filename: str,
    ) -> None:
        """Execute synchronous REST STT for clips <= 30 seconds."""
        try:
            stt_result = await self.provider.transcribe_sync(
                audio_bytes=audio_bytes,
                filename=filename,
                language=job.language_code,
            )
        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as exc:
            logger.warning(
                "Network timeout during REST transcription for job %s: %s",
                job.id,
                exc,
            )
            try:
                TranscriptionJobService.record_submission_ambiguous(
                    db=db,
                    workspace_id=job.workspace_id,
                    job_id=job.id,
                    error_code="SUBMISSION_TIMEOUT",
                    error_message=f"Network timeout contacting transcription provider: {exc}",
                    expected_worker_id=self.worker_id,
                    expected_lease_token=job.lease_token,
                )
            except ConflictException as c_exc:
                logger.warning(
                    "Worker %s lost lease on job %s during REST timeout recording: %s",
                    self.worker_id,
                    job.id,
                    c_exc,
                )
            return
        except ExternalProviderException as exc:
            logger.error("Provider error in REST transcription for job %s: %s", job.id, exc)
            try:
                TranscriptionJobService.record_failure(
                    db=db,
                    workspace_id=job.workspace_id,
                    job_id=job.id,
                    error_code="PROVIDER_REST_ERROR",
                    error_message=str(exc),
                    expected_worker_id=self.worker_id,
                    expected_lease_token=job.lease_token,
                )
            except ConflictException as c_exc:
                logger.warning(
                    "Worker %s lost lease on job %s during REST error recording: %s",
                    self.worker_id,
                    job.id,
                    c_exc,
                )
            return
        except Exception as exc:
            logger.error("Unexpected error in REST transcription for job %s: %s", job.id, exc)
            try:
                TranscriptionJobService.record_failure(
                    db=db,
                    workspace_id=job.workspace_id,
                    job_id=job.id,
                    error_code="REST_PROCESSING_FAILED",
                    error_message=str(exc),
                    expected_worker_id=self.worker_id,
                    expected_lease_token=job.lease_token,
                )
            except ConflictException as c_exc:
                logger.warning(
                    "Worker %s lost lease on job %s during REST failure recording: %s",
                    self.worker_id,
                    job.id,
                    c_exc,
                )
            return

        # Save transcript idempotently and complete job under lease fencing
        try:
            transcript = TranscriptionJobService.save_transcript_idempotent(
                db=db,
                job=job,
                stt_result=stt_result,
                expected_worker_id=self.worker_id,
                expected_lease_token=job.lease_token,
            )
            TranscriptionJobService.record_completion(
                db=db,
                workspace_id=job.workspace_id,
                job_id=job.id,
                transcript_id=transcript.id,
                expected_worker_id=self.worker_id,
                expected_lease_token=job.lease_token,
            )
            logger.info(
                "REST transcription completed for job %s (transcript_id=%s)",
                job.id,
                transcript.id,
            )
        except ConflictException as exc:
            logger.warning(
                "Worker %s lost lease on job %s after REST response received: %s. "
                "Aborting completion.",
                self.worker_id,
                job.id,
                exc,
            )
            return

    async def _execute_batch_submission(
        self,
        db: Session,
        job: TranscriptionJob,
        audio_bytes: bytes,
        filename: str,
    ) -> None:
        """Submit audio to Gnani Batch STT pipeline."""
        try:
            external_job_id = await self.provider.create_batch_job(
                audio_bytes=audio_bytes,
                filename=filename,
                language=job.language_code,
            )
        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as exc:
            logger.warning(
                "Network timeout during Batch job submission for job %s: %s",
                job.id,
                exc,
            )
            try:
                TranscriptionJobService.record_submission_ambiguous(
                    db=db,
                    workspace_id=job.workspace_id,
                    job_id=job.id,
                    error_code="SUBMISSION_TIMEOUT",
                    error_message=(
                        "Network timeout waiting for provider response. Provider receipt unknown."
                    ),
                    expected_worker_id=self.worker_id,
                    expected_lease_token=job.lease_token,
                )
            except ConflictException as c_exc:
                logger.warning(
                    "Worker %s lost lease on job %s during Batch timeout recording: %s",
                    self.worker_id,
                    job.id,
                    c_exc,
                )
            return
        except ExternalProviderException as exc:
            logger.error(
                "Provider rejected Batch job submission for job %s: %s",
                job.id,
                exc,
            )
            try:
                TranscriptionJobService.record_failure(
                    db=db,
                    workspace_id=job.workspace_id,
                    job_id=job.id,
                    error_code="PROVIDER_SUBMISSION_REJECTED",
                    error_message=str(exc),
                    expected_worker_id=self.worker_id,
                    expected_lease_token=job.lease_token,
                )
            except ConflictException as c_exc:
                logger.warning(
                    "Worker %s lost lease on job %s during Batch rejection recording: %s",
                    self.worker_id,
                    job.id,
                    c_exc,
                )
            return
        except Exception as exc:
            logger.error("Unexpected error submitting Batch job %s: %s", job.id, exc)
            try:
                TranscriptionJobService.record_failure(
                    db=db,
                    workspace_id=job.workspace_id,
                    job_id=job.id,
                    error_code="SUBMISSION_ERROR",
                    error_message=str(exc),
                    expected_worker_id=self.worker_id,
                    expected_lease_token=job.lease_token,
                )
            except ConflictException as c_exc:
                logger.warning(
                    "Worker %s lost lease on job %s during Batch error recording: %s",
                    self.worker_id,
                    job.id,
                    c_exc,
                )
            return

        # Start batch processing if required by provider contract
        try:
            await self.provider.start_batch_job(external_job_id)
        except Exception as exc:
            logger.warning(
                "Failed to call start on batch job %s (%s): %s",
                job.id,
                external_job_id,
                exc,
            )

        # Transition to submitted and schedule first poll under lease fencing
        try:
            TranscriptionJobService.record_submission(
                db=db,
                workspace_id=job.workspace_id,
                job_id=job.id,
                external_job_id=external_job_id,
                next_poll_seconds=self.batch_poll_interval,
                expected_worker_id=self.worker_id,
                expected_lease_token=job.lease_token,
            )
            logger.info(
                "Batch job %s successfully submitted with external_id=%s",
                job.id,
                external_job_id,
            )
        except ConflictException as exc:
            logger.warning(
                "Worker %s lost lease on job %s after batch submission: %s. Aborting state update.",
                self.worker_id,
                job.id,
                exc,
            )
            return

    async def _process_polling_job(self, db: Session, job: TranscriptionJob) -> None:
        """Poll status for an in-flight Batch job."""
        if not job.external_job_id:
            try:
                TranscriptionJobService.record_failure(
                    db=db,
                    workspace_id=job.workspace_id,
                    job_id=job.id,
                    error_code="MISSING_EXTERNAL_JOB_ID",
                    error_message="Submitted job lacks external provider job ID.",
                    expected_worker_id=self.worker_id,
                    expected_lease_token=job.lease_token,
                )
            except ConflictException as exc:
                logger.warning(
                    "Worker %s lost lease on job %s: %s",
                    self.worker_id,
                    job.id,
                    exc,
                )
            return

        logger.debug(
            "Polling provider status for job %s (external_id=%s)",
            job.id,
            job.external_job_id,
        )

        try:
            batch_status = await self.provider.get_batch_job_status(job.external_job_id)
        except ExternalProviderException as exc:
            self._handle_polling_transient_error(db, job, str(exc))
            return
        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as exc:
            self._handle_polling_transient_error(db, job, f"Network timeout during poll: {exc}")
            return
        except Exception as exc:
            self._handle_polling_transient_error(db, job, f"Unexpected polling error: {exc}")
            return

        st = batch_status.status.upper()

        try:
            if st in ("CREATED", "STARTING", "QUEUED", "IN_PROGRESS"):
                TranscriptionJobService.transition_status(
                    db=db,
                    workspace_id=job.workspace_id,
                    job_id=job.id,
                    target_status="processing",
                    progress_percent=batch_status.percent,
                    next_poll_seconds=self.batch_poll_interval,
                    expected_worker_id=self.worker_id,
                    expected_lease_token=job.lease_token,
                )

            elif st == "COMPLETED":
                await self._complete_batch_job(db, job)

            elif st == "FAILED":
                TranscriptionJobService.record_failure(
                    db=db,
                    workspace_id=job.workspace_id,
                    job_id=job.id,
                    error_code="PROVIDER_JOB_FAILED",
                    error_message=batch_status.error_message
                    or "Provider batch job reported failure.",
                    expected_worker_id=self.worker_id,
                    expected_lease_token=job.lease_token,
                )

            elif st == "CANCELLED":
                TranscriptionJobService.confirm_cancellation(
                    db=db,
                    workspace_id=job.workspace_id,
                    job_id=job.id,
                    expected_worker_id=self.worker_id,
                    expected_lease_token=job.lease_token,
                )

            else:
                logger.warning("Unrecognized provider status '%s' for job %s", st, job.id)
                TranscriptionJobService.transition_status(
                    db=db,
                    workspace_id=job.workspace_id,
                    job_id=job.id,
                    target_status="processing",
                    progress_percent=batch_status.percent,
                    next_poll_seconds=self.batch_poll_interval,
                    expected_worker_id=self.worker_id,
                    expected_lease_token=job.lease_token,
                )
        except ConflictException as exc:
            logger.warning(
                "Worker %s lost lease on polling job %s: %s. Aborting state update.",
                self.worker_id,
                job.id,
                exc,
            )
            return

    async def _complete_batch_job(self, db: Session, job: TranscriptionJob) -> None:
        """Fetch transcript and record job completion."""
        assert job.external_job_id is not None
        try:
            stt_result = await self.provider.fetch_batch_transcript(job.external_job_id)
        except Exception as exc:
            logger.error(
                "Failed to fetch completed batch transcript for job %s: %s",
                job.id,
                exc,
            )
            self._handle_polling_transient_error(
                db, job, f"Failed to retrieve completed transcript: {exc}"
            )
            return

        try:
            transcript = TranscriptionJobService.save_transcript_idempotent(
                db=db,
                job=job,
                stt_result=stt_result,
                expected_worker_id=self.worker_id,
                expected_lease_token=job.lease_token,
            )
            TranscriptionJobService.record_completion(
                db=db,
                workspace_id=job.workspace_id,
                job_id=job.id,
                transcript_id=transcript.id,
                expected_worker_id=self.worker_id,
                expected_lease_token=job.lease_token,
            )
            logger.info(
                "Batch job %s successfully completed (transcript_id=%s)",
                job.id,
                transcript.id,
            )
        except ConflictException as exc:
            logger.warning(
                "Worker %s lost lease on job %s during batch completion: %s. Aborting.",
                self.worker_id,
                job.id,
                exc,
            )
            return

    def _handle_polling_transient_error(
        self,
        db: Session,
        job: TranscriptionJob,
        error_msg: str,
    ) -> None:
        """Handle polling error with retry tracking and exponential backoff under lease fencing."""
        attempt_count = job.attempt_count + 1

        try:
            if attempt_count >= self.max_retries:
                logger.error(
                    "Polling max retries exceeded (%d) for job %s: %s",
                    self.max_retries,
                    job.id,
                    error_msg,
                )
                TranscriptionJobService.record_failure(
                    db=db,
                    workspace_id=job.workspace_id,
                    job_id=job.id,
                    error_code="POLLING_RETRIES_EXCEEDED",
                    error_message=f"Polling retries exceeded ({self.max_retries}): {error_msg}",
                    expected_worker_id=self.worker_id,
                    expected_lease_token=job.lease_token,
                )
                return

            # Calculate exponential backoff
            backoff_seconds = min(
                self.max_backoff,
                self.batch_poll_interval * (2 ** min(attempt_count, 6)),
            )
            TranscriptionJobService.schedule_poll_retry(
                db=db,
                workspace_id=job.workspace_id,
                job_id=job.id,
                next_poll_seconds=backoff_seconds,
                expected_worker_id=self.worker_id,
                expected_lease_token=job.lease_token,
            )

            logger.warning(
                "Polling error for job %s (attempt %d/%d). Retrying in %ds. Error: %s",
                job.id,
                attempt_count,
                self.max_retries,
                backoff_seconds,
                error_msg,
            )
        except ConflictException as exc:
            logger.warning(
                "Worker %s lost lease on job %s during transient error handling: %s",
                self.worker_id,
                job.id,
                exc,
            )
            return


def main() -> None:
    """CLI execution entrypoint for python -m app.workers.transcription_worker."""
    parser = argparse.ArgumentParser(description="FounderSignal Transcription Worker")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single processing and polling cycle then exit",
    )
    parser.add_argument(
        "--worker-id",
        type=str,
        default=None,
        help="Custom identifier for this worker instance",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=None,
        help="Idle sleep interval between polling cycles in seconds",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    worker = TranscriptionWorker(
        worker_id=args.worker_id,
        poll_interval=args.poll_interval,
    )

    if args.once:
        logger.info("Executing single pass with worker %s...", worker.worker_id)
        summary = worker.run_once()
        logger.info("Completed pass: %s", summary)
    else:
        worker.run()


if __name__ == "__main__":
    main()
