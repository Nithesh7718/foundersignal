import pytest

from app.providers.llm import get_llm_provider
from app.providers.stt import get_stt_provider
from app.providers.timbre import get_tts_provider


@pytest.mark.asyncio
async def test_mock_stt_provider_contract() -> None:
    stt = get_stt_provider()
    assert stt.is_mock is True
    result = await stt.transcribe_audio(b"sample_audio_data")

    assert result.is_mock is True
    assert result.total_duration > 0
    assert len(result.segments) > 0
    first_seg = result.segments[0]
    assert first_seg.confidence >= 0.0 and first_seg.confidence <= 1.0
    assert first_seg.speaker is not None


@pytest.mark.asyncio
async def test_mock_tts_provider_contract() -> None:
    tts = get_tts_provider()
    assert tts.is_mock is True
    result = await tts.synthesize_speech("Onboarding reminder")

    assert result.is_mock is True
    assert result.audio_format == "mp3"
    assert len(result.audio_bytes) > 0


@pytest.mark.asyncio
async def test_mock_llm_provider_evidence_contract() -> None:
    llm = get_llm_provider()
    assert llm.is_mock is True
    result = await llm.extract_signals("Sample conversation text")

    assert result.is_mock is True
    assert len(result.signals) > 0
    sig = result.signals[0]
    # Verify core principles: certainty tag, confidence, and source quote
    assert sig.certainty in ["confirmed_fact", "inferred", "unknown"]
    assert sig.confidence >= 0.0 and sig.confidence <= 1.0
    assert len(sig.source_quote) > 0
