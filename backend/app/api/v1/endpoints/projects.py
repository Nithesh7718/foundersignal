import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_workspace_context, get_db
from app.models.workspace import Workspace
from app.schemas.project import (
    ProjectCreate,
    ProjectDeliverySummary,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.project_service import ProjectService

router = APIRouter()


@router.get(
    "/workspaces/{workspace_id}/projects",
    response_model=list[ProjectResponse],
)
def list_projects(
    workspace_context: Annotated[tuple[Workspace, str], Depends(get_current_workspace_context)],
    db: Annotated[Session, Depends(get_db)],
    status: str | None = Query(None, description="Optional filter by status"),
) -> list[ProjectResponse]:
    """List all projects in the workspace with delivery stats."""
    workspace, _role = workspace_context
    projects = ProjectService.list_projects(
        db=db,
        workspace_id=workspace.id,
        status=status,
    )
    return [ProjectResponse.model_validate(p) for p in projects]


@router.post(
    "/workspaces/{workspace_id}/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    project_in: ProjectCreate,
    workspace_context: Annotated[tuple[Workspace, str], Depends(get_current_workspace_context)],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectResponse:
    """Create a new project in the workspace."""
    workspace, role = workspace_context
    project = ProjectService.create_project(
        db=db,
        workspace_id=workspace.id,
        project_in=project_in,
        role=role,
    )
    return ProjectResponse.model_validate(project)


@router.get(
    "/workspaces/{workspace_id}/projects/delivery/summary",
    response_model=ProjectDeliverySummary,
)
def get_delivery_summary(
    workspace_context: Annotated[tuple[Workspace, str], Depends(get_current_workspace_context)],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectDeliverySummary:
    """Get aggregated delivery and progress statistics for the workspace."""
    workspace, _role = workspace_context
    return ProjectService.get_delivery_summary(
        db=db,
        workspace_id=workspace.id,
    )


@router.get(
    "/workspaces/{workspace_id}/projects/{project_id}",
    response_model=ProjectResponse,
)
def get_project(
    project_id: uuid.UUID,
    workspace_context: Annotated[tuple[Workspace, str], Depends(get_current_workspace_context)],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectResponse:
    """Get details for a single project."""
    workspace, _role = workspace_context
    project = ProjectService.get_project(
        db=db,
        workspace_id=workspace.id,
        project_id=project_id,
    )
    return ProjectResponse.model_validate(project)


@router.patch(
    "/workspaces/{workspace_id}/projects/{project_id}",
    response_model=ProjectResponse,
)
def update_project(
    project_id: uuid.UUID,
    update_in: ProjectUpdate,
    workspace_context: Annotated[tuple[Workspace, str], Depends(get_current_workspace_context)],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectResponse:
    """Update project metadata or delivery status."""
    workspace, role = workspace_context
    project = ProjectService.update_project(
        db=db,
        workspace_id=workspace.id,
        project_id=project_id,
        update_in=update_in,
        role=role,
    )
    return ProjectResponse.model_validate(project)


@router.delete(
    "/workspaces/{workspace_id}/projects/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_project(
    project_id: uuid.UUID,
    workspace_context: Annotated[tuple[Workspace, str], Depends(get_current_workspace_context)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Delete a project (owner or admin only)."""
    workspace, role = workspace_context
    ProjectService.delete_project(
        db=db,
        workspace_id=workspace.id,
        project_id=project_id,
        role=role,
    )
