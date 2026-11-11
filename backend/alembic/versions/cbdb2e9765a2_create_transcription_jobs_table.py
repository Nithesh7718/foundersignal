"""create_transcription_jobs_table

Revision ID: cbdb2e9765a2
Revises: afedc0e90813
Create Date: 2026-11-11 09:08:52.575540

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cbdb2e9765a2"
down_revision: str | None = "afedc0e90813"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Composite uniqueness and foreign key on conversations
    op.create_unique_constraint(
        "uq_conversations_id_workspace_id", "conversations", ["id", "workspace_id"]
    )

    # 2. Composite uniqueness and foreign key on audio_assets
    op.create_unique_constraint(
        "uq_audio_assets_id_workspace_conversation",
        "audio_assets",
        ["id", "workspace_id", "conversation_id"],
    )
    op.create_foreign_key(
        "fk_audio_assets_conversation_workspace",
        "audio_assets",
        "conversations",
        ["conversation_id", "workspace_id"],
        ["id", "workspace_id"],
        ondelete="CASCADE",
    )

    # 3. Composite uniqueness and foreign key on transcripts
    op.create_unique_constraint(
        "uq_transcripts_id_workspace_conversation",
        "transcripts",
        ["id", "workspace_id", "conversation_id"],
    )
    op.create_foreign_key(
        "fk_transcripts_conversation_workspace",
        "transcripts",
        "conversations",
        ["conversation_id", "workspace_id"],
        ["id", "workspace_id"],
        ondelete="CASCADE",
    )

    # 4. Create transcription_jobs with composite foreign keys
    op.create_table(
        "transcription_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("audio_asset_id", sa.Uuid(), nullable=False),
        sa.Column("transcript_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("job_type", sa.String(length=20), nullable=False),
        sa.Column("external_job_id", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("language_code", sa.String(length=20), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_poll_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["audio_asset_id"], ["audio_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["conversation_id", "workspace_id"],
            ["conversations.id", "conversations.workspace_id"],
            ondelete="CASCADE",
            name="fk_transcription_jobs_conversation_workspace",
        ),
        sa.ForeignKeyConstraint(
            ["audio_asset_id", "workspace_id", "conversation_id"],
            ["audio_assets.id", "audio_assets.workspace_id", "audio_assets.conversation_id"],
            ondelete="CASCADE",
            name="fk_transcription_jobs_audio_workspace_conversation",
        ),
        sa.ForeignKeyConstraint(
            ["transcript_id"],
            ["transcripts.id"],
            ondelete="SET NULL",
            name="fk_transcription_jobs_transcript_id",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
            name="fk_transcription_jobs_workspace_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_transcription_jobs_audio_asset_id"),
        "transcription_jobs",
        ["audio_asset_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_transcription_jobs_conversation_id"),
        "transcription_jobs",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_transcription_jobs_external_job_id"),
        "transcription_jobs",
        ["external_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_transcription_jobs_next_poll_at"),
        "transcription_jobs",
        ["next_poll_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_transcription_jobs_status"), "transcription_jobs", ["status"], unique=False
    )
    op.create_index(
        "ix_transcription_jobs_status_next_poll",
        "transcription_jobs",
        ["status", "next_poll_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_transcription_jobs_transcript_id"),
        "transcription_jobs",
        ["transcript_id"],
        unique=False,
    )
    op.create_index(
        "ix_transcription_jobs_workspace_conversation",
        "transcription_jobs",
        ["workspace_id", "conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_transcription_jobs_workspace_id"),
        "transcription_jobs",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "uq_active_transcription_job_per_asset",
        "transcription_jobs",
        ["audio_asset_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('queued', 'submitting', 'submitted', "
            "'submission_unknown', 'cancelled_unconfirmed', 'processing')"
        ),
    )
    op.create_index(
        "uq_transcription_jobs_provider_external_id",
        "transcription_jobs",
        ["provider", "external_job_id"],
        unique=True,
        postgresql_where=sa.text("external_job_id IS NOT NULL"),
    )

    # 5. Database triggers enforcing cross-tenant consistency on nullable relations
    op.execute(
        """
        CREATE OR REPLACE FUNCTION check_transcription_job_transcript_consistency()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.transcript_id IS NOT NULL THEN
                IF NOT EXISTS (
                    SELECT 1 FROM transcripts
                    WHERE id = NEW.transcript_id
                      AND workspace_id = NEW.workspace_id
                      AND conversation_id = NEW.conversation_id
                ) THEN
                    RAISE EXCEPTION
                        'Transcript % does not belong to workspace % and conversation %',
                        NEW.transcript_id, NEW.workspace_id, NEW.conversation_id;
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_transcription_job_transcript_consistency
        BEFORE INSERT OR UPDATE OF transcript_id, workspace_id, conversation_id
        ON transcription_jobs
        FOR EACH ROW
        EXECUTE FUNCTION check_transcription_job_transcript_consistency();
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION check_transcript_audio_asset_consistency()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.audio_asset_id IS NOT NULL THEN
                IF NOT EXISTS (
                    SELECT 1 FROM audio_assets
                    WHERE id = NEW.audio_asset_id
                      AND workspace_id = NEW.workspace_id
                      AND conversation_id = NEW.conversation_id
                ) THEN
                    RAISE EXCEPTION
                        'AudioAsset % does not belong to workspace % and conversation %',
                        NEW.audio_asset_id, NEW.workspace_id, NEW.conversation_id;
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_transcript_audio_asset_consistency
        BEFORE INSERT OR UPDATE OF audio_asset_id, workspace_id, conversation_id
        ON transcripts
        FOR EACH ROW
        EXECUTE FUNCTION check_transcript_audio_asset_consistency();
        """
    )


def downgrade() -> None:
    # 5. Drop triggers and functions
    op.execute("DROP TRIGGER IF EXISTS trg_transcript_audio_asset_consistency ON transcripts;")
    op.execute("DROP FUNCTION IF EXISTS check_transcript_audio_asset_consistency();")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_transcription_job_transcript_consistency ON transcription_jobs;"
    )
    op.execute("DROP FUNCTION IF EXISTS check_transcription_job_transcript_consistency();")

    # 4. Drop transcription_jobs and indexes
    op.drop_index(
        "uq_transcription_jobs_provider_external_id",
        table_name="transcription_jobs",
        postgresql_where=sa.text("external_job_id IS NOT NULL"),
    )
    op.drop_index(
        "uq_active_transcription_job_per_asset",
        table_name="transcription_jobs",
        postgresql_where=sa.text(
            "status IN ('queued', 'submitting', 'submitted', "
            "'submission_unknown', 'cancelled_unconfirmed', 'processing')"
        ),
    )
    op.drop_index(op.f("ix_transcription_jobs_workspace_id"), table_name="transcription_jobs")
    op.drop_index("ix_transcription_jobs_workspace_conversation", table_name="transcription_jobs")
    op.drop_index(op.f("ix_transcription_jobs_transcript_id"), table_name="transcription_jobs")
    op.drop_index("ix_transcription_jobs_status_next_poll", table_name="transcription_jobs")
    op.drop_index(op.f("ix_transcription_jobs_status"), table_name="transcription_jobs")
    op.drop_index(op.f("ix_transcription_jobs_next_poll_at"), table_name="transcription_jobs")
    op.drop_index(op.f("ix_transcription_jobs_external_job_id"), table_name="transcription_jobs")
    op.drop_index(op.f("ix_transcription_jobs_conversation_id"), table_name="transcription_jobs")
    op.drop_index(op.f("ix_transcription_jobs_audio_asset_id"), table_name="transcription_jobs")
    op.drop_table("transcription_jobs")

    # 3. Drop composite constraints on transcripts
    op.drop_constraint("fk_transcripts_conversation_workspace", "transcripts", type_="foreignkey")
    op.drop_constraint("uq_transcripts_id_workspace_conversation", "transcripts", type_="unique")

    # 2. Drop composite constraints on audio_assets
    op.drop_constraint("fk_audio_assets_conversation_workspace", "audio_assets", type_="foreignkey")
    op.drop_constraint("uq_audio_assets_id_workspace_conversation", "audio_assets", type_="unique")

    # 1. Drop composite constraint on conversations
    op.drop_constraint("uq_conversations_id_workspace_id", "conversations", type_="unique")
