"""API endpoints for managing transcription jobs, status polling, and reconciliation."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_workspace_context,
    get_db,
)
from app.core.exceptions import ExternalProviderException, ForbiddenException
from app.models.workspace import Workspace
from app.providers.stt.base import STTProvider, get_stt_provider
from app.schemas.transcription_job import (
    TranscriptionJobCreate,
    TranscriptionJobReconcileRequest,
    TranscriptionJobResponse,
)
from app.services.transcription_job_service import TranscriptionJobService

router = APIRouter()


@router.post(
    "/workspaces/{workspace_id}/conversations/{conversation_id}/transcribe",
    response_model=TranscriptionJobResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_transcription_job(
    conversation_id: uuid.UUID,
    job_in: TranscriptionJobCreate,
    workspace_context: Annotated[tuple[Workspace, str], Depends(get_current_workspace_context)],
    db: Annotated[Session, Depends(get_db)],
) -> TranscriptionJobResponse:
    """Create a durable transcription job for an audio asset in a conversation."""
    workspace, _role = workspace_context
    job = TranscriptionJobService.create_job(
        db=db,
        workspace_id=workspace.id,
        conversation_id=conversation_id,
        audio_asset_id=job_in.audio_asset_id,
        language_code=job_in.language_code,
    )
    return TranscriptionJobResponse.model_validate(job)


@router.get(
    "/workspaces/{workspace_id}/conversations/{conversation_id}/transcription-jobs",
    response_model=list[TranscriptionJobResponse],
)
def list_conversation_transcription_jobs(
    conversation_id: uuid.UUID,
    workspace_context: Annotated[tuple[Workspace, str], Depends(get_current_workspace_context)],
    db: Annotated[Session, Depends(get_db)],
) -> list[TranscriptionJobResponse]:
    """List all transcription jobs for a conversation."""
    workspace, _role = workspace_context
    jobs = TranscriptionJobService.list_jobs_for_conversation(
        db=db,
        workspace_id=workspace.id,
        conversation_id=conversation_id,
    )
    return [TranscriptionJobResponse.model_validate(j) for j in jobs]


@router.get(
    "/workspaces/{workspace_id}/transcription-jobs/unresolved",
    response_model=list[TranscriptionJobResponse],
)
def list_unresolved_transcription_jobs(
    workspace_context: Annotated[tuple[Workspace, str], Depends(get_current_workspace_context)],
    db: Annotated[Session, Depends(get_db)],
) -> list[TranscriptionJobResponse]:
    """List unresolved jobs requiring reconciliation (unknown/unconfirmed)."""
    workspace, _role = workspace_context
    jobs = TranscriptionJobService.list_unresolved_jobs(
        db=db,
        workspace_id=workspace.id,
    )
    return [TranscriptionJobResponse.model_validate(j) for j in jobs]


@router.get(
    "/workspaces/{workspace_id}/transcription-jobs/{job_id}",
    response_model=TranscriptionJobResponse,
)
def get_transcription_job(
    job_id: uuid.UUID,
    workspace_context: Annotated[tuple[Workspace, str], Depends(get_current_workspace_context)],
    db: Annotated[Session, Depends(get_db)],
) -> TranscriptionJobResponse:
    """Get details and status of a transcription job."""
    workspace, _role = workspace_context
    job = TranscriptionJobService.get_job(
        db=db,
        workspace_id=workspace.id,
        job_id=job_id,
    )
    return TranscriptionJobResponse.model_validate(job)


@router.post(
    "/workspaces/{workspace_id}/transcription-jobs/{job_id}/cancel",
    response_model=TranscriptionJobResponse,
)
async def cancel_transcription_job(
    job_id: uuid.UUID,
    workspace_context: Annotated[tuple[Workspace, str], Depends(get_current_workspace_context)],
    db: Annotated[Session, Depends(get_db)],
) -> TranscriptionJobResponse:
    """Request cancellation of a transcription job.

    Authorization Policy:
    - Only workspace owners and admins can cancel transcription jobs. Members are rejected with 403.

    Behavior:
    - If the job has been submitted to a remote provider, remote confirmation is attempted.
    - If confirmation times out or fails, the job moves to cancelled_unconfirmed to preserve
      the active audio asset lock until reconciled.
    """
    workspace, role = workspace_context
    if role not in ("owner", "admin"):
        raise ForbiddenException("Only workspace owners and admins can cancel transcription jobs.")

    job = TranscriptionJobService.get_job(
        db=db,
        workspace_id=workspace.id,
        job_id=job_id,
    )

    if job.status in ("submitted", "processing") and job.external_job_id:
        stt_provider: STTProvider = get_stt_provider()
        try:
            confirmed = await stt_provider.cancel_batch_job(job.external_job_id)
            updated_job = TranscriptionJobService.cancel_job(
                db=db,
                workspace_id=workspace.id,
                job_id=job_id,
                remote_confirmed=confirmed,
            )
        except ExternalProviderException:
            updated_job = TranscriptionJobService.record_cancellation_ambiguous(
                db=db,
                workspace_id=workspace.id,
                job_id=job_id,
                error_message=(
                    "Remote provider cancellation failed or timed out. Status unconfirmed."
                ),
            )
    else:
        updated_job = TranscriptionJobService.cancel_job(
            db=db,
            workspace_id=workspace.id,
            job_id=job_id,
        )

    return TranscriptionJobResponse.model_validate(updated_job)


@router.post(
    "/workspaces/{workspace_id}/transcription-jobs/{job_id}/reconcile",
    response_model=TranscriptionJobResponse,
)
def reconcile_transcription_job(
    job_id: uuid.UUID,
    reconcile_in: TranscriptionJobReconcileRequest,
    workspace_context: Annotated[tuple[Workspace, str], Depends(get_current_workspace_context)],
    db: Annotated[Session, Depends(get_db)],
) -> TranscriptionJobResponse:
    """Manually reconcile an unresolved job (submission_unknown or cancelled_unconfirmed).

    Authorization Policy:
    - Only workspace owners and admins can reconcile transcription jobs.
      Members are rejected with 403.

    Supported resolutions:
    - 'attach_external_id': Attach confirmed provider job ID and resume polling.
    - 'confirm_absent': Mark job failed and release audio asset lock after confirming provider
      never received it.
    - 'cancel': Stop tracking ambiguous job while retaining audio lock to prevent duplicates.
    - 'confirm_cancelled': Confirm remote job was cancelled and safely release audio lock.
    """
    workspace, role = workspace_context
    if role not in ("owner", "admin"):
        raise ForbiddenException(
            "Only workspace owners and admins can reconcile transcription jobs."
        )

    reconciled_job = TranscriptionJobService.resolve_ambiguous_submission(
        db=db,
        workspace_id=workspace.id,
        job_id=job_id,
        resolution=reconcile_in.resolution,
        external_job_id=reconcile_in.external_job_id,
        reason=reconcile_in.reason,
    )
    return TranscriptionJobResponse.model_validate(reconciled_job)
