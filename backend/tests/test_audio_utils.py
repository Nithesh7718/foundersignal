import io
import wave
from pathlib import Path

from app.core.audio_utils import (
    detect_audio_duration_from_path,
    detect_audio_duration_seconds,
    get_mp3_duration_seconds,
    get_wav_duration_seconds,
)


def _generate_test_wav_bytes(duration_seconds: float = 2.5, framerate: int = 16000) -> bytes:
    buffer = io.BytesIO()
    nframes = int(duration_seconds * framerate)
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(b"\x00\x00" * nframes)
    return buffer.getvalue()


def test_wav_duration_detection() -> None:
    expected_duration = 3.25
    wav_bytes = _generate_test_wav_bytes(duration_seconds=expected_duration, framerate=16000)

    detected = get_wav_duration_seconds(wav_bytes)
    assert detected is not None
    assert abs(detected - expected_duration) < 0.01

    # Also test detect_audio_duration_seconds helper
    detected_via_helper = detect_audio_duration_seconds(wav_bytes, "voice_memo.wav")
    assert detected_via_helper is not None
    assert abs(detected_via_helper - expected_duration) < 0.01


def test_corrupted_wav_returns_none() -> None:
    assert get_wav_duration_seconds(b"RIFF\x00\x00\x00\x00WAVEfmt truncated") is None
    assert detect_audio_duration_seconds(b"") is None
    assert detect_audio_duration_seconds(b"short") is None


def test_detect_audio_duration_from_path(tmp_path: Path) -> None:
    wav_bytes = _generate_test_wav_bytes(duration_seconds=1.5, framerate=8000)
    file_path = tmp_path / "sample.wav"
    file_path.write_bytes(wav_bytes)

    detected = detect_audio_duration_from_path(str(file_path))
    assert detected is not None
    assert abs(detected - 1.5) < 0.01

    # Non-existent file
    assert detect_audio_duration_from_path(str(tmp_path / "non_existent.wav")) is None


def test_mp3_duration_detection_heuristic() -> None:
    # Synthetic minimal MPEG-1 Layer III frame header:
    # 0xFF, 0xFB (sync + MPEG1 Layer III, no CRC)
    # 0x90 (bitrate idx 9 = 128 kbps, samplerate idx 0 = 44100Hz)
    # 0x00 (padding, private, etc.)
    header = b"\xff\xfb\x90\x00"
    payload = b"\x00" * 16000  # ~16004 bytes at 128 kbps = ~1.0 second
    fake_mp3 = header + payload

    duration = get_mp3_duration_seconds(fake_mp3)
    assert duration is not None
    assert 0.8 < duration < 1.2
