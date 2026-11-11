import io
import logging
import wave

logger = logging.getLogger(__name__)


def get_wav_duration_seconds(audio_bytes: bytes) -> float | None:
    """Extract audio duration in seconds from WAV binary content using standard wave parser.

    Returns duration in seconds rounded to 3 decimal places, or None if invalid.
    """
    if len(audio_bytes) < 44:
        return None
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
            framerate = wf.getframerate()
            nframes = wf.getnframes()
            if framerate > 0 and nframes >= 0:
                return round(nframes / float(framerate), 3)
    except Exception as exc:
        logger.debug("Failed to parse WAV header for duration: %s", exc)
        return None
    return None


def get_mp3_duration_seconds(audio_bytes: bytes) -> float | None:
    """Estimate MP3 duration by inspecting ID3 tags and first MPEG audio frame header.

    Returns approximate duration in seconds, or None if cannot be determined.
    """
    if len(audio_bytes) < 128:
        return None

    # Check for ID3v2 header
    offset = 0
    if audio_bytes.startswith(b"ID3") and len(audio_bytes) >= 10:
        # ID3v2 tag size is 4 syncsafe bytes at offset 6..9
        tag_size = (
            ((audio_bytes[6] & 0x7F) << 21)
            | ((audio_bytes[7] & 0x7F) << 14)
            | ((audio_bytes[8] & 0x7F) << 7)
            | (audio_bytes[9] & 0x7F)
        )
        offset = 10 + tag_size

    # Scan for MPEG sync word (11 consecutive 1 bits: 0xFF followed by 0xE0 mask)
    data_len = len(audio_bytes)
    while offset < data_len - 4:
        b0 = audio_bytes[offset]
        b1 = audio_bytes[offset + 1]
        if b0 == 0xFF and (b1 & 0xE0) == 0xE0:
            version_bits = (b1 >> 3) & 0x03
            layer_bits = (b1 >> 1) & 0x03

            # We care primarily about Layer III (0x01)
            if layer_bits == 0x01:
                b2 = audio_bytes[offset + 2]
                bitrate_idx = (b2 >> 4) & 0x0F
                samplerate_idx = (b2 >> 2) & 0x03

                # Bitrate table for MPEG-1 Layer III in kbps
                bitrates_v1_l3 = [
                    0,
                    32,
                    40,
                    48,
                    56,
                    64,
                    80,
                    96,
                    112,
                    128,
                    160,
                    192,
                    224,
                    256,
                    320,
                    0,
                ]
                sample_rates_v1 = [44100, 48000, 32000, 0]

                if version_bits == 3:  # MPEG-1
                    if bitrate_idx < len(bitrates_v1_l3) and samplerate_idx < len(sample_rates_v1):
                        bitrate = bitrates_v1_l3[bitrate_idx]
                        if bitrate > 0:
                            audio_payload_bytes = data_len - offset
                            duration = (audio_payload_bytes * 8.0) / (bitrate * 1000.0)
                            return round(duration, 3)
            break
        offset += 1

    return None


def detect_audio_duration_seconds(audio_bytes: bytes, filename: str = "") -> float | None:
    """Robustly detect or estimate audio duration in seconds from raw bytes.

    Gracefully falls back to None on unsupported or unparseable formats.
    """
    if not audio_bytes:
        return None

    lower_name = filename.lower()

    # Prioritize WAV detection
    if audio_bytes.startswith(b"RIFF") or lower_name.endswith(".wav"):
        duration = get_wav_duration_seconds(audio_bytes)
        if duration is not None:
            return duration

    # Check MP3
    if audio_bytes.startswith(b"ID3") or lower_name.endswith(".mp3"):
        duration = get_mp3_duration_seconds(audio_bytes)
        if duration is not None:
            return duration

    return None


def detect_audio_duration_from_path(file_path: str) -> float | None:
    """Detect audio duration directly from a filesystem file path."""
    from pathlib import Path

    path = Path(file_path)
    if not path.is_file():
        return None

    try:
        if path.suffix.lower() == ".wav":
            with wave.open(str(path), "rb") as wf:
                framerate = wf.getframerate()
                nframes = wf.getnframes()
                if framerate > 0 and nframes >= 0:
                    return round(nframes / float(framerate), 3)

        # Fallback to inspecting initial sample bytes
        with open(path, "rb") as f:
            sample_bytes = f.read(1024 * 1024)
            return detect_audio_duration_seconds(sample_bytes, path.name)
    except Exception as exc:
        logger.debug("Failed to detect audio duration from %s: %s", file_path, exc)
        return None
