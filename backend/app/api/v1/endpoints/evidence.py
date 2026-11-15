from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_workspace_context, get_db
from app.models.workspace import Workspace
from app.schemas.evidence import EvidenceGraphResponse
from app.services.evidence_service import EvidenceService

router = APIRouter()


@router.get(
    "/workspaces/{workspace_id}/evidence/graph",
    response_model=EvidenceGraphResponse,
)
def get_evidence_graph(
    workspace_context: Annotated[tuple[Workspace, str], Depends(get_current_workspace_context)],
    db: Annotated[Session, Depends(get_db)],
) -> EvidenceGraphResponse:
    """Retrieve connected evidence graph nodes and edges for the workspace."""
    workspace, _role = workspace_context
    return EvidenceService.get_evidence_graph(
        db=db,
        workspace_id=workspace.id,
    )
