import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.audio_utils import detect_audio_duration_from_path
from app.core.config import settings
from app.core.exceptions import NotFoundException
from app.core.storage.base import StorageAdapter
from app.models.audio_asset import AudioAsset
from app.models.conversation import Conversation
from app.schemas.conversation import ConversationCreate


class ConversationService:
    @staticmethod
    def create_conversation(
        db: Session,
        workspace_id: uuid.UUID,
        conv_in: ConversationCreate,
    ) -> Conversation:
        conversation = Conversation(
            workspace_id=workspace_id,
            title=conv_in.title.strip(),
            conversation_type=conv_in.conversation_type,
            status="draft",
            recorded_at=conv_in.recorded_at or datetime.now(UTC),
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        return conversation

    @staticmethod
    def list_conversations(
        db: Session,
        workspace_id: uuid.UUID,
    ) -> list[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.workspace_id == workspace_id)
            .options(
                selectinload(Conversation.audio_assets),
                selectinload(Conversation.commitments),
            )
            .order_by(Conversation.created_at.desc())
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def get_conversation(
        db: Session,
        workspace_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> Conversation:
        stmt = (
            select(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.workspace_id == workspace_id,
            )
            .options(
                selectinload(Conversation.audio_assets),
                selectinload(Conversation.transcripts),
                selectinload(Conversation.commitments),
            )
        )
        conversation = db.execute(stmt).scalar_one_or_none()
        if not conversation:
            raise NotFoundException("Conversation not found in this workspace.")
        return conversation

    @staticmethod
    async def attach_audio_file(
        db: Session,
        workspace_id: uuid.UUID,
        conversation_id: uuid.UUID,
        original_filename: str,
        file_obj: BinaryIO,
        storage: StorageAdapter,
    ) -> AudioAsset:
        conversation = ConversationService.get_conversation(db, workspace_id, conversation_id)

        asset_id = uuid.uuid4()
        rel_path, total_size, mime_type, sha256_hash = await storage.save_file(
            workspace_id=str(workspace_id),
            asset_id=str(asset_id),
            original_filename=original_filename,
            file_obj=file_obj,
        )

        # Compute duration if detectable from audio headers
        full_dest_path = Path(settings.AUDIO_STORAGE_PATH) / rel_path
        duration = detect_audio_duration_from_path(str(full_dest_path.resolve()))

        audio_asset = AudioAsset(
            id=asset_id,
            workspace_id=workspace_id,
            conversation_id=conversation.id,
            file_name=original_filename,
            storage_path=rel_path,
            file_size_bytes=total_size,
            mime_type=mime_type,
            duration_seconds=duration,
            checksum_sha256=sha256_hash,
            status="ready",
        )
        db.add(audio_asset)
        conversation.status = "uploaded"
        db.commit()
        db.refresh(audio_asset)
        return audio_asset

    @staticmethod
    async def delete_conversation(
        db: Session,
        workspace_id: uuid.UUID,
        conversation_id: uuid.UUID,
        storage: StorageAdapter,
    ) -> None:
        """Delete conversation and remove physical audio files to prevent orphaned storage."""
        conversation = ConversationService.get_conversation(db, workspace_id, conversation_id)
        storage_paths = [asset.storage_path for asset in conversation.audio_assets]

        db.delete(conversation)
        db.commit()

        for path in storage_paths:
            await storage.delete_file(path)
