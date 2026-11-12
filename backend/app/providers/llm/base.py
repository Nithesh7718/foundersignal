import asyncio
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
    confidence: float | None = Field(
        None, ge=0.0, le=1.0, description="Extraction confidence score"
    )
    source_quote: str = Field(..., description="Verbatim source excerpt supporting this signal")
    source_speaker: str | None = Field(None, description="Speaker credited with this signal")
    suggested_action: str | None = Field(None, description="Recommended next step if applicable")
    owner: str | None = Field(None, description="Explicitly stated owner, or None")
    deadline: str | None = Field(None, description="Explicitly stated deadline, or None")
    timestamp_start: float | None = Field(None, description="Start timestamp if available")
    timestamp_end: float | None = Field(None, description="End timestamp if available")
    evidence_explanation: str | None = Field(
        None, description="Evidence-based justification linking signal to text"
    )
    item_type: str = Field(
        default="commitment",
        description=(
            "Type: commitment, decision, suggestion, question, completed_action, "
            "uncertain_statement"
        ),
    )


class GeminiCandidateSignal(BaseModel):
    statement: str = Field(
        ...,
        description="Concise statement/title of the action, commitment, or decision",
    )
    item_type: str = Field(
        ...,
        description=(
            "Classification: 'commitment', 'decision', 'suggestion', "
            "'question', 'completed_action', or 'uncertain_statement'"
        ),
    )
    category: str = Field(
        ...,
        description="Category: 'commitment', 'decision', 'blocker', or 'progress'",
    )
    certainty: str = Field(
        ...,
        description="Certainty rating: 'confirmed_fact', 'inferred', or 'unknown'",
    )
    source_quote: str = Field(
        ...,
        description=(
            "Verbatim excerpt from transcript supporting statement. Must be exact substring."
        ),
    )
    source_speaker: str | None = Field(
        None,
        description="Speaker name if explicitly identifiable in transcript; otherwise null.",
    )
    owner: str | None = Field(
        None,
        description="Explicitly named individual responsible if stated; otherwise null.",
    )
    deadline: str | None = Field(
        None,
        description="Explicit date or time deadline if stated in transcript; otherwise null.",
    )
    confidence: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Defensible confidence between 0.0 and 1.0 based on text. Null if uncertain.",
    )
    evidence_explanation: str | None = Field(
        None,
        description="Evidence-based explanation linking this item directly to source text.",
    )
    suggested_action: str | None = Field(
        None,
        description="Recommended operational next step if applicable; otherwise null.",
    )


class GeminiExtractionResponse(BaseModel):
    signals: list[GeminiCandidateSignal] = Field(
        default_factory=list,
        description="List of extracted signals from the transcript.",
    )


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
        if not transcript_text or not transcript_text.strip():
            return ExtractionResult(
                provider=self.provider_name,
                is_mock=True,
                model_name="mock-extractor-v1",
                signals=[],
                metadata={"processed_chars": 0},
            )

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
                    owner=None,
                    deadline="Thursday",
                    evidence_explanation=(
                        "Founder explicitly proposed preparing onboarding flow "
                        "before Thursday review."
                    ),
                    item_type="commitment",
                )
            ],
            metadata={"processed_chars": len(transcript_text)},
        )


class GeminiLLMProvider(LLMProvider):
    """Google Gemini LLM Provider for structured commitment extraction using google-genai SDK."""

    def __init__(
        self,
        api_key: str,
        model_name: str | None = None,
        max_retries: int = 3,
        base_retry_delay: float = 1.0,
    ) -> None:
        if not api_key or not api_key.strip():
            raise ExternalProviderException(
                provider="gemini",
                message="API key for Gemini LLM provider is not configured.",
            )
        self._api_key = api_key.strip()
        self.model_name = (model_name or settings.GEMINI_MODEL or "gemini-3.8-flash").strip()
        self.max_retries = max_retries
        self.base_retry_delay = base_retry_delay
        self._client: Any = None

    def __repr__(self) -> str:
        return f"<GeminiLLMProvider model='{self.model_name}'>"

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def is_mock(self) -> bool:
        return False

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from google import genai

                self._client = genai.Client(api_key=self._api_key)
            except Exception as exc:
                raise ExternalProviderException(
                    provider="gemini",
                    message=f"Failed to initialize Google GenAI client: {exc}",
                ) from exc
        return self._client

    async def extract_signals(
        self,
        transcript_text: str,
        context: dict[str, Any] | None = None,
    ) -> ExtractionResult:
        if not transcript_text or not transcript_text.strip():
            return ExtractionResult(
                provider=self.provider_name,
                is_mock=False,
                model_name=self.model_name,
                signals=[],
                metadata={"processed_chars": 0},
            )

        client = self._get_client()
        from google.genai import errors, types

        prompt = self._build_prompt(transcript_text, context)

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=GeminiExtractionResponse,
            temperature=0.1,
        )

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await client.aio.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config,
                )
                break
            except errors.APIError as exc:
                last_error = exc
                is_transient = exc.code in (429, 500, 502, 503, 504) or isinstance(
                    exc, errors.ServerError
                )
                if is_transient and attempt < self.max_retries:
                    await asyncio.sleep(self.base_retry_delay * (2 ** (attempt - 1)))
                    continue
                error_msg = getattr(exc, "message", None) or str(exc)
                raise ExternalProviderException(
                    provider="gemini",
                    message=f"Gemini API error ({exc.code}): {error_msg}",
                ) from exc
            except TimeoutError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    await asyncio.sleep(self.base_retry_delay * (2 ** (attempt - 1)))
                    continue
                raise ExternalProviderException(
                    provider="gemini",
                    message="Gemini API request timed out.",
                ) from exc
            except Exception as exc:
                raise ExternalProviderException(
                    provider="gemini",
                    message=f"Unexpected error communicating with Gemini: {exc}",
                ) from exc
        else:
            raise ExternalProviderException(
                provider="gemini",
                message=(
                    f"Gemini API request failed after {self.max_retries} attempts: {last_error}"
                ),
            )

        raw_text = (response.text or "").strip()
        if not raw_text:
            return ExtractionResult(
                provider=self.provider_name,
                is_mock=False,
                model_name=self.model_name,
                signals=[],
                metadata={"processed_chars": len(transcript_text), "raw_response_empty": True},
            )

        clean_text = raw_text
        if clean_text.startswith("```"):
            lines = clean_text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            clean_text = "\n".join(lines).strip()

        try:
            parsed = GeminiExtractionResponse.model_validate_json(clean_text)
        except Exception as exc:
            raise ExternalProviderException(
                provider="gemini",
                message=f"Failed to parse structured JSON response from Gemini: {exc}",
            ) from exc

        signals: list[ExtractedSignal] = []
        for cand in parsed.signals:
            raw_quote = cand.source_quote.strip()
            quote_cand = raw_quote
            if quote_cand.startswith(('"', "'", "“")) and quote_cand.endswith(('"', "'", "”")):
                quote_cand = quote_cand[1:-1].strip()

            # Verbatim check: candidate quote must be an exact substring of transcript
            if quote_cand not in transcript_text:
                continue

            signals.append(
                ExtractedSignal(
                    category=cand.category,
                    statement=cand.statement,
                    certainty=cand.certainty,
                    confidence=cand.confidence,
                    source_quote=quote_cand,
                    source_speaker=cand.source_speaker,
                    suggested_action=cand.suggested_action,
                    owner=cand.owner,
                    deadline=cand.deadline,
                    evidence_explanation=cand.evidence_explanation,
                    item_type=cand.item_type,
                )
            )

        return ExtractionResult(
            provider=self.provider_name,
            is_mock=False,
            model_name=self.model_name,
            signals=signals,
            metadata={"processed_chars": len(transcript_text)},
        )

    def _build_prompt(self, transcript_text: str, context: dict[str, Any] | None) -> str:
        ctx_title = (context or {}).get("title", "Business Conversation")
        return (
            "You are the structured extraction engine of FounderSignal, an AI operating "
            "companion for founders.\n"
            "Extract commitments, decisions, and factual statements from the following "
            "conversation transcript.\n\n"
            f"CONVERSATION CONTEXT:\nTitle: {ctx_title}\n\n"
            "STRICT EXTRACTION RULES:\n"
            "1. EVIDENCE OVER ASSUMPTIONS: Every item must have an exact, verbatim 'source_quote' "
            "from the transcript.\n"
            "2. NO HALLUCINATIONS: Never invent owners, deadlines, monetary figures, or actions.\n"
            "   - If no specific owner is explicitly stated for an item, set 'owner' to null.\n"
            "   - If no specific deadline is explicitly stated for an item, set 'deadline' "
            "to null.\n"
            "   - If the speaker is not identifiable from the text, set 'source_speaker' "
            "to null.\n"
            "3. PRECISE CLASSIFICATION:\n"
            "   - 'item_type' must be one of: 'commitment', 'decision', 'suggestion', "
            "'question', 'completed_action', 'uncertain_statement'.\n"
            "   - Do NOT classify questions, suggestions, or past completed actions as "
            "'commitment'.\n"
            "   - Only classify an item as 'commitment' if a participant explicitly agrees or "
            "promises to perform future work.\n"
            "4. CONFIDENCE SCORE:\n"
            "   - Provide 'confidence' between 0.0 and 1.0 based solely on how clearly and "
            "unambiguously the text states the commitment.\n"
            "   - If ambiguous, hypothetical, or vague, set confidence to null or a low value.\n"
            "5. EXPLANATION:\n"
            "   - Provide an 'evidence_explanation' detailing why the source quote justifies "
            "this extraction.\n\n"
            f'TRANSCRIPT TO ANALYZE:\n"""\n{transcript_text}\n"""\n'
        )


def get_llm_provider() -> LLMProvider:
    """Factory for selecting LLM provider based on configuration."""
    if settings.is_production and (
        settings.MOCK_PROVIDERS or settings.LLM_PROVIDER.lower() == "mock"
    ):
        raise RuntimeError("Mock LLM provider cannot be used in production mode.")

    if settings.MOCK_PROVIDERS or settings.LLM_PROVIDER.lower() == "mock":
        return MockLLMProvider()

    provider_name = settings.LLM_PROVIDER.lower()
    if provider_name == "gemini":
        api_key = settings.GEMINI_API_KEY or settings.LLM_API_KEY
        if not api_key:
            raise ExternalProviderException(
                provider="gemini",
                message="API key for LLM provider 'gemini' is not configured.",
            )
        return GeminiLLMProvider(
            api_key=api_key,
            model_name=settings.GEMINI_MODEL,
        )

    if provider_name in ["openai", "anthropic"]:
        if not settings.LLM_API_KEY:
            raise ExternalProviderException(
                provider=provider_name,
                message=f"API key for LLM provider '{provider_name}' is not configured.",
            )
        raise NotImplementedError(
            f"Production adapter for LLM provider '{provider_name}' requires live API credentials."
        )

    raise ExternalProviderException(
        provider="llm",
        message=f"Unsupported LLM provider '{settings.LLM_PROVIDER}'.",
    )
