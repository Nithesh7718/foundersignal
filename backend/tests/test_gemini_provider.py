import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.genai import errors

from app.core.config import Settings
from app.core.exceptions import ExternalProviderException
from app.providers.llm.base import (
    GeminiLLMProvider,
    get_llm_provider,
)


@pytest.mark.asyncio
async def test_gemini_successful_extraction_mocked_sdk() -> None:
    """Test successful commitment extraction with mocked Gemini GenAI SDK."""
    provider = GeminiLLMProvider(api_key="test-secret-key-12345", model_name="gemini-3.8-flash")
    assert "test-secret-key" not in repr(provider)
    assert provider.provider_name == "gemini"
    assert not provider.is_mock

    mock_json_payload = {
        "signals": [
            {
                "statement": "Finalize Q3 investor financial report",
                "item_type": "commitment",
                "category": "commitment",
                "certainty": "confirmed_fact",
                "source_quote": (
                    "I will finalize the Q3 investor financial report by Wednesday 3 PM."
                ),
                "source_speaker": "CFO",
                "owner": "CFO",
                "deadline": "Wednesday 3 PM",
                "confidence": 0.96,
                "evidence_explanation": "CFO stated explicit personal commitment and deadline.",
                "suggested_action": "Track delivery of Q3 report on Wednesday.",
            }
        ]
    }

    mock_response = MagicMock()
    mock_response.text = json.dumps(mock_json_payload)

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
    provider._client = mock_client

    transcript = "CFO: I will finalize the Q3 investor financial report by Wednesday 3 PM."
    result = await provider.extract_signals(transcript, context={"title": "Q3 Executive Review"})

    assert result.provider == "gemini"
    assert not result.is_mock
    assert len(result.signals) == 1
    sig = result.signals[0]
    assert sig.statement == "Finalize Q3 investor financial report"
    assert sig.item_type == "commitment"
    assert sig.source_speaker == "CFO"
    assert sig.owner == "CFO"
    assert sig.deadline == "Wednesday 3 PM"
    assert sig.confidence == 0.96
    assert sig.source_quote == "I will finalize the Q3 investor financial report by Wednesday 3 PM."


@pytest.mark.asyncio
async def test_gemini_empty_transcript_fast_path() -> None:
    """Empty or whitespace transcripts must immediately return empty signals without calling API."""
    provider = GeminiLLMProvider(api_key="dummy-key")
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock()
    provider._client = mock_client

    res1 = await provider.extract_signals("")
    assert res1.signals == []
    assert mock_client.aio.models.generate_content.call_count == 0

    res2 = await provider.extract_signals("   \n\t  ")
    assert res2.signals == []
    assert mock_client.aio.models.generate_content.call_count == 0


@pytest.mark.asyncio
async def test_gemini_no_hallucination_null_owner_and_deadline() -> None:
    """When transcript does not state owner or deadline, provider preserves null values."""
    provider = GeminiLLMProvider(api_key="dummy-key")
    mock_json_payload = {
        "signals": [
            {
                "statement": "Explore migration to European cloud datacenter",
                "item_type": "suggestion",
                "category": "decision",
                "certainty": "inferred",
                "source_quote": "Maybe we could look into moving our servers to Frankfurt.",
                "source_speaker": None,
                "owner": None,
                "deadline": None,
                "confidence": 0.45,
                "evidence_explanation": "Casual suggestion with no committed owner or deadline.",
                "suggested_action": None,
            }
        ]
    }
    mock_response = MagicMock()
    mock_response.text = json.dumps(mock_json_payload)

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
    provider._client = mock_client

    transcript = "Maybe we could look into moving our servers to Frankfurt."
    result = await provider.extract_signals(transcript)
    assert len(result.signals) == 1
    sig = result.signals[0]
    assert sig.owner is None
    assert sig.deadline is None
    assert sig.source_speaker is None
    assert sig.item_type == "suggestion"
    assert sig.confidence == 0.45


@pytest.mark.asyncio
async def test_gemini_rate_limit_retry_and_backoff() -> None:
    """Transient errors (429, 503) retry up to max_retries before succeeding."""
    provider = GeminiLLMProvider(api_key="dummy-key", max_retries=3, base_retry_delay=0.01)

    mock_json_payload = {"signals": []}
    mock_success = MagicMock()
    mock_success.text = json.dumps(mock_json_payload)

    err429 = errors.APIError(429, {"error": {"message": "Resource exhausted"}})
    err503 = errors.APIError(503, {"error": {"message": "Service unavailable"}})

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=[err429, err503, mock_success])
    provider._client = mock_client

    result = await provider.extract_signals("Brief conversation text.")
    assert result.signals == []
    assert mock_client.aio.models.generate_content.call_count == 3


@pytest.mark.asyncio
async def test_gemini_persistent_error_raises_exception() -> None:
    """Persistent 503 errors exhaust retries and raise ExternalProviderException."""
    provider = GeminiLLMProvider(api_key="dummy-key", max_retries=2, base_retry_delay=0.01)
    err503 = errors.APIError(503, {"error": {"message": "The service is temporarily overloaded."}})

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=err503)
    provider._client = mock_client

    with pytest.raises(ExternalProviderException) as exc_info:
        await provider.extract_signals("Some meeting discussion.")

    assert exc_info.value.status_code == 502
    assert "Gemini API error (503)" in str(exc_info.value.message)


@pytest.mark.asyncio
async def test_gemini_timeout_handling() -> None:
    """Network timeouts retry and eventually raise ExternalProviderException."""
    provider = GeminiLLMProvider(api_key="dummy-key", max_retries=2, base_retry_delay=0.01)

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=TimeoutError())
    provider._client = mock_client

    with pytest.raises(ExternalProviderException) as exc_info:
        await provider.extract_signals("Discussion text.")

    assert exc_info.value.status_code == 502
    assert "timed out" in str(exc_info.value.message).lower()


@pytest.mark.asyncio
async def test_gemini_malformed_json_response() -> None:
    """Non-JSON response raises ExternalProviderException with clear message."""
    provider = GeminiLLMProvider(api_key="dummy-key")
    mock_response = MagicMock()
    mock_response.text = "This is definitely not valid JSON from the model."

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
    provider._client = mock_client

    with pytest.raises(ExternalProviderException) as exc_info:
        await provider.extract_signals("Discussion text.")

    assert exc_info.value.status_code == 502
    assert "Failed to parse structured JSON" in str(exc_info.value.message)


def test_gemini_missing_api_key_validation() -> None:
    """Initializing Gemini provider without API key raises validation exception."""
    with pytest.raises(ExternalProviderException) as exc_info:
        GeminiLLMProvider(api_key="")
    assert "API key for Gemini LLM provider is not configured" in str(exc_info.value.message)


def test_gemini_provider_factory_resolution() -> None:
    """get_llm_provider correctly instantiates GeminiLLMProvider when configured."""
    test_settings = Settings(
        ENVIRONMENT="development",
        MOCK_PROVIDERS=False,
        LLM_PROVIDER="gemini",
        GEMINI_API_KEY="test-configured-key",
        GEMINI_MODEL="gemini-3.8-flash",
    )
    with patch("app.providers.llm.base.settings", test_settings):
        provider = get_llm_provider()
        assert isinstance(provider, GeminiLLMProvider)
        assert provider.model_name == "gemini-3.8-flash"


def test_production_mode_blocks_mock_fallback() -> None:
    """Production mode must reject mock provider configurations and missing Gemini keys."""
    # 1. Pydantic settings level validation rejects mock in production
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as val_info:
        Settings(
            ENVIRONMENT="production",
            MOCK_PROVIDERS=False,
            LLM_PROVIDER="mock",
        )
    assert "LLM_PROVIDER cannot be 'mock' in production mode" in str(val_info.value)

    # 2. Defense-in-depth runtime check in get_llm_provider
    prod_mock_settings = Settings.model_construct(
        ENVIRONMENT="production",
        MOCK_PROVIDERS=False,
        LLM_PROVIDER="mock",
    )
    with patch("app.providers.llm.base.settings", prod_mock_settings):
        with pytest.raises(RuntimeError) as exc_info:
            get_llm_provider()
        assert "Mock LLM provider cannot be used in production mode" in str(exc_info.value)

    # 3. Production mode with Gemini requires API key
    prod_gemini_no_key = Settings.model_construct(
        ENVIRONMENT="production",
        MOCK_PROVIDERS=False,
        LLM_PROVIDER="gemini",
        GEMINI_API_KEY="",
        LLM_API_KEY=None,
    )
    with patch("app.providers.llm.base.settings", prod_gemini_no_key):
        with pytest.raises(ExternalProviderException) as exc_info2:
            get_llm_provider()
        assert "API key for LLM provider 'gemini' is not configured" in str(exc_info2.value.message)
