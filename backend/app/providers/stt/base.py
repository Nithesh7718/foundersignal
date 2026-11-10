from abc import abstractmethod

from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.exceptions import ExternalProviderException
from app.providers.base import BaseProvider


class TranscriptSegment(BaseModel):
    start_time: float = Field(..., description="Start timestamp in seconds")
    end_time: float = Field(..., description="End timestamp in seconds")
    speaker: str | None = Field(None, description="Identified speaker label or ID")
    text: str = Field(..., description="Transcribed utterance text")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Word/segment confidence score")


class STTResult(BaseModel):
    provider: str
    is_mock: bool
    language: str
    total_duration: float
    full_transcript: str
    segments: list[TranscriptSegment]


class STTProvider(BaseProvider):
    """Abstract interface for Speech-to-Text providers (specifically Gnani Prisma)."""

    @abstractmethod
    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        language: str = "en",
    ) -> STTResult:
        """Transcribe audio bytes to structured transcript with timestamps."""
        pass


class MockGnaniPrismaSTTProvider(STTProvider):
    """Mock STT Provider explicitly labelled for local development and test environments."""

    @property
    def provider_name(self) -> str:
        return "gnani_prisma_mock"

    @property
    def is_mock(self) -> bool:
        return True

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        language: str = "en",
    ) -> STTResult:
        return STTResult(
            provider=self.provider_name,
            is_mock=True,
            language=language,
            total_duration=12.5,
            full_transcript=(
                "Let's ensure the onboarding flow is ready by Thursday before client review."
            ),
            segments=[
                TranscriptSegment(
                    start_time=0.0,
                    end_time=3.2,
                    speaker="Founder",
                    text="Let's ensure the onboarding flow is ready by Thursday",
                    confidence=0.96,
                ),
                TranscriptSegment(
                    start_time=3.5,
                    end_time=6.1,
                    speaker="Founder",
                    text="before client review.",
                    confidence=0.94,
                ),
            ],
        )


class GnaniPrismaSTTProvider(STTProvider):
    """Gnani Prisma Speech-to-Text integration.

    Requires valid Gnani credentials and API endpoint.
    """

    def __init__(self, api_key: str, endpoint: str):
        self._api_key = api_key
        self._endpoint = endpoint

    @property
    def provider_name(self) -> str:
        return "gnani_prisma"

    @property
    def is_mock(self) -> bool:
        return False

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        language: str = "en",
    ) -> STTResult:
        if not self._api_key:
            raise ExternalProviderException(
                provider=self.provider_name,
                message="Gnani Prisma STT API key is not configured.",
            )
        # Production implementation requires real Gnani Prisma credentials and official contract
        raise NotImplementedError(
            "Gnani Prisma production integration requires live API credentials."
        )


def get_stt_provider() -> STTProvider:
    """Factory for selecting STT provider based on configuration."""
    if settings.is_production and settings.MOCK_PROVIDERS:
        raise RuntimeError("Mock STT provider cannot be used in production mode.")
    if settings.MOCK_PROVIDERS:
        return MockGnaniPrismaSTTProvider()
    return GnaniPrismaSTTProvider(
        api_key=settings.GNANI_PRISMA_API_KEY,
        endpoint=settings.GNANI_PRISMA_ENDPOINT,
    )
