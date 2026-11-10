from abc import ABC, abstractmethod
from typing import BinaryIO


class StorageAdapter(ABC):
    """Abstract interface for audio file storage.

    Retention Policy:
    FounderSignal stores raw audio assets for evidence verification, transcription auditing,
    and voice analytics. Raw audio files are stored in segregated workspace partitions,
    indexed by workspace ID and asset UUID. Audio assets are retained until deleted
    by a workspace owner or when the parent conversation/workspace is removed.
    Cascading deletes remove both database records and physical storage objects.
    """

    @abstractmethod
    async def save_file(
        self,
        workspace_id: str,
        asset_id: str,
        original_filename: str,
        file_obj: BinaryIO,
    ) -> tuple[str, int, str, str]:
        """Save an audio file to storage.

        Args:
            workspace_id: Tenant workspace ID.
            asset_id: Unique UUID for the audio asset.
            original_filename: Name provided by client (for extension resolution).
            file_obj: File-like object with audio bytes.

        Returns:
            tuple[storage_path, file_size_bytes, mime_type, sha256_checksum]
        """
        pass

    @abstractmethod
    async def get_file_bytes(self, storage_path: str) -> bytes:
        """Retrieve stored file contents as bytes."""
        pass

    @abstractmethod
    async def delete_file(self, storage_path: str) -> bool:
        """Delete stored file from storage."""
        pass
