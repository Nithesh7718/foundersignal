from abc import abstractmethod

from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.exceptions import ExternalProviderException
from app.providers.base import BaseProvider


class TTSResult(BaseModel):
    provider: str
    is_mock: bool
    audio_format: str = "mp3"
    audio_bytes: bytes = Field(..., repr=False)
    duration_seconds: float


class TTSProvider(BaseProvider):
    """Abstract interface for Text-to-Speech providers (specifically Timbre)."""

    @abstractmethod
    async def synthesize_speech(
        self,
        text: str,
        voice_id: str = "default",
    ) -> TTSResult:
        """Synthesize text into speech audio bytes."""
        pass


class MockTimbreTTSProvider(TTSProvider):
    """Mock Timbre TTS Provider explicitly labelled for local development and testing."""

    @property
    def provider_name(self) -> str:
        return "timbre_tts_mock"

    @property
    def is_mock(self) -> bool:
        return True

    async def synthesize_speech(
        self,
        text: str,
        voice_id: str = "default",
    ) -> TTSResult:
        # Return lightweight placeholder audio payload for mock testing
        return TTSResult(
            provider=self.provider_name,
            is_mock=True,
            audio_format="mp3",
            audio_bytes=b"ID3_MOCK_TIMBRE_AUDIO_CONTENT",
            duration_seconds=3.0,
        )


class TimbreTTSProvider(TTSProvider):
    """Timbre Text-to-Speech integration.

    Requires valid Timbre API credentials and configured endpoint.
    """

    def __init__(self, api_key: str, endpoint: str):
        self._api_key = api_key
        self._endpoint = endpoint

    @property
    def provider_name(self) -> str:
        return "timbre_tts"

    @property
    def is_mock(self) -> bool:
        return False

    async def synthesize_speech(
        self,
        text: str,
        voice_id: str = "default",
    ) -> TTSResult:
        if not self._api_key:
            raise ExternalProviderException(
                provider=self.provider_name,
                message="Timbre TTS API key is not configured.",
            )
        raise NotImplementedError("Timbre production integration requires live API credentials.")


def get_tts_provider() -> TTSProvider:
    """Factory for selecting TTS provider based on configuration."""
    if settings.is_production and settings.MOCK_PROVIDERS:
        raise RuntimeError("Mock TTS provider cannot be used in production mode.")
    if settings.MOCK_PROVIDERS:
        return MockTimbreTTSProvider()
    return TimbreTTSProvider(
        api_key=settings.TIMBRE_API_KEY,
        endpoint=settings.TIMBRE_ENDPOINT,
    )
