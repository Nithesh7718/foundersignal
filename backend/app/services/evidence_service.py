import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.commitment import Commitment
from app.models.conversation import Conversation
from app.models.project import Project
from app.schemas.evidence import EvidenceGraphResponse, GraphEdge, GraphNode


class EvidenceService:
    @staticmethod
    def get_evidence_graph(db: Session, workspace_id: uuid.UUID) -> EvidenceGraphResponse:
        """Construct a complete, strictly tenant-isolated evidence graph for the workspace."""
        # 1. Load conversations with audio assets and transcripts
        conv_stmt = (
            select(Conversation)
            .where(Conversation.workspace_id == workspace_id)
            .options(
                selectinload(Conversation.audio_assets),
                selectinload(Conversation.transcripts),
            )
            .order_by(Conversation.recorded_at.desc())
        )
        conversations = db.execute(conv_stmt).scalars().all()

        # 2. Load commitments
        comm_stmt = (
            select(Commitment)
            .where(Commitment.workspace_id == workspace_id)
            .order_by(Commitment.created_at.desc())
        )
        commitments = db.execute(comm_stmt).scalars().all()

        # 3. Load projects
        proj_stmt = (
            select(Project)
            .where(Project.workspace_id == workspace_id)
            .order_by(Project.created_at.desc())
        )
        projects = db.execute(proj_stmt).scalars().all()

        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []
        seen_speakers: set[str] = set()

        total_audio = 0
        total_transcripts = 0

        # Conversation, Audio, and Transcript nodes
        for conv in conversations:
            conv_node_id = f"conv_{conv.id}"
            nodes.append(
                GraphNode(
                    id=conv_node_id,
                    label=conv.title,
                    type="conversation",
                    metadata={
                        "id": str(conv.id),
                        "title": conv.title,
                        "conversation_type": conv.conversation_type,
                        "status": conv.status,
                        "recorded_at": conv.recorded_at.isoformat() if conv.recorded_at else None,
                    },
                )
            )

            for audio in conv.audio_assets:
                total_audio += 1
                audio_node_id = f"audio_{audio.id}"
                nodes.append(
                    GraphNode(
                        id=audio_node_id,
                        label=audio.file_name,
                        type="audio",
                        metadata={
                            "id": str(audio.id),
                            "file_name": audio.file_name,
                            "mime_type": audio.mime_type,
                            "file_size_bytes": audio.file_size_bytes,
                            "duration_seconds": audio.duration_seconds,
                            "conversation_id": str(conv.id),
                        },
                    )
                )
                edges.append(
                    GraphEdge(
                        id=f"e_{conv_node_id}_{audio_node_id}",
                        source=conv_node_id,
                        target=audio_node_id,
                        label="has_audio",
                        type="has_audio",
                    )
                )

            for transcript in conv.transcripts:
                total_transcripts += 1
                tr_node_id = f"transcript_{transcript.id}"
                snippet = (
                    transcript.raw_transcript[:120] + "..."
                    if transcript.raw_transcript and len(transcript.raw_transcript) > 120
                    else (transcript.raw_transcript or "")
                )
                nodes.append(
                    GraphNode(
                        id=tr_node_id,
                        label=f"Transcript ({transcript.language_code or 'en'})",
                        type="transcript",
                        metadata={
                            "id": str(transcript.id),
                            "language": transcript.language_code,
                            "confidence": transcript.confidence,
                            "snippet": snippet,
                            "conversation_id": str(conv.id),
                        },
                    )
                )
                edges.append(
                    GraphEdge(
                        id=f"e_{conv_node_id}_{tr_node_id}",
                        source=conv_node_id,
                        target=tr_node_id,
                        label="has_transcript",
                        type="has_transcript",
                    )
                )

        # Project nodes
        project_ids = set()
        for proj in projects:
            proj_node_id = f"proj_{proj.id}"
            project_ids.add(proj.id)
            nodes.append(
                GraphNode(
                    id=proj_node_id,
                    label=proj.name,
                    type="project",
                    metadata={
                        "id": str(proj.id),
                        "name": proj.name,
                        "status": proj.status,
                        "description": proj.description,
                        "target_date": proj.target_date.isoformat() if proj.target_date else None,
                    },
                )
            )

        # Commitment nodes and edges
        for comm in commitments:
            comm_node_id = f"comm_{comm.id}"
            nodes.append(
                GraphNode(
                    id=comm_node_id,
                    label=comm.title,
                    type="commitment",
                    metadata={
                        "id": str(comm.id),
                        "title": comm.title,
                        "status": comm.status,
                        "confidence_score": comm.confidence_score,
                        "source_quote": comm.source_quote,
                        "speaker": comm.speaker,
                        "due_date": comm.due_date.isoformat() if comm.due_date else None,
                        "conversation_id": str(comm.conversation_id),
                        "project_id": str(comm.project_id) if comm.project_id else None,
                    },
                )
            )

            # Edge to conversation
            conv_node_id = f"conv_{comm.conversation_id}"
            edges.append(
                GraphEdge(
                    id=f"e_{conv_node_id}_{comm_node_id}",
                    source=conv_node_id,
                    target=comm_node_id,
                    label="extracted_from",
                    type="extracted_from",
                )
            )

            # Edge to project if assigned
            if comm.project_id and comm.project_id in project_ids:
                proj_node_id = f"proj_{comm.project_id}"
                edges.append(
                    GraphEdge(
                        id=f"e_{comm_node_id}_{proj_node_id}",
                        source=comm_node_id,
                        target=proj_node_id,
                        label="assigned_to_project",
                        type="assigned_to_project",
                    )
                )

            # Speaker node & edge if present
            if comm.speaker:
                clean_speaker = comm.speaker.strip()
                speaker_id = f"speaker_{clean_speaker.lower().replace(' ', '_')}"
                if clean_speaker not in seen_speakers:
                    seen_speakers.add(clean_speaker)
                    nodes.append(
                        GraphNode(
                            id=speaker_id,
                            label=clean_speaker,
                            type="speaker",
                            metadata={"name": clean_speaker},
                        )
                    )
                edges.append(
                    GraphEdge(
                        id=f"e_{comm_node_id}_{speaker_id}",
                        source=comm_node_id,
                        target=speaker_id,
                        label="spoken_by",
                        type="spoken_by",
                    )
                )

        return EvidenceGraphResponse(
            workspace_id=workspace_id,
            nodes=nodes,
            edges=edges,
            total_conversations=len(conversations),
            total_audio_assets=total_audio,
            total_transcripts=total_transcripts,
            total_commitments=len(commitments),
            total_projects=len(projects),
        )
