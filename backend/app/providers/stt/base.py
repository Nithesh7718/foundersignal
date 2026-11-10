import logging
from abc import abstractmethod

import httpx
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.exceptions import ExternalProviderException
from app.providers.base import BaseProvider

logger = logging.getLogger(__name__)


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
        language: str = "en-IN",
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
        language: str = "en-IN",
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
    """Gnani Prisma Speech-to-Text official integration.

    Endpoints and Headers:
    - Target: POST https://api.vachana.ai/stt/v3
    - Header: X-API-Key-ID: <key>
    - Form payload: audio_file, model="prisma-v3.0", language_code="en-IN" (or "indic-auto")
    """

    def __init__(self, api_key: str, endpoint: str):
        self._api_key = api_key
        self._endpoint = endpoint or "https://api.vachana.ai/stt/v3"

    @property
    def provider_name(self) -> str:
        return "gnani_prisma"

    @property
    def is_mock(self) -> bool:
        return False

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        language: str = "en-IN",
    ) -> STTResult:
        if not self._api_key:
            raise ExternalProviderException(
                provider=self.provider_name,
                message="Gnani Prisma STT API key is not configured.",
            )

        headers = {
            "X-API-Key-ID": self._api_key,
        }
        data = {
            "model": "prisma-v3.0",
            "language_code": language,
        }
        files = {
            "audio_file": ("audio_input.wav", audio_bytes, "audio/wav"),
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self._endpoint,
                    headers=headers,
                    data=data,
                    files=files,
                )

            if response.status_code != 200:
                logger.error(
                    "Gnani Prisma STT API error status %s: %s",
                    response.status_code,
                    response.text,
                )
                raise ExternalProviderException(
                    provider=self.provider_name,
                    message=f"Gnani Prisma STT returned status {response.status_code}",
                )

            res_json = response.json()
            if not res_json.get("success", False):
                raise ExternalProviderException(
                    provider=self.provider_name,
                    message=res_json.get("message", "Gnani Prisma STT request was unsuccessful."),
                )

            transcript_text = res_json.get("transcript", "")
            detected_lang = res_json.get("detected_language_code", language)

            return STTResult(
                provider=self.provider_name,
                is_mock=False,
                language=detected_lang,
                total_duration=0.0,
                full_transcript=transcript_text,
                segments=[
                    TranscriptSegment(
                        start_time=0.0,
                        end_time=0.0,
                        speaker=None,
                        text=transcript_text,
                        confidence=1.0,
                    )
                ],
            )
        except httpx.RequestError as exc:
            logger.error("Gnani Prisma STT connection error: %s", exc)
            raise ExternalProviderException(
                provider=self.provider_name,
                message="Failed to connect to Gnani Prisma STT service.",
            ) from exc


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
