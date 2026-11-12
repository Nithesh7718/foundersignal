import hashlib
from pathlib import Path
from typing import BinaryIO

from app.core.config import settings
from app.core.exceptions import (
    NotFoundException,
    PayloadTooLargeException,
    ValidationException,
)
from app.core.storage.base import StorageAdapter


def detect_audio_mime(header: bytes, filename: str) -> str:
    """Validate magic bytes against supported audio formats."""
    if len(header) < 12:
        raise ValidationException("Audio file is too small or empty.")

    # WAV: RIFF....WAVE
    if header[:4] == b"RIFF" and header[8:12] == b"WAVE":
        return "audio/wav"

    # MP3: ID3 tag or MPEG sync frame (0xFFF)
    if header[:3] == b"ID3":
        return "audio/mpeg"
    if header[0] == 0xFF and (header[1] & 0xE0) == 0xE0:
        return "audio/mpeg"

    # OGG
    if header[:4] == b"OggS":
        return "audio/ogg"

    # FLAC
    if header[:4] == b"fLaC":
        return "audio/flac"

    # MP4 / M4A (ftyp box)
    if header[4:8] == b"ftyp":
        return "audio/mp4"

    # WebM / Matroska
    if header[:4] == b"\x1a\x45\xdf\xa3":
        return "audio/webm"

    # Fallback check on common extensions if header signature is non-standard
    ext = Path(filename).suffix.lower()
    if ext in [".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac", ".webm"]:
        # If extension is valid but header didn't match known signatures, reject for safety
        raise ValidationException("Uploaded file does not match valid audio format magic bytes.")

    raise ValidationException(
        "Unsupported audio format. Supported formats: WAV, MP3, OGG, FLAC, M4A, WebM. "
        f"File: {filename}"
    )


class LocalStorageAdapter(StorageAdapter):
    """Local filesystem storage adapter with strict validation and multi-tenant partitioning."""

    def __init__(self, base_directory: str | None = None) -> None:
        self.base_dir = Path(base_directory or settings.AUDIO_STORAGE_PATH).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.max_bytes = settings.MAX_AUDIO_UPLOAD_SIZE_MB * 1024 * 1024

    def _resolve_safe_path(self, workspace_id: str, filename: str) -> Path:
        """Resolve path and guard against directory traversal attacks."""
        target_dir = (self.base_dir / workspace_id).resolve()
        if not target_dir.is_relative_to(self.base_dir):
            raise ValidationException("Invalid workspace path identifier.")

        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = (target_dir / filename).resolve()
        if not target_file.is_relative_to(self.base_dir):
            raise ValidationException("Path traversal attempt detected in storage path.")

        return target_file

    async def save_file(
        self,
        workspace_id: str,
        asset_id: str,
        original_filename: str,
        file_obj: BinaryIO,
    ) -> tuple[str, int, str, str]:
        """Save and validate an audio file to the local storage hierarchy."""
        # Determine extension from original filename safely
        ext = Path(original_filename).suffix.lower()
        if not ext or len(ext) > 10:
            ext = ".bin"

        stored_filename = f"{asset_id}{ext}"
        dest_path = self._resolve_safe_path(workspace_id, stored_filename)

        # Read initial chunk for magic bytes validation
        chunk = file_obj.read(512)
        if not chunk:
            raise ValidationException("Uploaded audio file is empty.")

        mime_type = detect_audio_mime(chunk, original_filename)

        # Write to disk while computing SHA-256 and enforcing size limit
        hasher = hashlib.sha256()
        total_size = len(chunk)
        if total_size > self.max_bytes:
            limit_mb = settings.MAX_AUDIO_UPLOAD_SIZE_MB
            raise PayloadTooLargeException(
                f"Audio file exceeds maximum allowed size of {limit_mb}MB."
            )
        hasher.update(chunk)

        with open(dest_path, "wb") as f:
            f.write(chunk)
            while True:
                buf = file_obj.read(64 * 1024)
                if not buf:
                    break
                total_size += len(buf)
                if total_size > self.max_bytes:
                    f.close()
                    dest_path.unlink(missing_ok=True)
                    limit_mb = settings.MAX_AUDIO_UPLOAD_SIZE_MB
                    raise PayloadTooLargeException(
                        f"Audio file exceeds maximum allowed size of {limit_mb}MB."
                    )
                hasher.update(buf)
                f.write(buf)

        sha256_checksum = hasher.hexdigest()
        rel_path = str(dest_path.relative_to(self.base_dir))

        return rel_path, total_size, mime_type, sha256_checksum

    async def get_file_bytes(self, storage_path: str) -> bytes:
        """Read audio file bytes from storage."""
        full_path = (self.base_dir / storage_path).resolve()
        if not full_path.is_relative_to(self.base_dir):
            raise ValidationException("Path traversal attempt detected.")
        if not full_path.exists():
            raise NotFoundException("Requested audio file does not exist.")

        with open(full_path, "rb") as f:
            return f.read()

    async def get_file_size(self, storage_path: str) -> int:
        """Get stored file size in bytes without loading contents into memory."""
        full_path = (self.base_dir / storage_path).resolve()
        if not full_path.is_relative_to(self.base_dir):
            raise ValidationException("Path traversal attempt detected.")
        if not full_path.exists():
            raise NotFoundException("Requested audio file does not exist.")
        return full_path.stat().st_size

    async def get_file_slice(self, storage_path: str, start: int, end: int) -> bytes:
        """Retrieve a specific byte slice [start, end] inclusive from storage."""
        full_path = (self.base_dir / storage_path).resolve()
        if not full_path.is_relative_to(self.base_dir):
            raise ValidationException("Path traversal attempt detected.")
        if not full_path.exists():
            raise NotFoundException("Requested audio file does not exist.")

        length = end - start + 1
        with open(full_path, "rb") as f:
            f.seek(start)
            return f.read(length)

    async def delete_file(self, storage_path: str) -> bool:
        """Delete audio file from storage."""
        full_path = (self.base_dir / storage_path).resolve()
        if not full_path.is_relative_to(self.base_dir):
            raise ValidationException("Path traversal attempt detected.")

        if full_path.exists():
            full_path.unlink()
            return True
        return False
