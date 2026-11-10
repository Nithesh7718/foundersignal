from abc import abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.exceptions import ExternalProviderException
from app.providers.base import BaseProvider


class ExtractedSignal(BaseModel):
    category: str = Field(
        ..., description="Signal category (decision, commitment, blocker, progress)"
    )
    statement: str = Field(..., description="Concise statement of the fact or action")
    certainty: str = Field(..., description="'confirmed_fact', 'inferred', or 'unknown'")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence score")
    source_quote: str = Field(..., description="Verbatim source excerpt supporting this signal")
    source_speaker: str | None = Field(None, description="Speaker credited with this signal")
    suggested_action: str | None = Field(None, description="Recommended next step if applicable")


class ExtractionResult(BaseModel):
    provider: str
    is_mock: bool
    model_name: str
    signals: list[ExtractedSignal]
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMProvider(BaseProvider):
    """Abstract interface for LLM extraction and synthesis."""

    @abstractmethod
    async def extract_signals(
        self,
        transcript_text: str,
        context: dict[str, Any] | None = None,
    ) -> ExtractionResult:
        """Extract decisions, commitments, and facts with source quotes and confidence."""
        pass


class MockLLMProvider(LLMProvider):
    """Mock LLM Provider for local testing and deterministic validation."""

    @property
    def provider_name(self) -> str:
        return "mock_llm"

    @property
    def is_mock(self) -> bool:
        return True

    async def extract_signals(
        self,
        transcript_text: str,
        context: dict[str, Any] | None = None,
    ) -> ExtractionResult:
        return ExtractionResult(
            provider=self.provider_name,
            is_mock=True,
            model_name="mock-extractor-v1",
            signals=[
                ExtractedSignal(
                    category="commitment",
                    statement="Prepare onboarding flow before Thursday client review.",
                    certainty="inferred",
                    confidence=0.92,
                    source_quote=(
                        "Let's ensure the onboarding flow is ready by Thursday "
                        "before client review."
                    ),
                    source_speaker="Founder",
                    suggested_action="Confirm commitment and assign owner.",
                )
            ],
            metadata={"processed_chars": len(transcript_text)},
        )


def get_llm_provider() -> LLMProvider:
    """Factory for selecting LLM provider based on configuration."""
    if settings.is_production and (
        settings.MOCK_PROVIDERS or settings.LLM_PROVIDER.lower() == "mock"
    ):
        raise RuntimeError("Mock LLM provider cannot be used in production mode.")

    if settings.MOCK_PROVIDERS or settings.LLM_PROVIDER.lower() == "mock":
        return MockLLMProvider()

    if settings.LLM_PROVIDER.lower() in ["openai", "anthropic", "gemini"]:
        if not settings.LLM_API_KEY:
            raise ExternalProviderException(
                provider=settings.LLM_PROVIDER,
                message=f"API key for LLM provider '{settings.LLM_PROVIDER}' is not configured.",
            )
        raise NotImplementedError(
            f"Production adapter for LLM provider '{settings.LLM_PROVIDER}' "
            "requires live API credentials."
        )

    raise ExternalProviderException(
        provider="llm",
        message=f"Unsupported LLM provider '{settings.LLM_PROVIDER}'.",
    )
