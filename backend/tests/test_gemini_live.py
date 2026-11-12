import os

import pytest

from app.core.config import settings
from app.core.exceptions import ExternalProviderException
from app.providers.llm.base import GeminiLLMProvider

# Only run live API test if GEMINI_API_KEY is present in environment
HAS_LIVE_KEY = bool(settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY"))


@pytest.mark.skipif(not HAS_LIVE_KEY, reason="Live GEMINI_API_KEY not configured in environment")
@pytest.mark.asyncio
async def test_live_gemini_structured_commitment_extraction() -> None:
    """Separately identified LIVE integration test with Google Gemini API.
    Uses a short, non-sensitive business transcript snippet.
    """
    api_key = settings.GEMINI_API_KEY or os.environ["GEMINI_API_KEY"]
    model_name = os.environ.get("GEMINI_LIVE_MODEL") or settings.GEMINI_MODEL or "gemini-3.8-flash"

    transcript_snippet = (
        "Founder: Team, let's lock in our key deliverables for this sprint.\n"
        "Priya: I will finalize the marketing pitch deck by Thursday at 5 PM.\n"
        "Founder: Perfect. Does anyone have ideas for next quarter?\n"
        "Alex: Maybe we could explore expanding to Tokyo next year."
    )

    provider = GeminiLLMProvider(
        api_key=api_key,
        model_name=model_name,
        max_retries=2,
        base_retry_delay=1.0,
    )

    try:
        result = await provider.extract_signals(
            transcript_snippet,
            context={"title": "Sprint Planning Delivery Check"},
        )
    except ExternalProviderException as exc:
        # If gemini-3.8-flash is experiencing temporary 503 high demand spikes on Google's side,
        # fail over to gemini-3.1-flash-lite to verify live structured integration
        if "503" in str(exc.message) and model_name == "gemini-3.8-flash":
            fallback_provider = GeminiLLMProvider(
                api_key=api_key,
                model_name="gemini-3.1-flash-lite",
            )
            result = await fallback_provider.extract_signals(
                transcript_snippet,
                context={"title": "Sprint Planning Delivery Check"},
            )
        else:
            raise

    assert result.provider == "gemini"
    assert not result.is_mock
    assert len(result.signals) >= 1

    # Find the commitment made by Priya
    priya_commits = [
        s
        for s in result.signals
        if s.item_type == "commitment" and "pitch deck" in s.statement.lower()
    ]
    assert len(priya_commits) >= 1
    commit = priya_commits[0]

    assert (
        "priya" in (commit.owner or "").lower() or "priya" in (commit.source_speaker or "").lower()
    )
    assert "thursday" in (commit.deadline or "").lower()
    assert commit.source_quote in transcript_snippet
    assert commit.confidence is not None
    assert 0.0 <= commit.confidence <= 1.0
