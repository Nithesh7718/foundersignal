import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenException, NotFoundException
from app.models.commitment import Commitment
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectDeliverySummary, ProjectUpdate


class ProjectService:
    @staticmethod
    def _project_to_dict(project: Project, commitments: Sequence[Commitment]) -> dict[str, Any]:
        now = datetime.now(UTC)
        total = len(commitments)
        completed = sum(1 for c in commitments if c.status == "completed")
        in_progress = sum(1 for c in commitments if c.status == "in_progress")
        confirmed = sum(1 for c in commitments if c.status == "confirmed")
        inferred = sum(1 for c in commitments if c.status == "inferred")
        overdue = sum(
            1
            for c in commitments
            if c.due_date and c.due_date < now and c.status not in ("completed", "rejected")
        )

        return {
            "id": project.id,
            "workspace_id": project.workspace_id,
            "name": project.name,
            "description": project.description,
            "status": project.status,
            "target_date": project.target_date,
            "created_at": project.created_at,
            "updated_at": project.updated_at,
            "total_commitments": total,
            "completed_commitments": completed,
            "in_progress_commitments": in_progress,
            "confirmed_commitments": confirmed,
            "inferred_commitments": inferred,
            "overdue_commitments": overdue,
        }

    @staticmethod
    def create_project(
        db: Session,
        workspace_id: uuid.UUID,
        project_in: ProjectCreate,
        role: str,
    ) -> dict[str, Any]:
        if role == "viewer":
            raise ForbiddenException("Viewers cannot create projects.")

        project = Project(
            workspace_id=workspace_id,
            name=project_in.name.strip(),
            description=project_in.description.strip() if project_in.description else None,
            status=project_in.status,
            target_date=project_in.target_date,
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return ProjectService._project_to_dict(project, [])

    @staticmethod
    def list_projects(
        db: Session,
        workspace_id: uuid.UUID,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        stmt = select(Project).where(Project.workspace_id == workspace_id)
        if status:
            stmt = stmt.where(Project.status == status)
        stmt = stmt.order_by(Project.created_at.desc())
        projects = db.execute(stmt).scalars().all()

        results = []
        for project in projects:
            comm_stmt = select(Commitment).where(
                Commitment.workspace_id == workspace_id,
                Commitment.project_id == project.id,
            )
            comms = db.execute(comm_stmt).scalars().all()
            results.append(ProjectService._project_to_dict(project, comms))
        return results

    @staticmethod
    def get_project(
        db: Session,
        workspace_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> dict[str, Any]:
        stmt = select(Project).where(
            Project.id == project_id,
            Project.workspace_id == workspace_id,
        )
        project = db.execute(stmt).scalar_one_or_none()
        if not project:
            raise NotFoundException("Project not found.")

        comm_stmt = select(Commitment).where(
            Commitment.workspace_id == workspace_id,
            Commitment.project_id == project.id,
        )
        comms = db.execute(comm_stmt).scalars().all()
        return ProjectService._project_to_dict(project, comms)

    @staticmethod
    def update_project(
        db: Session,
        workspace_id: uuid.UUID,
        project_id: uuid.UUID,
        update_in: ProjectUpdate,
        role: str,
    ) -> dict[str, Any]:
        if role == "viewer":
            raise ForbiddenException("Viewers cannot update projects.")

        stmt = select(Project).where(
            Project.id == project_id,
            Project.workspace_id == workspace_id,
        )
        project = db.execute(stmt).scalar_one_or_none()
        if not project:
            raise NotFoundException("Project not found.")

        if update_in.name is not None:
            project.name = update_in.name.strip()
        if update_in.description is not None:
            project.description = update_in.description.strip() if update_in.description else None
        if update_in.status is not None:
            project.status = update_in.status
        if update_in.target_date is not None:
            project.target_date = update_in.target_date

        db.commit()
        db.refresh(project)

        comm_stmt = select(Commitment).where(
            Commitment.workspace_id == workspace_id,
            Commitment.project_id == project.id,
        )
        comms = db.execute(comm_stmt).scalars().all()
        return ProjectService._project_to_dict(project, comms)

    @staticmethod
    def delete_project(
        db: Session,
        workspace_id: uuid.UUID,
        project_id: uuid.UUID,
        role: str,
    ) -> None:
        if role not in ("owner", "admin"):
            raise ForbiddenException("Only workspace owners and admins can delete projects.")

        stmt = select(Project).where(
            Project.id == project_id,
            Project.workspace_id == workspace_id,
        )
        project = db.execute(stmt).scalar_one_or_none()
        if not project:
            raise NotFoundException("Project not found.")

        db.delete(project)
        db.commit()

    @staticmethod
    def get_delivery_summary(
        db: Session,
        workspace_id: uuid.UUID,
    ) -> ProjectDeliverySummary:
        now = datetime.now(UTC)
        projects = (
            db.execute(select(Project).where(Project.workspace_id == workspace_id)).scalars().all()
        )
        commitments = (
            db.execute(select(Commitment).where(Commitment.workspace_id == workspace_id))
            .scalars()
            .all()
        )

        total_projects = len(projects)
        active_projects = sum(1 for p in projects if p.status == "active")
        completed_projects = sum(1 for p in projects if p.status == "completed")

        total_commitments = len(commitments)
        completed_commitments = sum(1 for c in commitments if c.status == "completed")
        in_progress_commitments = sum(1 for c in commitments if c.status == "in_progress")
        overdue_commitments = sum(
            1
            for c in commitments
            if c.due_date and c.due_date < now and c.status not in ("completed", "rejected")
        )

        rate = (
            round((completed_commitments / total_commitments) * 100.0, 1)
            if total_commitments > 0
            else 0.0
        )

        return ProjectDeliverySummary(
            total_projects=total_projects,
            active_projects=active_projects,
            completed_projects=completed_projects,
            total_commitments=total_commitments,
            completed_commitments=completed_commitments,
            in_progress_commitments=in_progress_commitments,
            overdue_commitments=overdue_commitments,
            delivery_completion_rate=rate,
        )
