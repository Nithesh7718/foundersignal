import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.workspace import WorkspaceCreate, WorkspaceResponse
from app.services.workspace_service import WorkspaceService

router = APIRouter()


@router.get("", response_model=list[WorkspaceResponse])
def list_workspaces(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[WorkspaceResponse]:
    """List all workspaces that the current user belongs to."""
    workspaces_with_role = WorkspaceService.get_user_workspaces(db, current_user.id)
    return [
        WorkspaceResponse(
            id=ws.id,
            name=ws.name,
            slug=ws.slug,
            owner_id=ws.owner_id,
            role=role,
            created_at=ws.created_at,
        )
        for ws, role in workspaces_with_role
    ]


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
def create_workspace(
    ws_in: WorkspaceCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> WorkspaceResponse:
    """Create a new workspace and assign the current user as owner."""
    ws = WorkspaceService.create_workspace(db, current_user.id, ws_in)
    return WorkspaceResponse(
        id=ws.id,
        name=ws.name,
        slug=ws.slug,
        owner_id=ws.owner_id,
        role="owner",
        created_at=ws.created_at,
    )


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
def get_workspace(
    workspace_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> WorkspaceResponse:
    """Get details for a workspace if user is a member."""
    ws, role = WorkspaceService.get_workspace_for_user(db, workspace_id, current_user.id)
    return WorkspaceResponse(
        id=ws.id,
        name=ws.name,
        slug=ws.slug,
        owner_id=ws.owner_id,
        role=role,
        created_at=ws.created_at,
    )
