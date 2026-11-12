"""harden_commitments_schema_and_lifecycle

Revision ID: 3c8e411b22e1
Revises: 8af19defa86a
Create Date: 2026-11-13 01:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3c8e411b22e1"
down_revision: str | None = "8af19defa86a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Make confidence_score nullable (remove misleading 1.0 default)
    op.alter_column(
        "commitments",
        "confidence_score",
        existing_type=sa.Float(),
        nullable=True,
    )

    # 2. Add evidence_hash for stable deduplication
    op.add_column(
        "commitments",
        sa.Column("evidence_hash", sa.String(length=64), nullable=True),
    )

    # 3. Add review audit columns
    op.add_column(
        "commitments",
        sa.Column("reviewed_by_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "commitments",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 4. Foreign key for reviewed_by_id
    op.create_foreign_key(
        "fk_commitments_reviewed_by_id_users",
        "commitments",
        "users",
        ["reviewed_by_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 5. Indexes
    op.create_index(
        op.f("ix_commitments_evidence_hash"),
        "commitments",
        ["evidence_hash"],
        unique=False,
    )
    op.create_index(
        "uq_commitments_conv_evidence_hash",
        "commitments",
        ["conversation_id", "evidence_hash"],
        unique=True,
        postgresql_where=sa.text("evidence_hash IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_commitments_conv_evidence_hash", table_name="commitments")
    op.drop_index(op.f("ix_commitments_evidence_hash"), table_name="commitments")
    op.drop_constraint("fk_commitments_reviewed_by_id_users", "commitments", type_="foreignkey")
    op.drop_column("commitments", "reviewed_at")
    op.drop_column("commitments", "reviewed_by_id")
    op.drop_column("commitments", "evidence_hash")
    op.alter_column(
        "commitments",
        "confidence_score",
        existing_type=sa.Float(),
        nullable=False,
    )
