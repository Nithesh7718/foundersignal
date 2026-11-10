import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.models.workspace import Workspace, WorkspaceMembership
from app.schemas.workspace import WorkspaceCreate
from app.services.auth_service import slugify


class WorkspaceService:
    @staticmethod
    def create_workspace(
        db: Session,
        user_id: uuid.UUID,
        ws_in: WorkspaceCreate,
    ) -> Workspace:
        base_slug = ws_in.slug or slugify(ws_in.name)
        candidate_slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

        existing = db.execute(
            select(Workspace).where(Workspace.slug == candidate_slug)
        ).scalar_one_or_none()
        if existing:
            raise ConflictException("Workspace with this slug already exists.")

        workspace = Workspace(
            name=ws_in.name.strip(),
            slug=candidate_slug,
            owner_id=user_id,
        )
        db.add(workspace)
        db.flush()

        membership = WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=user_id,
            role="owner",
        )
        db.add(membership)
        db.commit()
        db.refresh(workspace)
        return workspace

    @staticmethod
    def get_user_workspaces(
        db: Session,
        user_id: uuid.UUID,
    ) -> list[tuple[Workspace, str]]:
        stmt = (
            select(Workspace, WorkspaceMembership.role)
            .join(WorkspaceMembership, Workspace.id == WorkspaceMembership.workspace_id)
            .where(WorkspaceMembership.user_id == user_id)
            .order_by(Workspace.created_at.desc())
        )
        results = db.execute(stmt).all()
        return [(ws, role) for ws, role in results]

    @staticmethod
    def get_workspace_for_user(
        db: Session,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> tuple[Workspace, str]:
        stmt = (
            select(Workspace, WorkspaceMembership.role)
            .join(WorkspaceMembership, Workspace.id == WorkspaceMembership.workspace_id)
            .where(
                Workspace.id == workspace_id,
                WorkspaceMembership.user_id == user_id,
            )
        )
        result = db.execute(stmt).first()
        if not result:
            # Check if workspace exists at all to return 404 vs 403
            ws_exists = db.execute(
                select(Workspace.id).where(Workspace.id == workspace_id)
            ).scalar_one_or_none()
            if not ws_exists:
                raise NotFoundException("Workspace not found.")
            raise ForbiddenException("You do not have access to this workspace.")

        return result[0], result[1]

    @staticmethod
    def verify_workspace_access(
        db: Session,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> WorkspaceMembership:
        membership = db.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == user_id,
            )
        ).scalar_one_or_none()

        if not membership:
            ws_exists = db.execute(
                select(Workspace.id).where(Workspace.id == workspace_id)
            ).scalar_one_or_none()
            if not ws_exists:
                raise NotFoundException("Workspace not found.")
            raise ForbiddenException("Access denied: You are not a member of this workspace.")

        return membership
