import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Header, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_workspace_context,
    get_db,
    get_storage_adapter,
)
from app.core.exceptions import ValidationException
from app.core.storage.base import StorageAdapter
from app.models.workspace import Workspace
from app.schemas.audio import AudioAssetResponse
from app.schemas.conversation import (
    ConversationCreate,
    ConversationDetailResponse,
    ConversationResponse,
)
from app.services.conversation_service import ConversationService

router = APIRouter()


@router.get(
    "/workspaces/{workspace_id}/conversations",
    response_model=list[ConversationResponse],
)
def list_conversations(
    workspace_context: Annotated[tuple[Workspace, str], Depends(get_current_workspace_context)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ConversationResponse]:
    """List all conversations within a workspace."""
    workspace, _role = workspace_context
    conversations = ConversationService.list_conversations(db, workspace.id)

    return [
        ConversationResponse(
            id=conv.id,
            workspace_id=conv.workspace_id,
            title=conv.title,
            conversation_type=conv.conversation_type,
            status=conv.status,
            recorded_at=conv.recorded_at,
            created_at=conv.created_at,
            audio_assets=[AudioAssetResponse.model_validate(asset) for asset in conv.audio_assets],
            commitments_count=len(conv.commitments),
        )
        for conv in conversations
    ]


@router.post(
    "/workspaces/{workspace_id}/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    conv_in: ConversationCreate,
    workspace_context: Annotated[tuple[Workspace, str], Depends(get_current_workspace_context)],
    db: Annotated[Session, Depends(get_db)],
) -> ConversationResponse:
    """Create a new conversation record in a workspace."""
    workspace, _role = workspace_context
    conv = ConversationService.create_conversation(db, workspace.id, conv_in)

    return ConversationResponse(
        id=conv.id,
        workspace_id=conv.workspace_id,
        title=conv.title,
        conversation_type=conv.conversation_type,
        status=conv.status,
        recorded_at=conv.recorded_at,
        created_at=conv.created_at,
        audio_assets=[],
        commitments_count=0,
    )


@router.get(
    "/workspaces/{workspace_id}/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
)
def get_conversation(
    conversation_id: uuid.UUID,
    workspace_context: Annotated[tuple[Workspace, str], Depends(get_current_workspace_context)],
    db: Annotated[Session, Depends(get_db)],
) -> ConversationDetailResponse:
    """Retrieve full conversation details including audio assets, transcripts, and commitments."""
    workspace, _role = workspace_context
    conv = ConversationService.get_conversation(db, workspace.id, conversation_id)
    return ConversationDetailResponse.model_validate(conv)


@router.post(
    "/workspaces/{workspace_id}/conversations/{conversation_id}/audio",
    response_model=AudioAssetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_conversation_audio(
    conversation_id: uuid.UUID,
    workspace_context: Annotated[tuple[Workspace, str], Depends(get_current_workspace_context)],
    file: Annotated[UploadFile, File(description="Audio file (WAV, MP3, OGG, FLAC, M4A, WebM)")],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[StorageAdapter, Depends(get_storage_adapter)],
) -> AudioAssetResponse:
    """Upload and attach an audio file to a conversation."""
    workspace, _role = workspace_context
    if not file.filename:
        raise ValidationException("Uploaded file must have a filename.")

    asset = await ConversationService.attach_audio_file(
        db=db,
        workspace_id=workspace.id,
        conversation_id=conversation_id,
        original_filename=file.filename,
        file_obj=file.file,
        storage=storage,
    )
    return AudioAssetResponse.model_validate(asset)


@router.delete(
    "/workspaces/{workspace_id}/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_conversation(
    conversation_id: uuid.UUID,
    workspace_context: Annotated[tuple[Workspace, str], Depends(get_current_workspace_context)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[StorageAdapter, Depends(get_storage_adapter)],
) -> None:
    """Delete a conversation, cascading database records and cleaning up physical audio storage."""
    workspace, _role = workspace_context
    await ConversationService.delete_conversation(
        db=db,
        workspace_id=workspace.id,
        conversation_id=conversation_id,
        storage=storage,
    )


@router.get(
    "/workspaces/{workspace_id}/conversations/{conversation_id}/audio/{audio_asset_id}",
    response_class=Response,
)
async def get_conversation_audio_file(
    conversation_id: uuid.UUID,
    audio_asset_id: uuid.UUID,
    workspace_context: Annotated[tuple[Workspace, str], Depends(get_current_workspace_context)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[StorageAdapter, Depends(get_storage_adapter)],
    range_header: Annotated[str | None, Header(alias="range")] = None,
) -> Response:
    """Retrieve raw audio file bytes with genuine HTTP Range (206), 200, and 416 support."""
    workspace, _role = workspace_context
    asset = ConversationService.get_audio_asset_metadata(
        db=db,
        workspace_id=workspace.id,
        conversation_id=conversation_id,
        audio_asset_id=audio_asset_id,
    )

    total_size = await storage.get_file_size(asset.storage_path)

    if range_header:
        if not range_header.startswith("bytes="):
            return Response(
                status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
                headers={"Content-Range": f"bytes */{total_size}", "Accept-Ranges": "bytes"},
            )

        range_val = range_header[len("bytes=") :].strip()
        parts = range_val.split("-")
        if len(parts) != 2:
            return Response(
                status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
                headers={"Content-Range": f"bytes */{total_size}", "Accept-Ranges": "bytes"},
            )

        start_str, end_str = parts[0].strip(), parts[1].strip()
        try:
            if start_str and end_str:
                start = int(start_str)
                end = int(end_str)
            elif start_str and not end_str:
                start = int(start_str)
                end = total_size - 1
            elif not start_str and end_str:
                suffix_len = int(end_str)
                start = max(0, total_size - suffix_len)
                end = total_size - 1
            else:
                raise ValueError("Empty range bounds")
        except ValueError:
            return Response(
                status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
                headers={"Content-Range": f"bytes */{total_size}", "Accept-Ranges": "bytes"},
            )

        if start < 0 or start >= total_size or end < start:
            return Response(
                status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
                headers={"Content-Range": f"bytes */{total_size}", "Accept-Ranges": "bytes"},
            )

        end = min(end, total_size - 1)
        slice_bytes = await storage.get_file_slice(asset.storage_path, start, end)
        content_length = len(slice_bytes)

        return Response(
            content=slice_bytes,
            status_code=status.HTTP_206_PARTIAL_CONTENT,
            media_type=asset.mime_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{total_size}",
                "Content-Length": str(content_length),
                "Accept-Ranges": "bytes",
                "Content-Disposition": f'inline; filename="{asset.file_name}"',
            },
        )

    file_bytes = await storage.get_file_bytes(asset.storage_path)
    return Response(
        content=file_bytes,
        status_code=status.HTTP_200_OK,
        media_type=asset.mime_type,
        headers={
            "Content-Length": str(total_size),
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'inline; filename="{asset.file_name}"',
        },
    )
