import asyncio
import json
import logging
from abc import abstractmethod
from typing import Any

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
    confidence: float | None = Field(
        None, ge=0.0, le=1.0, description="Word/segment confidence score"
    )
    language_detected: str | None = Field(
        None, description="Detected language code for this segment"
    )
    words: list[dict[str, Any]] = Field(
        default_factory=list, description="Word-level timestamps and details"
    )


class STTResult(BaseModel):
    provider: str
    is_mock: bool
    language: str
    total_duration: float
    full_transcript: str
    segments: list[TranscriptSegment] = Field(default_factory=list)
    model: str | None = "prisma-v3.0"
    raw_response: dict[str, Any] | None = None


class BatchJobStatus(BaseModel):
    job_id: str
    status: str  # CREATED, STARTING, QUEUED, IN_PROGRESS, COMPLETED, FAILED, CANCELLED
    percent: int = 0
    error_message: str | None = None
    file_details: list[dict[str, Any]] = Field(
        default_factory=list, description="Details of files processed in this batch job"
    )
    raw_data: dict[str, Any] | None = None


class STTProvider(BaseProvider):
    """Abstract interface for Speech-to-Text providers (specifically Gnani Prisma)."""

    @abstractmethod
    async def transcribe_sync(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language: str = "indic-auto",
    ) -> STTResult:
        """Synchronous REST transcription (for clips <= 30 seconds)."""
        pass

    @abstractmethod
    async def create_batch_job(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language: str = "indic-auto",
        with_diarization: bool = True,
        num_speakers: int = 5,
    ) -> str:
        """Create an asynchronous batch transcription job. Returns external job_id."""
        pass

    @abstractmethod
    async def start_batch_job(self, external_job_id: str) -> None:
        """Start processing a created batch job."""
        pass

    @abstractmethod
    async def get_batch_job_status(self, external_job_id: str) -> BatchJobStatus:
        """Get current status and progress of a batch transcription job."""
        pass

    @abstractmethod
    async def fetch_batch_transcript(self, external_job_id: str) -> STTResult:
        """Fetch and parse transcript from a completed batch job."""
        pass

    @abstractmethod
    async def cancel_batch_job(self, external_job_id: str, reason: str = "User cancelled") -> bool:
        """Cancel an active batch job. Returns True when remote cancellation is confirmed."""
        pass

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        language: str = "en-IN",
    ) -> STTResult:
        """Backwards compatible alias for transcribe_sync."""
        return await self.transcribe_sync(audio_bytes, "audio.wav", language)


class MockGnaniPrismaSTTProvider(STTProvider):
    """Mock STT Provider explicitly labelled for local development and test environments."""

    def __init__(self) -> None:
        # In-memory store for tracking mock batch jobs during dev/test sessions
        self._jobs: dict[str, dict[str, Any]] = {}

    @property
    def provider_name(self) -> str:
        return "gnani_prisma_mock"

    @property
    def is_mock(self) -> bool:
        return True

    async def transcribe_sync(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language: str = "indic-auto",
    ) -> STTResult:
        return STTResult(
            provider=self.provider_name,
            is_mock=True,
            language=language if language != "indic-auto" else "en-IN",
            total_duration=12.5,
            full_transcript=(
                "Let's ensure the onboarding flow is ready by Thursday before client review."
            ),
            model="prisma-v3.0",
            segments=[
                TranscriptSegment(
                    start_time=0.0,
                    end_time=3.2,
                    speaker="Founder",
                    text="Let's ensure the onboarding flow is ready by Thursday",
                    confidence=0.96,
                    language_detected="en-IN",
                ),
                TranscriptSegment(
                    start_time=3.5,
                    end_time=6.1,
                    speaker="Founder",
                    text="before client review.",
                    confidence=0.94,
                    language_detected="en-IN",
                ),
            ],
        )

    async def create_batch_job(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language: str = "indic-auto",
        with_diarization: bool = True,
        num_speakers: int = 5,
    ) -> str:
        import uuid

        job_id = f"mock-batch-{uuid.uuid4()}"
        self._jobs[job_id] = {
            "status": "CREATED",
            "percent": 0,
            "filename": filename,
            "language": language,
            "diarization": with_diarization,
        }
        return job_id

    async def start_batch_job(self, external_job_id: str) -> None:
        if external_job_id not in self._jobs:
            raise ExternalProviderException(
                provider=self.provider_name,
                message=f"Mock batch job '{external_job_id}' not found.",
            )
        self._jobs[external_job_id]["status"] = "STARTING"
        self._jobs[external_job_id]["percent"] = 10

    async def get_batch_job_status(self, external_job_id: str) -> BatchJobStatus:
        if external_job_id not in self._jobs:
            raise ExternalProviderException(
                provider=self.provider_name,
                message=f"Mock batch job '{external_job_id}' not found.",
            )

        job_info = self._jobs[external_job_id]
        current_status = job_info["status"]

        # Deterministically step through states for simulated background progress
        if current_status == "STARTING":
            job_info["status"] = "IN_PROGRESS"
            job_info["percent"] = 50
        elif current_status == "IN_PROGRESS":
            job_info["status"] = "COMPLETED"
            job_info["percent"] = 100

        return BatchJobStatus(
            job_id=external_job_id,
            status=job_info["status"],
            percent=job_info["percent"],
            raw_data=job_info,
        )

    async def fetch_batch_transcript(self, external_job_id: str) -> STTResult:
        if external_job_id not in self._jobs:
            raise ExternalProviderException(
                provider=self.provider_name,
                message=f"Mock batch job '{external_job_id}' not found.",
            )

        job_info = self._jobs[external_job_id]
        if job_info["status"] != "COMPLETED":
            raise ExternalProviderException(
                provider=self.provider_name,
                message=(
                    f"Cannot fetch transcript for job in state '{job_info['status']}'. "
                    "Must be COMPLETED."
                ),
            )

        lang = job_info.get("language", "en-IN")
        if lang == "indic-auto":
            lang = "en-IN"

        return STTResult(
            provider=self.provider_name,
            is_mock=True,
            language=lang,
            total_duration=18.4,
            model="prisma-v3.0",
            full_transcript=(
                "Good morning team, let's review the product backlog. "
                "I will deliver the API endpoints by Thursday. "
                "Great, let's make sure test coverage is in place."
            ),
            segments=[
                TranscriptSegment(
                    start_time=0.4,
                    end_time=3.8,
                    speaker="Speaker 0",
                    text="Good morning team, let's review the product backlog.",
                    confidence=0.96,
                    language_detected=lang,
                ),
                TranscriptSegment(
                    start_time=4.2,
                    end_time=8.5,
                    speaker="Speaker 1",
                    text="I will deliver the API endpoints by Thursday.",
                    confidence=0.93,
                    language_detected=lang,
                ),
                TranscriptSegment(
                    start_time=9.0,
                    end_time=13.4,
                    speaker="Speaker 0",
                    text="Great, let's make sure test coverage is in place.",
                    confidence=0.97,
                    language_detected=lang,
                ),
            ],
            raw_response={"mock_job_id": external_job_id},
        )

    async def cancel_batch_job(self, external_job_id: str, reason: str = "User cancelled") -> bool:
        if external_job_id in self._jobs:
            self._jobs[external_job_id]["status"] = "CANCELLED"
            self._jobs[external_job_id]["cancel_reason"] = reason
        return True


class GnaniPrismaSTTProvider(STTProvider):
    """Gnani Prisma Speech-to-Text official integration (REST and Batch).

    Follows official specs from docs.gnani.ai:
    - REST: POST https://api.vachana.ai/stt/v3 (for audio <= 30 seconds)
    - Batch:
      1. POST /stt/v3/batch/jobs (create)
      2. POST /stt/v3/batch/jobs/{job_id}/start (start)
      3. GET /stt/v3/batch/jobs/{job_id} (poll status >= 10s)
      4. GET /stt/v3/batch/jobs/{job_id}/files?status=COMPLETED (get file results)
      5. GET <transcript_url> (pre-signed S3 download)
    """

    def __init__(self, api_key: str, rest_endpoint: str, batch_endpoint: str):
        self._api_key = api_key
        self._rest_endpoint = rest_endpoint or "https://api.vachana.ai/stt/v3"
        self._batch_endpoint = batch_endpoint or "https://api.vachana.ai/stt/v3/batch/jobs"

    def __repr__(self) -> str:
        return (
            f"<GnaniPrismaSTTProvider "
            f"rest_endpoint='{self._rest_endpoint}' "
            f"batch_endpoint='{self._batch_endpoint}'>"
        )

    @property
    def provider_name(self) -> str:
        return "gnani_prisma"

    @property
    def is_mock(self) -> bool:
        return False

    def _headers(self) -> dict[str, str]:
        if not self._api_key:
            raise ExternalProviderException(
                provider=self.provider_name,
                message="Gnani Prisma STT API key is not configured.",
            )
        return {
            "X-API-Key-ID": self._api_key,
        }

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        timeout: float = 35.0,
        max_retries: int = 3,
    ) -> httpx.Response:
        """Execute HTTP request with exponential backoff on transient errors."""
        last_error: Exception | None = None
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        data=data,
                        files=files,
                        json=json_body,
                    )

                    # Transient server errors or rate limiting (429, 502, 503, 504) -> retry
                    if response.status_code in {429, 502, 503, 504} and attempt < max_retries - 1:
                        backoff = 0.5 * (2**attempt)
                        logger.warning(
                            "Gnani STT returned HTTP %s. Retrying in %.2fs (attempt %d/%d)",
                            response.status_code,
                            backoff,
                            attempt + 1,
                            max_retries,
                        )
                        await asyncio.sleep(backoff)
                        continue

                    return response
            except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as exc:
                last_error = exc
                if attempt < max_retries - 1:
                    backoff = 0.5 * (2**attempt)
                    logger.warning(
                        "Gnani STT connection failed: %s. Retrying in %.2fs (attempt %d/%d)",
                        exc,
                        backoff,
                        attempt + 1,
                        max_retries,
                    )
                    await asyncio.sleep(backoff)
                    continue

        if last_error:
            logger.error("Gnani Prisma STT request failed after retries: %s", last_error)
            raise ExternalProviderException(
                provider=self.provider_name,
                message="Failed to connect to Gnani Prisma STT service after retries.",
            ) from last_error

        raise ExternalProviderException(
            provider=self.provider_name,
            message="Unexpected request execution failure.",
        )

    async def transcribe_sync(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language: str = "indic-auto",
    ) -> STTResult:
        """Transcribe short audio (<= 30s) synchronously via REST STT."""
        norm_lang = "en-IN" if language.lower() in ("en", "english") else language
        headers = self._headers()
        data = {
            "model": "prisma-v3.0",
            "language_code": norm_lang,
            "format": "transcribe",
        }
        files = {
            "audio_file": (filename or "audio.wav", audio_bytes, "audio/wav"),
        }

        response = await self._request_with_retry(
            method="POST",
            url=self._rest_endpoint,
            headers=headers,
            data=data,
            files=files,
            timeout=35.0,
        )

        if response.status_code == 400 and "MAX_AUDIO_DURATION_EXCEEDED" in response.text:
            raise ExternalProviderException(
                provider=self.provider_name,
                message="MAX_AUDIO_DURATION_EXCEEDED: Audio clip exceeds 30s limit for REST STT.",
                details={"status_code": 400, "error": "MAX_AUDIO_DURATION_EXCEEDED"},
            )

        if response.status_code != 200:
            logger.error(
                "Gnani Prisma REST STT error status %s: %s",
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
        model_name = res_json.get("model", "prisma-v3.0")

        # Extract genuine confidence score if supplied by provider; default to None when absent
        conf_raw = res_json.get("confidence")
        segment_confidence: float | None = float(conf_raw) if conf_raw is not None else None

        return STTResult(
            provider=self.provider_name,
            is_mock=False,
            language=detected_lang,
            total_duration=0.0,
            full_transcript=transcript_text,
            model=model_name,
            segments=[
                TranscriptSegment(
                    start_time=0.0,
                    end_time=0.0,
                    speaker=None,
                    text=transcript_text,
                    confidence=segment_confidence,
                    language_detected=detected_lang,
                )
            ],
            raw_response=res_json,
        )

    async def create_batch_job(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language: str = "indic-auto",
        with_diarization: bool = True,
        num_speakers: int = 5,
    ) -> str:
        """Submit audio to create an asynchronous Batch transcription job."""
        if len(audio_bytes) > 10 * 1024 * 1024:
            raise ExternalProviderException(
                provider=self.provider_name,
                message=(
                    f"Audio file size ({len(audio_bytes) / (1024 * 1024):.1f} MB) "
                    "exceeds the 10 MB limit for direct batch transcription. "
                    "Files over 10 MB require the presigned batch v2 upload route."
                ),
            )

        headers = self._headers()
        norm_lang = "en-IN" if language.lower() in ("en", "english") else language
        config_payload = {
            "model": "prisma-v3.0",
            "language_code": norm_lang,
            "format": "transcribe",
            "mode": "transcribe",
            "with_diarization": with_diarization,
            "num_speakers": num_speakers,
        }
        data = {
            "config": json.dumps(config_payload),
        }
        files = {
            "files": (filename or "audio.wav", audio_bytes, "audio/wav"),
        }

        response = await self._request_with_retry(
            method="POST",
            url=self._batch_endpoint,
            headers=headers,
            data=data,
            files=files,
            timeout=40.0,
        )

        if response.status_code != 201:
            logger.error(
                "Gnani Prisma Create Batch Job error %s: %s",
                response.status_code,
                response.text,
            )
            raise ExternalProviderException(
                provider=self.provider_name,
                message=f"Failed to create Gnani Batch job (HTTP {response.status_code})",
            )

        res_json = response.json()
        job_id = res_json.get("job_id")
        if not job_id:
            raise ExternalProviderException(
                provider=self.provider_name,
                message="Gnani Batch job creation response missing 'job_id'.",
            )
        return str(job_id)

    async def start_batch_job(self, external_job_id: str) -> None:
        """Call POST /stt/v3/batch/jobs/{job_id}/start to begin processing."""
        headers = self._headers()
        url = f"{self._batch_endpoint.rstrip('/')}/{external_job_id}/start"

        response = await self._request_with_retry(
            method="POST",
            url=url,
            headers=headers,
            timeout=20.0,
        )

        if response.status_code not in (200, 202):
            logger.error(
                "Gnani Prisma Start Batch Job error %s: %s",
                response.status_code,
                response.text,
            )
            raise ExternalProviderException(
                provider=self.provider_name,
                message=(
                    f"Failed to start Gnani Batch job {external_job_id} "
                    f"(HTTP {response.status_code})"
                ),
            )

    async def get_batch_job_status(self, external_job_id: str) -> BatchJobStatus:
        """Poll status for an asynchronous Batch job."""
        headers = self._headers()
        url = f"{self._batch_endpoint.rstrip('/')}/{external_job_id}"

        response = await self._request_with_retry(
            method="GET",
            url=url,
            headers=headers,
            timeout=20.0,
        )

        if response.status_code != 200:
            logger.error(
                "Gnani Prisma Get Job Status error %s: %s",
                response.status_code,
                response.text,
            )
            raise ExternalProviderException(
                provider=self.provider_name,
                message=f"Failed to get Gnani Batch job status (HTTP {response.status_code})",
            )

        res_json = response.json()
        status_val = res_json.get("status", "UNKNOWN").upper()
        percent_val = int(res_json.get("percent", 0))
        error_msg = res_json.get("error_message") or res_json.get("message")
        file_details_val = res_json.get("file_details") or res_json.get("files") or []
        if not isinstance(file_details_val, list):
            file_details_val = []

        return BatchJobStatus(
            job_id=external_job_id,
            status=status_val,
            percent=percent_val,
            error_message=error_msg,
            file_details=file_details_val,
            raw_data=res_json,
        )

    async def fetch_batch_transcript(self, external_job_id: str) -> STTResult:
        """Download and assemble transcript JSON from completed Batch job."""
        headers = self._headers()
        url = f"{self._batch_endpoint.rstrip('/')}/{external_job_id}/files?status=COMPLETED"

        response = await self._request_with_retry(
            method="GET",
            url=url,
            headers=headers,
            timeout=25.0,
        )

        if response.status_code != 200:
            logger.error(
                "Gnani Prisma Get Job Files error %s: %s",
                response.status_code,
                response.text,
            )
            raise ExternalProviderException(
                provider=self.provider_name,
                message=(
                    f"Failed to retrieve files for job {external_job_id} "
                    f"(HTTP {response.status_code})"
                ),
            )

        files_json = response.json()
        file_items = files_json.get("data", [])
        if not file_items:
            raise ExternalProviderException(
                provider=self.provider_name,
                message=f"Batch job {external_job_id} has no completed file outputs.",
            )

        transcript_url = file_items[0].get("transcript_url")
        if not transcript_url:
            raise ExternalProviderException(
                provider=self.provider_name,
                message=f"Batch job {external_job_id} completed file missing transcript_url.",
            )

        # Download from pre-signed URL (no auth headers needed)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                dl_response = await client.get(transcript_url)
            if dl_response.status_code != 200:
                raise ExternalProviderException(
                    provider=self.provider_name,
                    message=(
                        "Failed to download transcript from presigned URL "
                        f"(HTTP {dl_response.status_code})"
                    ),
                )
            doc = dl_response.json()
        except Exception as exc:
            logger.error("Failed to download transcript document: %s", exc)
            raise ExternalProviderException(
                provider=self.provider_name,
                message="Error downloading completed batch transcript document.",
            ) from exc

        full_transcript = doc.get("full_transcript", "")
        duration_seconds = float(doc.get("duration_seconds", 0.0))
        model_name = doc.get("model", "prisma-v3.0")
        lang_code = doc.get("language_code", "en-IN")

        segments: list[TranscriptSegment] = []
        for raw_seg in doc.get("segments", []):
            text = raw_seg.get("text", "").strip()
            speaker_id = raw_seg.get("speaker_id")
            speaker_label: str | None = None
            if speaker_id is not None and speaker_id != -1:
                speaker_label = f"Speaker {speaker_id}"

            conf_raw = raw_seg.get("confidence")
            confidence = float(conf_raw) if conf_raw is not None else None
            words_raw = raw_seg.get("words", [])

            segments.append(
                TranscriptSegment(
                    start_time=float(raw_seg.get("start_time", 0.0)),
                    end_time=float(raw_seg.get("end_time", 0.0)),
                    speaker=speaker_label,
                    text=text,
                    confidence=confidence,
                    language_detected=raw_seg.get("language_detected"),
                    words=words_raw if isinstance(words_raw, list) else [],
                )
            )

        return STTResult(
            provider=self.provider_name,
            is_mock=False,
            language=lang_code,
            total_duration=duration_seconds,
            full_transcript=full_transcript,
            segments=segments,
            model=model_name,
            raw_response=doc,
        )

    async def cancel_batch_job(self, external_job_id: str, reason: str = "User cancelled") -> bool:
        """Cancel an in-progress or queued batch job via POST /stt/v3/batch/jobs/{job_id}/cancel.

        Requires remote confirmation (HTTP 200 or 409 JOB_CANCELLED).
        Raises ExternalProviderException on timeout, failure, or unexpected status code.
        """
        headers = self._headers()
        headers["Content-Type"] = "application/json"
        url = f"{self._batch_endpoint.rstrip('/')}/{external_job_id}/cancel"

        response = await self._request_with_retry(
            method="POST",
            url=url,
            headers=headers,
            json_body={"reason": reason},
            timeout=20.0,
        )

        if response.status_code in (200, 409):
            return True

        logger.error(
            "Gnani Prisma Cancel Job %s failed (HTTP %s): %s",
            external_job_id,
            response.status_code,
            response.text,
        )
        raise ExternalProviderException(
            provider=self.provider_name,
            message=(
                f"Failed to cancel Gnani Batch job {external_job_id} (HTTP {response.status_code})."
            ),
        )


def get_stt_provider() -> STTProvider:
    """Factory for selecting STT provider based on configuration."""
    if settings.is_production and settings.MOCK_PROVIDERS:
        raise RuntimeError("Mock STT provider cannot be used in production mode.")
    if settings.MOCK_PROVIDERS:
        return MockGnaniPrismaSTTProvider()
    return GnaniPrismaSTTProvider(
        api_key=settings.GNANI_PRISMA_API_KEY,
        rest_endpoint=settings.GNANI_PRISMA_ENDPOINT,
        batch_endpoint=settings.GNANI_PRISMA_BATCH_ENDPOINT,
    )
