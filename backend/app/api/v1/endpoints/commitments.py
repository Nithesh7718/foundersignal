import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_current_workspace_context, get_db
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.commitment import (
    CommitmentCreate,
    CommitmentResponse,
    CommitmentUpdate,
)
from app.services.commitment_service import CommitmentService

router = APIRouter()


@router.get(
    "/workspaces/{workspace_id}/conversations/{conversation_id}/commitments",
    response_model=list[CommitmentResponse],
)
def list_conversation_commitments(
    conversation_id: uuid.UUID,
    workspace_context: Annotated[tuple[Workspace, str], Depends(get_current_workspace_context)],
    db: Annotated[Session, Depends(get_db)],
) -> list[CommitmentResponse]:
    """List all extracted and manual commitments for a conversation."""
    workspace, _role = workspace_context
    commitments = CommitmentService.list_commitments(
        db=db,
        workspace_id=workspace.id,
        conversation_id=conversation_id,
    )
    return [CommitmentResponse.model_validate(c) for c in commitments]


@router.post(
    "/workspaces/{workspace_id}/conversations/{conversation_id}/commitments",
    response_model=CommitmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_commitment(
    conversation_id: uuid.UUID,
    commitment_in: CommitmentCreate,
    workspace_context: Annotated[tuple[Workspace, str], Depends(get_current_workspace_context)],
    db: Annotated[Session, Depends(get_db)],
) -> CommitmentResponse:
    """Manually add a verified commitment with source quotation."""
    workspace, role = workspace_context
    commitment = CommitmentService.create_commitment(
        db=db,
        workspace_id=workspace.id,
        conversation_id=conversation_id,
        commitment_in=commitment_in,
        role=role,
    )
    return CommitmentResponse.model_validate(commitment)


@router.post(
    "/workspaces/{workspace_id}/conversations/{conversation_id}/commitments/extract",
    response_model=list[CommitmentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def extract_commitments_from_transcript(
    conversation_id: uuid.UUID,
    workspace_context: Annotated[tuple[Workspace, str], Depends(get_current_workspace_context)],
    db: Annotated[Session, Depends(get_db)],
) -> list[CommitmentResponse]:
    """Trigger AI structured extraction of commitments from the conversation's transcript."""
    workspace, role = workspace_context
    commitments = await CommitmentService.extract_commitments_from_transcript(
        db=db,
        workspace_id=workspace.id,
        conversation_id=conversation_id,
        role=role,
    )
    return [CommitmentResponse.model_validate(c) for c in commitments]


@router.patch(
    "/workspaces/{workspace_id}/commitments/{commitment_id}",
    response_model=CommitmentResponse,
)
def update_commitment(
    commitment_id: uuid.UUID,
    update_in: CommitmentUpdate,
    workspace_context: Annotated[tuple[Workspace, str], Depends(get_current_workspace_context)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CommitmentResponse:
    """Update a commitment's status (confirm, reject, complete) or details with role validation."""
    workspace, role = workspace_context
    commitment = CommitmentService.update_commitment(
        db=db,
        workspace_id=workspace.id,
        commitment_id=commitment_id,
        update_in=update_in,
        user_id=current_user.id,
        role=role,
    )
    return CommitmentResponse.model_validate(commitment)


@router.delete(
    "/workspaces/{workspace_id}/commitments/{commitment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_commitment(
    commitment_id: uuid.UUID,
    workspace_context: Annotated[tuple[Workspace, str], Depends(get_current_workspace_context)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Delete a commitment. Only workspace owners and admins are authorized."""
    workspace, role = workspace_context
    CommitmentService.delete_commitment(
        db=db,
        workspace_id=workspace.id,
        commitment_id=commitment_id,
        role=role,
    )
