from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.core.exceptions import ExternalProviderException
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
    assert 0.0 <= first_seg.confidence <= 1.0
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
    assert sig.certainty in ["confirmed_fact", "inferred", "unknown"]
    assert 0.0 <= sig.confidence <= 1.0
    assert len(sig.source_quote) > 0


def test_production_guards_against_mocks() -> None:
    with (
        patch("app.core.config.settings.ENVIRONMENT", "production"),
        patch("app.core.config.settings.MOCK_PROVIDERS", True),
    ):
        with pytest.raises(RuntimeError, match="cannot be used in production mode"):
            get_stt_provider()

        with pytest.raises(RuntimeError, match="cannot be used in production mode"):
            get_tts_provider()

        with pytest.raises(RuntimeError, match="cannot be used in production mode"):
            get_llm_provider()


def test_unsupported_llm_provider_raises_exception() -> None:
    with (
        patch("app.core.config.settings.MOCK_PROVIDERS", False),
        patch("app.core.config.settings.LLM_PROVIDER", "unsupported_provider"),
    ):
        with pytest.raises(ExternalProviderException, match="Unsupported LLM provider"):
            get_llm_provider()


def test_settings_validation_rejects_mock_in_production() -> None:
    with pytest.raises(ValueError, match="MOCK_PROVIDERS cannot be enabled in production"):
        Settings(
            ENVIRONMENT="production",
            MOCK_PROVIDERS=True,
            SECRET_KEY="production_safe_key_1234567890123456",
            GNANI_PRISMA_API_KEY="prod_key",
            TIMBRE_API_KEY="prod_key",
            LLM_API_KEY="prod_key",
            LLM_PROVIDER="openai",
        )


def test_settings_validation_rejects_wildcard_cors() -> None:
    with pytest.raises(ValueError, match=r"Wildcard origin '\*' is forbidden"):
        Settings(BACKEND_CORS_ORIGINS=["*"])
