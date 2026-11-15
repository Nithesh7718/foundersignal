"""create_projects_table_and_link_commitments

Revision ID: e1f49b8a2c10
Revises: 3c8e411b22e1
Create Date: 2026-11-15 14:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1f49b8a2c10"
down_revision: str | None = "3c8e411b22e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create projects table
    op.create_table(
        "projects",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="active"),
        sa.Column("target_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_projects_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. Indexes on projects table
    op.create_index(
        op.f("ix_projects_workspace_id"),
        "projects",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_projects_status"),
        "projects",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_projects_workspace_status",
        "projects",
        ["workspace_id", "status"],
        unique=False,
    )

    # 3. Add project_id to commitments table
    op.add_column(
        "commitments",
        sa.Column("project_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_commitments_project_id_projects",
        "commitments",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_commitments_project_id"),
        "commitments",
        ["project_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_commitments_project_id"), table_name="commitments")
    op.drop_constraint(
        "fk_commitments_project_id_projects", "commitments", type_="foreignkey"
    )
    op.drop_column("commitments", "project_id")

    op.drop_index("ix_projects_workspace_status", table_name="projects")
    op.drop_index(op.f("ix_projects_status"), table_name="projects")
    op.drop_index(op.f("ix_projects_workspace_id"), table_name="projects")
    op.drop_table("projects")
