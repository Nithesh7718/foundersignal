import io
import tempfile
import uuid

import pytest

from app.core.exceptions import PayloadTooLargeException, ValidationException
from app.core.storage.local import LocalStorageAdapter, detect_audio_mime
from tests.test_conversations import create_minimal_wav_bytes


@pytest.mark.asyncio
async def test_storage_adapter_save_and_retrieve() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageAdapter(base_directory=tmpdir)
        workspace_id = str(uuid.uuid4())
        asset_id = str(uuid.uuid4())
        wav_bytes = create_minimal_wav_bytes()

        rel_path, size, mime, sha256_hash = await storage.save_file(
            workspace_id=workspace_id,
            asset_id=asset_id,
            original_filename="sample_meeting.wav",
            file_obj=io.BytesIO(wav_bytes),
        )

        assert size == len(wav_bytes)
        assert mime == "audio/wav"
        assert len(sha256_hash) == 64

        retrieved_bytes = await storage.get_file_bytes(rel_path)
        assert retrieved_bytes == wav_bytes

        deleted = await storage.delete_file(rel_path)
        assert deleted is True


@pytest.mark.asyncio
async def test_storage_adapter_path_traversal_blocked() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageAdapter(base_directory=tmpdir)
        with pytest.raises(ValidationException):
            await storage.save_file(
                workspace_id="../../../etc",
                asset_id="passwd",
                original_filename="malicious.wav",
                file_obj=io.BytesIO(create_minimal_wav_bytes()),
            )


@pytest.mark.asyncio
async def test_storage_adapter_exceeds_size_limit_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageAdapter(base_directory=tmpdir)
        # Set max_bytes to 50 bytes for test
        storage.max_bytes = 50

        # WAV header (44 bytes) + 20 bytes data = 64 bytes > 50
        large_wav = create_minimal_wav_bytes() + b"\x00" * 20

        with pytest.raises(PayloadTooLargeException):
            await storage.save_file(
                workspace_id=str(uuid.uuid4()),
                asset_id=str(uuid.uuid4()),
                original_filename="oversized.wav",
                file_obj=io.BytesIO(large_wav),
            )


def test_magic_bytes_detection() -> None:
    # WAV
    wav = create_minimal_wav_bytes()
    assert detect_audio_mime(wav, "test.wav") == "audio/wav"

    # MP3 with ID3
    mp3_id3 = b"ID3" + b"\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 10
    assert detect_audio_mime(mp3_id3, "test.mp3") == "audio/mpeg"

    # OGG
    ogg = b"OggS\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00" + b"\x00" * 10
    assert detect_audio_mime(ogg, "test.ogg") == "audio/ogg"

    # WebM
    webm = b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01\x42\xf7\x81\x01"
    assert detect_audio_mime(webm, "test.webm") == "audio/webm"

    # Non-audio rejected
    with pytest.raises(ValidationException):
        detect_audio_mime(b"<!DOCTYPE html><html>", "test.html")
