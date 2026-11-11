import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.config import Settings
from app.core.exceptions import ExternalProviderException
from app.providers.llm import get_llm_provider
from app.providers.stt import get_stt_provider
from app.providers.stt.base import (
    BatchJobStatus,
    GnaniPrismaSTTProvider,
    STTResult,
    TranscriptSegment,
)
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


@pytest.mark.asyncio
async def test_mock_stt_batch_lifecycle() -> None:
    stt = get_stt_provider()
    assert stt.is_mock is True

    # 1. Create Batch Job
    job_id = await stt.create_batch_job(
        audio_bytes=b"dummy_wav_bytes",
        filename="meeting.wav",
        language="indic-auto",
        with_diarization=True,
    )
    assert job_id.startswith("mock-batch-")

    # 2. Start Batch Job
    await stt.start_batch_job(job_id)

    # 3. Poll Status (first poll: IN_PROGRESS)
    status_1 = await stt.get_batch_job_status(job_id)
    assert status_1.status == "IN_PROGRESS"
    assert status_1.percent == 50

    # 4. Poll Status (second poll: COMPLETED)
    status_2 = await stt.get_batch_job_status(job_id)
    assert status_2.status == "COMPLETED"
    assert status_2.percent == 100

    # 5. Fetch Transcript
    result = await stt.fetch_batch_transcript(job_id)
    assert result.is_mock is True
    assert result.total_duration > 0
    assert len(result.segments) >= 2
    assert result.segments[0].speaker == "Speaker 0"
    assert result.segments[1].speaker == "Speaker 1"
    assert result.segments[0].confidence is not None

    # 6. Cancel test
    job_id_2 = await stt.create_batch_job(b"more_bytes")
    await stt.cancel_batch_job(job_id_2, reason="Test cancellation")
    status_cancel = await stt.get_batch_job_status(job_id_2)
    assert status_cancel.status == "CANCELLED"


@pytest.mark.asyncio
async def test_mock_stt_batch_not_completed_fails() -> None:
    stt = get_stt_provider()
    job_id = await stt.create_batch_job(b"bytes")
    # Job is in CREATED status, fetching transcript should fail
    with pytest.raises(ExternalProviderException, match="Cannot fetch transcript"):
        await stt.fetch_batch_transcript(job_id)


@pytest.mark.asyncio
async def test_gnani_prisma_rest_stt_mocked() -> None:
    provider = GnaniPrismaSTTProvider(
        api_key="test_key",
        rest_endpoint="https://api.vachana.ai/stt/v3",
        batch_endpoint="https://api.vachana.ai/stt/v3/batch/jobs",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "success": True,
        "request_id": "test-req-123",
        "transcript": "Hello from FounderSignal",
        "detected_language_code": "en-IN",
        "model": "prisma-v3.0",
    }

    with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_resp
        res = await provider.transcribe_sync(b"fake_audio", "audio.wav", "en-IN")
        assert res.full_transcript == "Hello from FounderSignal"
        assert res.language == "en-IN"
        assert res.is_mock is False


@pytest.mark.asyncio
async def test_gnani_prisma_rest_stt_duration_exceeded_mocked() -> None:
    provider = GnaniPrismaSTTProvider(
        api_key="test_key",
        rest_endpoint="https://api.vachana.ai/stt/v3",
        batch_endpoint="https://api.vachana.ai/stt/v3/batch/jobs",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.text = "MAX_AUDIO_DURATION_EXCEEDED"

    with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_resp
        with pytest.raises(ExternalProviderException, match="MAX_AUDIO_DURATION_EXCEEDED"):
            await provider.transcribe_sync(b"long_audio", "audio.wav", "en-IN")


@pytest.mark.asyncio
async def test_gnani_prisma_batch_stt_mocked_flow() -> None:
    provider = GnaniPrismaSTTProvider(
        api_key="test_key",
        rest_endpoint="https://api.vachana.ai/stt/v3",
        batch_endpoint="https://api.vachana.ai/stt/v3/batch/jobs",
    )

    # 1. Create job mock
    resp_create = MagicMock()
    resp_create.status_code = 201
    resp_create.json.return_value = {"job_id": "gnani-job-456", "status": "CREATED"}

    # 2. Start job mock
    resp_start = MagicMock()
    resp_start.status_code = 202
    resp_start.json.return_value = {"job_id": "gnani-job-456", "status": "STARTING"}

    # 3. Get status mock
    resp_status = MagicMock()
    resp_status.status_code = 200
    resp_status.json.return_value = {"status": "COMPLETED", "percent": 100}

    # 4. Get files mock
    resp_files = MagicMock()
    resp_files.status_code = 200
    resp_files.json.return_value = {
        "data": [
            {
                "file_id": "file-1",
                "status": "COMPLETED",
                "transcript_url": "https://s3.amazonaws.com/results/file-1.json",
            }
        ]
    }

    # 5. S3 download mock
    resp_dl = MagicMock()
    resp_dl.status_code = 200
    resp_dl.json.return_value = {
        "full_transcript": "Batch transcription completed with multi-speaker diarization.",
        "duration_seconds": 45.2,
        "model": "prisma-v3.0",
        "language_code": "en-IN",
        "segments": [
            {
                "start_time": 0.5,
                "end_time": 5.0,
                "speaker_id": 1,
                "text": "Batch transcription completed",
                "confidence": 0.95,
                "language_detected": "en-IN",
            },
            {
                "start_time": 5.2,
                "end_time": 9.5,
                "speaker_id": 2,
                "text": "with multi-speaker diarization.",
                "confidence": 0.91,
                "language_detected": "en-IN",
            },
        ],
    }

    with (
        patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_req,
        patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get,
    ):
        mock_req.side_effect = [resp_create, resp_start, resp_status, resp_files]
        mock_get.return_value = resp_dl

        # Create
        job_id = await provider.create_batch_job(b"audio_bytes", "meeting.wav", "en-IN")
        assert job_id == "gnani-job-456"

        # Start
        await provider.start_batch_job(job_id)

        # Status
        status_res = await provider.get_batch_job_status(job_id)
        assert status_res.status == "COMPLETED"
        assert status_res.percent == 100

        # Fetch Transcript
        result = await provider.fetch_batch_transcript(job_id)
        assert "Batch transcription completed" in result.full_transcript
        assert result.total_duration == 45.2
        assert len(result.segments) == 2
        assert result.segments[0].speaker == "Speaker 1"
        assert result.segments[1].speaker == "Speaker 2"


def test_transcript_segment_defaults_and_immutability() -> None:
    # 1. Omitting words produces an empty list
    seg1 = TranscriptSegment(
        start_time=0.0,
        end_time=2.5,
        text="Hello world",
    )
    assert seg1.words == []
    assert isinstance(seg1.words, list)

    # 2. Explicitly supplied list is preserved
    explicit_words = [
        {"word": "Hello", "start": 0.0, "end": 1.0},
        {"word": "world", "start": 1.1, "end": 2.5},
    ]
    seg2 = TranscriptSegment(
        start_time=0.0,
        end_time=2.5,
        text="Hello world",
        words=explicit_words,
    )
    assert seg2.words == explicit_words

    # 3. Separate instances do not share mutable list defaults
    seg3 = TranscriptSegment(
        start_time=2.5,
        end_time=4.0,
        text="Another test",
    )
    seg1.words.append({"word": "mutated", "start": 0.0, "end": 0.5})
    assert len(seg1.words) == 1
    assert len(seg3.words) == 0

    # 4. Model serialization works correctly
    dumped = seg2.model_dump()
    assert dumped["words"] == explicit_words
    json_dumped = seg2.model_dump_json()
    assert "Hello" in json_dumped
    assert "world" in json_dumped


def test_batch_job_status_defaults_and_immutability() -> None:
    # 1. Omitting file_details produces an empty list
    job1 = BatchJobStatus(
        job_id="job-1",
        status="IN_PROGRESS",
    )
    assert job1.file_details == []
    assert isinstance(job1.file_details, list)

    # 2. Explicitly supplied list is preserved
    explicit_files = [{"file_id": "f-1", "status": "COMPLETED"}]
    job2 = BatchJobStatus(
        job_id="job-2",
        status="COMPLETED",
        file_details=explicit_files,
    )
    assert job2.file_details == explicit_files

    # 3. Separate instances do not share mutable list defaults
    job3 = BatchJobStatus(
        job_id="job-3",
        status="STARTING",
    )
    job1.file_details.append({"file_id": "mutated"})
    assert len(job1.file_details) == 1
    assert len(job3.file_details) == 0

    # 4. Model serialization works correctly
    dumped = job2.model_dump()
    assert dumped["file_details"] == explicit_files
    json_dumped = job2.model_dump_json()
    assert "f-1" in json_dumped


def test_stt_result_defaults_and_immutability() -> None:
    # 1. Omitting segments defaults to empty list
    res1 = STTResult(
        provider="mock",
        is_mock=True,
        language="en-IN",
        total_duration=5.0,
        full_transcript="Short transcript",
    )
    assert res1.segments == []

    # 2. Separate instances do not share mutable defaults
    res2 = STTResult(
        provider="mock",
        is_mock=True,
        language="en-IN",
        total_duration=5.0,
        full_transcript="Short transcript",
    )
    res1.segments.append(TranscriptSegment(start_time=0.0, end_time=1.0, text="test"))
    assert len(res1.segments) == 1
    assert len(res2.segments) == 0


def test_gnani_prisma_repr_redacts_credentials() -> None:
    provider = GnaniPrismaSTTProvider(
        api_key="super_secret_gnani_key_xyz123",
        rest_endpoint="https://api.vachana.ai/stt/v3",
        batch_endpoint="https://api.vachana.ai/stt/v3/batch/jobs",
    )
    repr_str = repr(provider)
    assert "super_secret_gnani_key_xyz123" not in repr_str
    assert "GnaniPrismaSTTProvider" in repr_str
    assert "https://api.vachana.ai/stt/v3" in repr_str


@pytest.mark.asyncio
async def test_gnani_prisma_cancel_batch_job_verified() -> None:
    provider = GnaniPrismaSTTProvider(
        api_key="test_key",
        rest_endpoint="https://api.vachana.ai/stt/v3",
        batch_endpoint="https://api.vachana.ai/stt/v3/batch/jobs",
    )

    # 1. 200 OK cancellation response
    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = {
        "job_id": "gnani-job-123",
        "status": "CANCELLED",
        "message": "Job cancelled successfully.",
    }

    with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_resp_200
        success = await provider.cancel_batch_job("gnani-job-123", reason="User stopped")
        assert success is True
        mock_req.assert_called_once()
        called_args = mock_req.call_args
        assert called_args.kwargs["method"] == "POST"
        assert (
            called_args.kwargs["url"]
            == "https://api.vachana.ai/stt/v3/batch/jobs/gnani-job-123/cancel"
        )
        assert called_args.kwargs["json"] == {"reason": "User stopped"}
        assert called_args.kwargs["headers"]["X-API-Key-ID"] == "test_key"

    # 2. 409 Conflict: Already cancelled -> returns True
    mock_resp_409 = MagicMock()
    mock_resp_409.status_code = 409
    mock_resp_409.json.return_value = {"error": "JOB_CANCELLED"}

    with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_resp_409
        success = await provider.cancel_batch_job("gnani-job-123")
        assert success is True

    # 3. HTTP 500 error -> raises ExternalProviderException
    mock_resp_500 = MagicMock()
    mock_resp_500.status_code = 500
    mock_resp_500.text = "Internal Server Error"

    with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_resp_500
        with pytest.raises(ExternalProviderException, match="Failed to cancel Gnani Batch job"):
            await provider.cancel_batch_job("gnani-job-123")


@pytest.mark.asyncio
async def test_gnani_prisma_batch_rejects_files_above_10mb() -> None:
    provider = GnaniPrismaSTTProvider(
        api_key="test_key",
        rest_endpoint="https://api.vachana.ai/stt/v3",
        batch_endpoint="https://api.vachana.ai/stt/v3/batch/jobs",
    )

    oversized_bytes = b"0" * (11 * 1024 * 1024)  # 11 MB
    with pytest.raises(ExternalProviderException, match="exceeds the 10 MB limit"):
        await provider.create_batch_job(
            audio_bytes=oversized_bytes,
            filename="large_recording.wav",
        )


@pytest.mark.asyncio
async def test_gnani_prisma_rest_stt_confidence_none_when_omitted() -> None:
    """FS-03: Verify REST STT sets confidence=None when provider omits confidence score."""
    provider = GnaniPrismaSTTProvider(
        api_key="test_key",
        rest_endpoint="https://api.vachana.ai/stt/v3",
        batch_endpoint="https://api.vachana.ai/stt/v3/batch/jobs",
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "success": True,
        "transcript": "No confidence provided by API",
        "detected_language_code": "en-IN",
        "model": "prisma-v3.0",
    }

    with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_resp
        res = await provider.transcribe_sync(b"audio_bytes", "audio.wav", "en-IN")
        assert len(res.segments) == 1
        assert res.segments[0].confidence is None
        assert res.segments[0].text == "No confidence provided by API"


@pytest.mark.asyncio
async def test_gnani_prisma_rest_stt_confidence_preserved_when_supplied() -> None:
    """FS-03: Verify REST STT preserves genuine provider confidence score when returned."""
    provider = GnaniPrismaSTTProvider(
        api_key="test_key",
        rest_endpoint="https://api.vachana.ai/stt/v3",
        batch_endpoint="https://api.vachana.ai/stt/v3/batch/jobs",
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "success": True,
        "transcript": "Genuine confidence score provided",
        "detected_language_code": "en-IN",
        "model": "prisma-v3.0",
        "confidence": 0.88,
    }

    with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_resp
        res = await provider.transcribe_sync(b"audio_bytes", "audio.wav", "en-IN")
        assert len(res.segments) == 1
        assert res.segments[0].confidence == 0.88


@pytest.mark.asyncio
async def test_transcript_persistence_preserves_none_confidence_for_rest_stt() -> None:
    """FS-03: Verify transcript persistence does not convert missing confidence into 1.0."""
    from app.core.database import SessionLocal
    from app.models.audio_asset import AudioAsset
    from app.models.conversation import Conversation
    from app.models.transcription_job import TranscriptionJob
    from app.models.user import User
    from app.models.workspace import Workspace, WorkspaceMembership
    from app.services.transcription_job_service import TranscriptionJobService

    with SessionLocal() as db:
        user = User(
            email=f"conf_test_{uuid.uuid4()}@example.com",
            hashed_password="pw",
            full_name="Conf Tester",
            is_active=True,
        )
        db.add(user)
        db.flush()

        ws = Workspace(name="Conf WS", slug=f"conf-{uuid.uuid4()}", owner_id=user.id)
        db.add(ws)
        db.flush()
        db.add(WorkspaceMembership(workspace_id=ws.id, user_id=user.id, role="owner"))
        conv = Conversation(workspace_id=ws.id, title="Conf Conv", conversation_type="meeting")
        db.add(conv)
        db.flush()
        asset = AudioAsset(
            workspace_id=ws.id,
            conversation_id=conv.id,
            file_name="test.wav",
            storage_path="path/to/test.wav",
            file_size_bytes=100,
            mime_type="audio/wav",
            duration_seconds=10.0,
            status="ready",
        )
        db.add(asset)
        db.flush()

        job = TranscriptionJob(
            workspace_id=ws.id,
            conversation_id=conv.id,
            audio_asset_id=asset.id,
            job_type="rest",
            status="queued",
        )
        db.add(job)
        db.commit()

        stt_result = STTResult(
            provider="gnani_prisma",
            is_mock=False,
            language="en-IN",
            total_duration=10.0,
            full_transcript="Speech with no confidence provided.",
            segments=[
                TranscriptSegment(
                    start_time=0.0,
                    end_time=10.0,
                    speaker=None,
                    text="Speech with no confidence provided.",
                    confidence=None,  # Missing confidence from provider
                )
            ],
        )

        transcript = TranscriptionJobService.save_transcript_idempotent(
            db=db,
            job=job,
            stt_result=stt_result,
        )
        assert transcript.confidence is None
        assert transcript.confidence != 1.0
