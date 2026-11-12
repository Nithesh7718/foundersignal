import hashlib
import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.models.commitment import Commitment
from app.models.transcript import Transcript
from app.providers.llm.base import LLMProvider, get_llm_provider
from app.schemas.commitment import (
    VALID_COMMITMENT_STATUSES,
    VALID_COMMITMENT_TRANSITIONS,
    CommitmentCreate,
    CommitmentUpdate,
)
from app.services.conversation_service import ConversationService

logger = logging.getLogger(__name__)

STOP_WORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "but",
    "if",
    "then",
    "to",
    "for",
    "of",
    "at",
    "by",
    "from",
    "up",
    "about",
    "into",
    "over",
    "after",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "shall",
    "should",
    "may",
    "might",
    "must",
    "can",
    "could",
    "let",
    "lets",
    "our",
    "my",
    "your",
    "his",
    "her",
    "their",
    "we",
    "i",
    "you",
    "he",
    "she",
    "it",
    "they",
    "this",
    "that",
    "these",
    "those",
}


def normalize_action_tokens(text: str) -> str:
    """Normalize text into sorted significant tokens to prevent near-duplicate extractions."""
    cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text.lower())
    tokens = [w for w in cleaned.split() if w not in STOP_WORDS and len(w) > 1]
    if not tokens:
        tokens = cleaned.split()
    return " ".join(sorted(tokens))


def compute_evidence_hash(conversation_id: uuid.UUID, source_quote: str, title: str) -> str:
    """Compute stable SHA-256 fingerprint from conversation, quote, and core action tokens."""
    norm_quote = " ".join(source_quote.strip().lower().split())
    norm_action = normalize_action_tokens(title)
    raw = f"{conversation_id}:{norm_quote}:{norm_action}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class CommitmentService:
    """Business logic for extracted commitments, founder review, and status transitions."""

    @staticmethod
    def list_commitments(
        db: Session,
        workspace_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> Sequence[Commitment]:
        """List all commitments for a specific conversation."""
        # Verify conversation belongs to the workspace
        ConversationService.get_conversation(db, workspace_id, conversation_id)

        stmt = (
            select(Commitment)
            .where(
                Commitment.workspace_id == workspace_id,
                Commitment.conversation_id == conversation_id,
            )
            .order_by(Commitment.created_at.asc())
        )
        return db.execute(stmt).scalars().all()

    @staticmethod
    def get_commitment(
        db: Session,
        workspace_id: uuid.UUID,
        commitment_id: uuid.UUID,
    ) -> Commitment:
        """Fetch a single commitment enforcing workspace boundary."""
        stmt = select(Commitment).where(
            Commitment.id == commitment_id,
            Commitment.workspace_id == workspace_id,
        )
        commitment = db.execute(stmt).scalar_one_or_none()
        if not commitment:
            raise NotFoundException("Commitment not found in this workspace.")
        return commitment

    @staticmethod
    def create_commitment(
        db: Session,
        workspace_id: uuid.UUID,
        conversation_id: uuid.UUID,
        commitment_in: CommitmentCreate,
        role: str | None = None,
    ) -> Commitment:
        """Create a commitment attached to a conversation."""
        if role is not None and role not in ("owner", "admin", "member"):
            raise ForbiddenException(
                "You do not have permission to create commitments in this workspace."
            )

        ConversationService.get_conversation(db, workspace_id, conversation_id)

        if commitment_in.status not in VALID_COMMITMENT_STATUSES:
            allowed = ", ".join(sorted(VALID_COMMITMENT_STATUSES))
            raise ValidationException(
                f"Invalid status '{commitment_in.status}'. Allowed: {allowed}"
            )

        ev_hash = commitment_in.evidence_hash or compute_evidence_hash(
            conversation_id, commitment_in.source_quote, commitment_in.title
        )

        commitment = Commitment(
            workspace_id=workspace_id,
            conversation_id=conversation_id,
            title=commitment_in.title.strip(),
            description=commitment_in.description.strip() if commitment_in.description else None,
            status=commitment_in.status,
            confidence_score=commitment_in.confidence_score,
            source_quote=commitment_in.source_quote.strip(),
            speaker=commitment_in.speaker.strip() if commitment_in.speaker else None,
            timestamp_start=commitment_in.timestamp_start,
            timestamp_end=commitment_in.timestamp_end,
            assignee_id=commitment_in.assignee_id,
            due_date=commitment_in.due_date,
            evidence_hash=ev_hash,
        )
        db.add(commitment)
        try:
            db.commit()
            db.refresh(commitment)
        except IntegrityError as exc:
            db.rollback()
            raise ConflictException(
                "A commitment with this evidence quote already exists for this conversation."
            ) from exc

        return commitment

    @staticmethod
    def update_commitment(
        db: Session,
        workspace_id: uuid.UUID,
        commitment_id: uuid.UUID,
        update_in: CommitmentUpdate,
        user_id: uuid.UUID | None = None,
        role: str | None = None,
    ) -> Commitment:
        """Update commitment fields, founder review decisions, and lifecycle transitions."""
        if role is not None and role not in ("owner", "admin", "member"):
            raise ForbiddenException("You do not have permission to update commitments.")

        # Row-level locking to prevent concurrent race conditions on lifecycle transitions
        stmt = (
            select(Commitment)
            .where(
                Commitment.id == commitment_id,
                Commitment.workspace_id == workspace_id,
            )
            .with_for_update()
        )
        commitment = db.execute(stmt).scalar_one_or_none()
        if not commitment:
            raise NotFoundException("Commitment not found in this workspace.")

        if update_in.status is not None and update_in.status != commitment.status:
            current_status = commitment.status
            new_status = update_in.status

            if new_status not in VALID_COMMITMENT_STATUSES:
                allowed = ", ".join(sorted(VALID_COMMITMENT_STATUSES))
                raise ValidationException(f"Invalid status '{new_status}'. Allowed: {allowed}")

            # Terminal state guard: completed commitments cannot transition to any other state
            if current_status == "completed":
                raise ValidationException(
                    "Completed commitments are final and cannot be transitioned to any other state."
                )

            allowed_transitions = VALID_COMMITMENT_TRANSITIONS.get(current_status, set())
            if new_status not in allowed_transitions:
                allowed_str = ", ".join(sorted(allowed_transitions)) or "none"
                raise ValidationException(
                    f"Invalid state transition from '{current_status}' to '{new_status}'. "
                    f"Allowed transitions from '{current_status}': {allowed_str}."
                )

            # Enforce Role-Based Access Control on Founder Approval / Rejection
            if new_status in ("confirmed", "rejected"):
                if role is not None and role not in ("owner", "admin"):
                    raise ForbiddenException(
                        "Only workspace owners and admins can confirm or reject commitments."
                    )
                commitment.status = new_status
                commitment.reviewed_by_id = user_id
                commitment.reviewed_at = datetime.now(UTC)
            elif current_status == "rejected" and new_status == "inferred":
                # Explicit reopen action
                if role is not None and role not in ("owner", "admin"):
                    raise ForbiddenException(
                        "Only workspace owners and admins can reopen rejected commitments."
                    )
                commitment.status = new_status
                commitment.reviewed_by_id = None
                commitment.reviewed_at = None
            else:
                commitment.status = new_status

        if update_in.title is not None:
            commitment.title = update_in.title.strip()

        if update_in.description is not None:
            desc = update_in.description.strip() if update_in.description else None
            commitment.description = desc

        if update_in.due_date is not None:
            commitment.due_date = update_in.due_date

        if update_in.assignee_id is not None:
            commitment.assignee_id = update_in.assignee_id

        db.commit()
        db.refresh(commitment)
        return commitment

    @staticmethod
    async def extract_commitments_from_transcript(
        db: Session,
        workspace_id: uuid.UUID,
        conversation_id: uuid.UUID,
        llm_provider: LLMProvider | None = None,
        role: str | None = None,
    ) -> list[Commitment]:
        """Extract commitments and decisions from conversation transcript using LLM extraction."""
        if role is not None and role not in ("owner", "admin", "member"):
            raise ForbiddenException(
                "You do not have permission to extract commitments in this workspace."
            )

        conversation = ConversationService.get_conversation(db, workspace_id, conversation_id)

        # Retrieve completed transcript
        stmt = (
            select(Transcript)
            .where(
                Transcript.conversation_id == conversation.id,
                Transcript.workspace_id == workspace_id,
                Transcript.status == "completed",
            )
            .order_by(Transcript.created_at.desc())
        )
        transcript = db.execute(stmt).scalars().first()
        if not transcript:
            raise ValidationException(
                "No completed transcript found for this conversation. "
                "Transcription must complete before extracting commitments."
            )

        if not transcript.raw_transcript or not transcript.raw_transcript.strip():
            return []

        provider = llm_provider or get_llm_provider()
        extraction_result = await provider.extract_signals(
            transcript_text=transcript.raw_transcript,
            context={"conversation_id": str(conversation_id), "title": conversation.title},
        )

        # Retrieve existing fingerprints to ensure idempotency across repeated extractions
        existing_hashes_stmt = select(Commitment.evidence_hash).where(
            Commitment.conversation_id == conversation.id,
            Commitment.evidence_hash.is_not(None),
        )
        existing_hashes = set(db.execute(existing_hashes_stmt).scalars().all())

        extracted_commitments: list[Commitment] = []
        seen_batch_hashes: set[str] = set()

        excluded_item_types = {"question", "suggestion", "completed_action", "uncertain_statement"}
        valid_cats = {"commitment", "decision", "action_item", "progress", "blocker"}

        for signal in extraction_result.signals:
            # Rule: Questions, suggestions, and completed actions must not become commitments
            if signal.item_type in excluded_item_types:
                continue

            if signal.category.lower() not in valid_cats:
                continue

            if not signal.source_quote or not signal.source_quote.strip():
                continue

            quote_text = signal.source_quote.strip()
            if quote_text not in transcript.raw_transcript:
                logger.warning(
                    f"Discarding candidate commitment '{signal.statement}': "
                    "source quote not found verbatim in transcript."
                )
                continue

            ev_hash = compute_evidence_hash(conversation.id, signal.source_quote, signal.statement)

            # Skip duplicate if already present in DB or earlier in current extraction batch
            if ev_hash in existing_hashes or ev_hash in seen_batch_hashes:
                continue
            seen_batch_hashes.add(ev_hash)

            desc = (
                signal.suggested_action.strip()
                if signal.suggested_action
                else (signal.evidence_explanation.strip() if signal.evidence_explanation else None)
            )

            new_commitment = Commitment(
                workspace_id=workspace_id,
                conversation_id=conversation.id,
                title=signal.statement.strip(),
                description=desc,
                # Principle 4: Inferred until founder explicitly confirms
                status="inferred",
                confidence_score=signal.confidence,
                source_quote=signal.source_quote.strip(),
                speaker=signal.source_speaker.strip() if signal.source_speaker else None,
                evidence_hash=ev_hash,
            )
            db.add(new_commitment)
            extracted_commitments.append(new_commitment)

        if extracted_commitments:
            try:
                db.commit()
                for item in extracted_commitments:
                    db.refresh(item)
            except IntegrityError as exc:
                db.rollback()
                err_msg = str(getattr(exc, "orig", exc)).lower()
                pgcode = getattr(getattr(exc, "orig", None), "pgcode", None)
                is_unique_violation = (
                    pgcode == "23505"
                    or "uq_commitments_conv_evidence_hash" in err_msg
                    or "evidence_hash" in err_msg
                    or "unique constraint" in err_msg
                )
                if is_unique_violation:
                    # Idempotency race: another worker/request committed concurrently
                    return list(
                        CommitmentService.list_commitments(db, workspace_id, conversation_id)
                    )
                # Unrelated database integrity failure must be re-raised
                raise

        return extracted_commitments

    @staticmethod
    def delete_commitment(
        db: Session,
        workspace_id: uuid.UUID,
        commitment_id: uuid.UUID,
        role: str | None = None,
    ) -> None:
        """Delete a commitment record. Restricted to workspace owners and admins."""
        if role is not None and role not in ("owner", "admin"):
            raise ForbiddenException("Only workspace owners and admins can delete commitments.")

        commitment = CommitmentService.get_commitment(db, workspace_id, commitment_id)
        db.delete(commitment)
        db.commit()
