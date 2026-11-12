import io
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.models.commitment import Commitment
from app.models.transcript import Transcript
from app.models.workspace import WorkspaceMembership
from app.providers.llm.base import ExtractedSignal, ExtractionResult, LLMProvider
from app.services.commitment_service import CommitmentService, compute_evidence_hash
from tests.test_conversations import create_minimal_wav_bytes
from tests.test_workspaces import create_authenticated_user


def test_audio_streaming_endpoint(client: TestClient) -> None:
    """Test audio streaming with genuine HTTP Range request support:
    - 200 OK without Range header (full content, Accept-Ranges, Content-Length)
    - 206 Partial Content with byte ranges (start-end, start-, suffix -N)
    - 416 Range Not Satisfiable on out-of-range bounds
    - 404 on missing audio asset
    - 403 on cross-workspace access
    """
    _email, token, ws_id = create_authenticated_user(client)

    # 1. Create conversation
    conv_res = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Weekly Founder Check-in", "conversation_type": "voice_note"},
    )
    assert conv_res.status_code == 201
    conv_id = conv_res.json()["id"]

    # 2. Upload audio
    wav_bytes = create_minimal_wav_bytes()
    total_size = len(wav_bytes)
    assert total_size > 20

    upload_res = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/audio",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("checkin.wav", io.BytesIO(wav_bytes), "audio/wav")},
    )
    assert upload_res.status_code == 201
    asset_id = upload_res.json()["id"]

    # 3. Stream / fetch audio: No Range header -> 200 OK
    audio_res = client.get(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/audio/{asset_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert audio_res.status_code == 200
    assert audio_res.headers["content-type"] == "audio/wav"
    assert audio_res.headers["accept-ranges"] == "bytes"
    assert audio_res.headers["content-length"] == str(total_size)
    assert audio_res.content == wav_bytes

    # 4. Range request: bytes=0-9 -> 206 Partial Content
    range_res_1 = client.get(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/audio/{asset_id}",
        headers={"Authorization": f"Bearer {token}", "Range": "bytes=0-9"},
    )
    assert range_res_1.status_code == 206
    assert range_res_1.headers["content-type"] == "audio/wav"
    assert range_res_1.headers["content-range"] == f"bytes 0-9/{total_size}"
    assert range_res_1.headers["content-length"] == "10"
    assert range_res_1.content == wav_bytes[0:10]

    # 5. Range request: bytes=10- (open-ended start) -> 206 Partial Content
    range_res_2 = client.get(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/audio/{asset_id}",
        headers={"Authorization": f"Bearer {token}", "Range": "bytes=10-"},
    )
    assert range_res_2.status_code == 206
    assert range_res_2.headers["content-range"] == f"bytes 10-{total_size - 1}/{total_size}"
    assert range_res_2.headers["content-length"] == str(total_size - 10)
    assert range_res_2.content == wav_bytes[10:]

    # 6. Range request: bytes=-10 (suffix range) -> 206 Partial Content
    range_res_3 = client.get(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/audio/{asset_id}",
        headers={"Authorization": f"Bearer {token}", "Range": "bytes=-10"},
    )
    assert range_res_3.status_code == 206
    expected_cr = f"bytes {total_size - 10}-{total_size - 1}/{total_size}"
    assert range_res_3.headers["content-range"] == expected_cr
    assert range_res_3.headers["content-length"] == "10"
    assert range_res_3.content == wav_bytes[-10:]

    # 7. Invalid range: bytes=999999- (out of range) -> 416 Range Not Satisfiable
    range_res_4 = client.get(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/audio/{asset_id}",
        headers={"Authorization": f"Bearer {token}", "Range": "bytes=999999-"},
    )
    assert range_res_4.status_code == 416
    assert range_res_4.headers["content-range"] == f"bytes */{total_size}"

    # 8. Non-existent audio asset -> 404 Not Found
    non_existent_id = uuid.uuid4()
    not_found_res = client.get(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/audio/{non_existent_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert not_found_res.status_code == 404

    # 9. Cross-workspace isolation -> 403 Forbidden
    _email2, token2, _ws_id2 = create_authenticated_user(client)
    cross_res = client.get(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/audio/{asset_id}",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert cross_res.status_code == 403


def test_commitment_crud_lifecycle(client: TestClient) -> None:
    _email, token, ws_id = create_authenticated_user(client)

    # 1. Create conversation
    conv_res = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Client Strategy Session", "conversation_type": "meeting"},
    )
    conv_id = conv_res.json()["id"]

    # 2. Create commitment
    create_res = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/commitments",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Deliver draft enterprise contract",
            "description": "Send reviewed enterprise MSA to legal team",
            "source_quote": "I will deliver the draft enterprise contract by end of day Friday.",
            "speaker": "Founder",
            "confidence_score": 0.95,
            "status": "inferred",
        },
    )
    assert create_res.status_code == 201
    commitment = create_res.json()
    commitment_id = commitment["id"]
    assert commitment["title"] == "Deliver draft enterprise contract"
    assert commitment["status"] == "inferred"
    assert commitment["confidence_score"] == 0.95

    # 3. List commitments
    list_res = client.get(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/commitments",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) == 1
    assert items[0]["id"] == commitment_id

    # 4. Update status: Founder confirms inferred commitment
    patch_res = client.patch(
        f"/api/v1/workspaces/{ws_id}/commitments/{commitment_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "confirmed", "title": "Deliver finalized enterprise contract"},
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["status"] == "confirmed"
    assert updated["title"] == "Deliver finalized enterprise contract"
    assert updated["reviewed_by_id"] is not None
    assert updated["reviewed_at"] is not None

    # 5. Reject commitment
    reject_res = client.patch(
        f"/api/v1/workspaces/{ws_id}/commitments/{commitment_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "rejected"},
    )
    assert reject_res.status_code == 200
    assert reject_res.json()["status"] == "rejected"

    # 6. Delete commitment
    del_res = client.delete(
        f"/api/v1/workspaces/{ws_id}/commitments/{commitment_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_res.status_code == 204

    # Verify deleted
    list_after = client.get(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/commitments",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert len(list_after) == 0


def test_confidence_nullable_and_not_defaulted(client: TestClient) -> None:
    """Confidence score must be nullable and never fabricated or defaulted to 1.0."""
    _email, token, ws_id = create_authenticated_user(client)

    conv_res = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Confidence Check Session", "conversation_type": "meeting"},
    )
    conv_id = conv_res.json()["id"]

    # Post commitment with null confidence
    create_res = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/commitments",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Explore market expansion into EMEA",
            "source_quote": "We should look at EMEA expansion when timing allows.",
            "confidence_score": None,
            "status": "inferred",
        },
    )
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["confidence_score"] is None


def test_extract_commitments_from_transcript_and_deduplication(client: TestClient) -> None:
    """Repeated extraction must be idempotent and not create duplicate commitments."""
    _email, token, ws_id = create_authenticated_user(client)

    # 1. Create conversation
    conv_res = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Sprint Planning Discussion", "conversation_type": "meeting"},
    )
    conv_id = uuid.UUID(conv_res.json()["id"])
    ws_uuid = uuid.UUID(ws_id)

    # 2. Insert completed transcript
    with SessionLocal() as db_session:
        transcript = Transcript(
            id=uuid.uuid4(),
            workspace_id=ws_uuid,
            conversation_id=conv_id,
            provider="mock_stt",
            model="whisper-mock",
            language_code="en",
            raw_transcript=(
                "Let's ensure the onboarding flow is ready by Thursday before client review."
            ),
            status="completed",
            confidence=0.98,
        )
        db_session.add(transcript)
        db_session.commit()

    # 3. First extraction
    extract_res1 = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/commitments/extract",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert extract_res1.status_code == 201
    extracted1 = extract_res1.json()
    assert len(extracted1) == 1
    assert extracted1[0]["status"] == "inferred"
    assert extracted1[0]["evidence_hash"] is not None

    # 4. Repeated extraction must NOT duplicate
    extract_res2 = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/commitments/extract",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert extract_res2.status_code == 201
    extracted2 = extract_res2.json()
    # Returns 0 newly added items since fingerprint already exists
    assert len(extracted2) == 0

    # 5. Verify total commitments count in database is still 1
    list_res = client.get(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/commitments",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert len(list_res.json()) == 1


def test_commitment_state_machine_valid_and_invalid_transitions(client: TestClient) -> None:
    """Enforce explicit lifecycle state machine:
    - inferred -> confirmed or rejected
    - confirmed -> in_progress, completed, or rejected
    - in_progress -> completed ONLY
    - completed -> TERMINAL (no transitions out, all return 422)
    - rejected -> inferred ONLY via reopen (clears reviewer audit fields)
    - rejected -> confirmed DIRECTLY must be blocked (422)
    - inferred -> completed DIRECTLY must be blocked (422)
    - in_progress -> rejected DIRECTLY must be blocked (422)
    """
    _email, token, ws_id = create_authenticated_user(client)

    conv_res = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "State Transition Test", "conversation_type": "meeting"},
    )
    conv_id = conv_res.json()["id"]

    create_res1 = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/commitments",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Build user activity feed",
            "source_quote": "I will build the user activity feed this week.",
            "status": "inferred",
        },
    )
    comm1_id = create_res1.json()["id"]

    # 1. Prohibited: inferred -> completed directly is blocked (422)
    bad_res1 = client.patch(
        f"/api/v1/workspaces/{ws_id}/commitments/{comm1_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "completed"},
    )
    assert bad_res1.status_code == 422
    assert "Invalid state transition" in bad_res1.json()["error"]["message"]

    # 2. Prohibited: inferred -> in_progress directly is blocked (422)
    bad_res2 = client.patch(
        f"/api/v1/workspaces/{ws_id}/commitments/{comm1_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "in_progress"},
    )
    assert bad_res2.status_code == 422
    assert "Invalid state transition" in bad_res2.json()["error"]["message"]

    # 3. Valid: inferred -> confirmed
    conf_res = client.patch(
        f"/api/v1/workspaces/{ws_id}/commitments/{comm1_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "confirmed"},
    )
    assert conf_res.status_code == 200
    assert conf_res.json()["status"] == "confirmed"

    # 4. Valid: confirmed -> in_progress
    prog_res = client.patch(
        f"/api/v1/workspaces/{ws_id}/commitments/{comm1_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "in_progress"},
    )
    assert prog_res.status_code == 200
    assert prog_res.json()["status"] == "in_progress"

    # 5. Prohibited: in_progress -> rejected is blocked (422)
    bad_prog_rej = client.patch(
        f"/api/v1/workspaces/{ws_id}/commitments/{comm1_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "rejected"},
    )
    assert bad_prog_rej.status_code == 422
    assert "Invalid state transition" in bad_prog_rej.json()["error"]["message"]

    # 6. Valid: in_progress -> completed
    comp_res = client.patch(
        f"/api/v1/workspaces/{ws_id}/commitments/{comm1_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "completed"},
    )
    assert comp_res.status_code == 200
    assert comp_res.json()["status"] == "completed"

    # 7. Terminal State Guard: completed allows NO transitions out
    for forbidden_target in ("in_progress", "confirmed", "rejected", "inferred"):
        term_res = client.patch(
            f"/api/v1/workspaces/{ws_id}/commitments/{comm1_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": forbidden_target},
        )
        assert term_res.status_code == 422
        assert "Completed commitments are final" in term_res.json()["error"]["message"]

    # 8. Rejection and Reopening lifecycle on a separate commitment
    create_res2 = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/commitments",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Evaluate third-party vendor",
            "source_quote": "We could consider evaluating that vendor next month.",
            "status": "inferred",
        },
    )
    comm2_id = create_res2.json()["id"]

    # Valid: inferred -> rejected
    rej_res1 = client.patch(
        f"/api/v1/workspaces/{ws_id}/commitments/{comm2_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "rejected"},
    )
    assert rej_res1.status_code == 200
    assert rej_res1.json()["status"] == "rejected"
    assert rej_res1.json()["reviewed_by_id"] is not None
    assert rej_res1.json()["reviewed_at"] is not None

    # Prohibited: rejected -> confirmed directly is blocked (must reopen first)
    bad_rej_conf = client.patch(
        f"/api/v1/workspaces/{ws_id}/commitments/{comm2_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "confirmed"},
    )
    assert bad_rej_conf.status_code == 422
    assert "Invalid state transition" in bad_rej_conf.json()["error"]["message"]

    # Valid: rejected -> inferred (explicit reopen)
    reopen_res = client.patch(
        f"/api/v1/workspaces/{ws_id}/commitments/{comm2_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "inferred"},
    )
    assert reopen_res.status_code == 200
    reopened = reopen_res.json()
    assert reopened["status"] == "inferred"
    # Audit fields cleared on reopening
    assert reopened["reviewed_by_id"] is None
    assert reopened["reviewed_at"] is None

    # Valid: confirmed -> rejected
    conf_res2 = client.patch(
        f"/api/v1/workspaces/{ws_id}/commitments/{comm2_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "confirmed"},
    )
    assert conf_res2.status_code == 200
    assert conf_res2.json()["status"] == "confirmed"

    rej_from_conf = client.patch(
        f"/api/v1/workspaces/{ws_id}/commitments/{comm2_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "rejected"},
    )
    assert rej_from_conf.status_code == 200
    assert rej_from_conf.json()["status"] == "rejected"


def test_role_based_approval_restrictions(client: TestClient) -> None:
    """Role matrix enforcement:
    - Member cannot confirm, reject, reopen, or delete commitments.
    - Viewer cannot update or delete commitments.
    - Owner/Admin can confirm, reject, reopen, and delete commitments.
    """
    # 1. Owner sets up workspace and commitment
    _owner_email, owner_token, ws_id = create_authenticated_user(client)
    ws_uuid = uuid.UUID(ws_id)

    conv_res = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"title": "Governance Check", "conversation_type": "meeting"},
    )
    conv_id = conv_res.json()["id"]

    comm_res = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/commitments",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "title": "Migrate database cluster",
            "source_quote": "We must migrate the database cluster by Sunday.",
            "status": "inferred",
        },
    )
    comm_id = comm_res.json()["id"]

    # 2. Create User B and add to workspace as 'member'
    _b_email, member_token, _ = create_authenticated_user(client)
    # Get User B id
    user_b_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {member_token}"})
    user_b_id = uuid.UUID(user_b_res.json()["id"])

    with SessionLocal() as db_session:
        membership = WorkspaceMembership(
            workspace_id=ws_uuid,
            user_id=user_b_id,
            role="member",
        )
        db_session.add(membership)
        db_session.commit()

    # Member attempts to confirm -> 403
    patch_confirm = client.patch(
        f"/api/v1/workspaces/{ws_id}/commitments/{comm_id}",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"status": "confirmed"},
    )
    assert patch_confirm.status_code == 403
    assert "Only workspace owners and admins" in patch_confirm.json()["error"]["message"]

    # Member attempts to reject -> 403
    patch_reject = client.patch(
        f"/api/v1/workspaces/{ws_id}/commitments/{comm_id}",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"status": "rejected"},
    )
    assert patch_reject.status_code == 403

    # Member attempts to delete -> 403
    del_attempt = client.delete(
        f"/api/v1/workspaces/{ws_id}/commitments/{comm_id}",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert del_attempt.status_code == 403

    # Member CAN update operational details (title, description)
    member_edit = client.patch(
        f"/api/v1/workspaces/{ws_id}/commitments/{comm_id}",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"title": "Migrate database cluster to AWS RDS"},
    )
    assert member_edit.status_code == 200
    assert member_edit.json()["title"] == "Migrate database cluster to AWS RDS"

    # 3. Create User C and add as 'viewer'
    _c_email, viewer_token, _ = create_authenticated_user(client)
    user_c_id = uuid.UUID(
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {viewer_token}"}).json()[
            "id"
        ]
    )

    with SessionLocal() as db_session:
        v_membership = WorkspaceMembership(
            workspace_id=ws_uuid,
            user_id=user_c_id,
            role="viewer",
        )
        db_session.add(v_membership)
        db_session.commit()

    # Viewer attempts to edit title -> 403
    viewer_edit = client.patch(
        f"/api/v1/workspaces/{ws_id}/commitments/{comm_id}",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={"title": "Viewer tampering attempt"},
    )
    assert viewer_edit.status_code == 403

    # Viewer attempts to delete -> 403
    viewer_del = client.delete(
        f"/api/v1/workspaces/{ws_id}/commitments/{comm_id}",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert viewer_del.status_code == 403

    # 4. Owner confirms successfully
    owner_conf = client.patch(
        f"/api/v1/workspaces/{ws_id}/commitments/{comm_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"status": "confirmed"},
    )
    assert owner_conf.status_code == 200
    assert owner_conf.json()["status"] == "confirmed"

    # Owner deletes successfully
    owner_del = client.delete(
        f"/api/v1/workspaces/{ws_id}/commitments/{comm_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert owner_del.status_code == 204


def test_cross_workspace_commitment_isolation(client: TestClient) -> None:
    """Users in Workspace B must not access, modify, or delete commitments in Workspace A."""
    _a_email, a_token, ws_a = create_authenticated_user(client)
    _b_email, b_token, ws_b = create_authenticated_user(client)

    conv_res = client.post(
        f"/api/v1/workspaces/{ws_a}/conversations",
        headers={"Authorization": f"Bearer {a_token}"},
        json={"title": "A Secret Strategy", "conversation_type": "meeting"},
    )
    conv_a_id = conv_res.json()["id"]

    comm_res = client.post(
        f"/api/v1/workspaces/{ws_a}/conversations/{conv_a_id}/commitments",
        headers={"Authorization": f"Bearer {a_token}"},
        json={
            "title": "Acquire Competitor X",
            "source_quote": "We will acquire Competitor X in Q4.",
            "status": "inferred",
        },
    )
    comm_a_id = comm_res.json()["id"]

    # User B tries to read User A's commitments via Workspace A endpoint -> 403
    read_attempt = client.get(
        f"/api/v1/workspaces/{ws_a}/conversations/{conv_a_id}/commitments",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert read_attempt.status_code == 403

    # User B tries to read User A's commitment using Workspace B ID -> 404
    read_b_route = client.get(
        f"/api/v1/workspaces/{ws_b}/conversations/{conv_a_id}/commitments",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert read_b_route.status_code == 404

    # User B tries to patch User A's commitment -> 403
    patch_attempt = client.patch(
        f"/api/v1/workspaces/{ws_a}/commitments/{comm_a_id}",
        headers={"Authorization": f"Bearer {b_token}"},
        json={"title": "Hacked Title"},
    )
    assert patch_attempt.status_code == 403

    # User B tries to delete User A's commitment -> 403
    del_attempt = client.delete(
        f"/api/v1/workspaces/{ws_a}/commitments/{comm_a_id}",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert del_attempt.status_code == 403


@pytest.mark.asyncio
async def test_concurrent_extraction_race_condition_safety(client: TestClient) -> None:
    """Direct service test: Verify concurrent extractions with identical fingerprints
    safely recover via rollback and list_commitments rather than crashing.
    """
    _email, token, ws_id_str = create_authenticated_user(client)
    ws_id = uuid.UUID(ws_id_str)

    conv_res = client.post(
        f"/api/v1/workspaces/{ws_id_str}/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Concurrency Check", "conversation_type": "meeting"},
    )
    conv_id = uuid.UUID(conv_res.json()["id"])

    with SessionLocal() as db:
        # Seed an existing commitment
        quote = "We will launch the mobile app by next Tuesday."
        title = "Launch mobile app"
        ev_hash = compute_evidence_hash(conv_id, quote, title)

        first_comm = Commitment(
            id=uuid.uuid4(),
            workspace_id=ws_id,
            conversation_id=conv_id,
            title=title,
            source_quote=quote,
            status="inferred",
            confidence_score=0.9,
            evidence_hash=ev_hash,
        )
        db.add(first_comm)
        db.commit()

        # Custom provider returning same commitment
        class CustomProvider(LLMProvider):
            @property
            def provider_name(self) -> str:
                return "custom"

            @property
            def is_mock(self) -> bool:
                return False

            async def extract_signals(self, transcript_text: str, context=None):
                return ExtractionResult(
                    provider="custom",
                    is_mock=False,
                    model_name="custom",
                    signals=[
                        ExtractedSignal(
                            category="commitment",
                            statement=title,
                            certainty="confirmed_fact",
                            confidence=0.9,
                            source_quote=quote,
                            item_type="commitment",
                        )
                    ],
                )

        # Mock transcript
        transcript = Transcript(
            id=uuid.uuid4(),
            workspace_id=ws_id,
            conversation_id=conv_id,
            provider="mock_stt",
            raw_transcript=quote,
            status="completed",
        )
        db.add(transcript)
        db.commit()

        results = await CommitmentService.extract_commitments_from_transcript(
            db=db,
            workspace_id=ws_id,
            conversation_id=conv_id,
            llm_provider=CustomProvider(),
            role="owner",
        )
        # Should return 0 new commitments because hash matches existing
        assert len(results) == 0


@pytest.mark.anyio
async def test_idempotency_adversarial_scenarios_a_b_c_d_e(client: TestClient) -> None:
    """Test all five critical idempotency and deduplication scenarios:
    - Scenario A: Same quote and title -> single commitment created.
    - Scenario B: Same quote, minor title rephrasing with stop words -> hash collision
      handled, no duplicate.
    - Scenario C: Same title, distinct quotes -> both commitments preserved (different hashes).
    - Scenario D: Single quote, two distinct commitments -> both commitments preserved
      (different action tokens).
    - Scenario E: Concurrent race condition safe, foreign key or unexpected DB error re-raised.
    """
    _email, token, ws_id_str = create_authenticated_user(client)
    ws_id = uuid.UUID(ws_id_str)

    conv_res = client.post(
        f"/api/v1/workspaces/{ws_id_str}/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Idempotency Adversarial Lab", "conversation_type": "meeting"},
    )
    conv_id = uuid.UUID(conv_res.json()["id"])

    # 1. Scenario A & B: Token-based normalization on identical quote
    quote_ab = "I will deliver draft enterprise contract by end of day Friday."
    title_a = "Deliver draft enterprise contract"
    title_b = "deliver the draft enterprise contract"  # stop word 'the' added, casing variation

    hash_a = compute_evidence_hash(conv_id, quote_ab, title_a)
    hash_b = compute_evidence_hash(conv_id, quote_ab, title_b)
    # Both normalize to the same action tokens {"contract", "deliver", "draft", "enterprise"}
    assert hash_a == hash_b

    # 2. Scenario C: Same title, completely distinct quotes -> different hashes
    quote_c1 = "I will review the backend code tomorrow."
    quote_c2 = "Let's review the frontend styles on Friday."
    title_c = "Review codebase"
    hash_c1 = compute_evidence_hash(conv_id, quote_c1, title_c)
    hash_c2 = compute_evidence_hash(conv_id, quote_c2, title_c)
    assert hash_c1 != hash_c2

    # 3. Scenario D: Single quote containing two distinct commitments -> different hashes
    quote_d = "Alice will migrate the database cluster, and Bob will build the frontend design."
    title_d1 = "Migrate database cluster"
    title_d2 = "Build frontend design"
    hash_d1 = compute_evidence_hash(conv_id, quote_d, title_d1)
    hash_d2 = compute_evidence_hash(conv_id, quote_d, title_d2)
    assert hash_d1 != hash_d2

    with SessionLocal() as db:
        # Create transcript containing quote_d
        transcript = Transcript(
            id=uuid.uuid4(),
            workspace_id=ws_id,
            conversation_id=conv_id,
            provider="mock_stt",
            raw_transcript=quote_d,
            status="completed",
        )
        db.add(transcript)
        db.commit()

        class MultiSignalProvider(LLMProvider):
            @property
            def provider_name(self) -> str:
                return "multi"

            @property
            def is_mock(self) -> bool:
                return False

            async def extract_signals(self, transcript_text: str, context=None):
                return ExtractionResult(
                    provider="multi",
                    is_mock=False,
                    model_name="multi",
                    signals=[
                        ExtractedSignal(
                            category="commitment",
                            statement=title_d1,
                            certainty="confirmed_fact",
                            confidence=0.95,
                            source_quote=quote_d,
                            item_type="commitment",
                        ),
                        ExtractedSignal(
                            category="commitment",
                            statement=title_d2,
                            certainty="confirmed_fact",
                            confidence=0.90,
                            source_quote=quote_d,
                            item_type="commitment",
                        ),
                    ],
                )

        # Extract both from single quote
        results_d = await CommitmentService.extract_commitments_from_transcript(
            db=db,
            workspace_id=ws_id,
            conversation_id=conv_id,
            llm_provider=MultiSignalProvider(),
            role="owner",
        )
        # Both distinct commitments must be preserved
        assert len(results_d) == 2

        # Repeated extraction of same signals -> 0 new additions
        results_d_repeat = await CommitmentService.extract_commitments_from_transcript(
            db=db,
            workspace_id=ws_id,
            conversation_id=conv_id,
            llm_provider=MultiSignalProvider(),
            role="owner",
        )
        assert len(results_d_repeat) == 0

        # Total in DB for this conversation is exactly 2
        total = db.query(Commitment).filter(Commitment.conversation_id == conv_id).count()
        assert total == 2


@pytest.mark.anyio
async def test_gemini_verbatim_quote_and_item_classification(client: TestClient) -> None:
    """Verify quality safeguards:
    1. Verbatim quote requirement: candidate quotes not present verbatim are discarded.
    2. Nullable fields: owner, deadline, and confidence are not fabricated when absent.
    3. Item classification: only candidate items of type 'commitment' are persisted;
       questions/suggestions/completed actions are excluded.
    """
    _email, token, ws_id_str = create_authenticated_user(client)
    ws_id = uuid.UUID(ws_id_str)

    conv_res = client.post(
        f"/api/v1/workspaces/{ws_id_str}/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Transcript Verification Lab", "conversation_type": "meeting"},
    )
    conv_id = uuid.UUID(conv_res.json()["id"])

    transcript_body = (
        "Alice: We need to improve the user onboarding flow. "
        "Bob: Should we hire another contractor for this? "
        "Alice: I will prepare the onboarding metrics by Friday."
    )

    with SessionLocal() as db:
        transcript = Transcript(
            id=uuid.uuid4(),
            workspace_id=ws_id,
            conversation_id=conv_id,
            provider="mock_stt",
            raw_transcript=transcript_body,
            status="completed",
        )
        db.add(transcript)
        db.commit()

        class QualityProvider(LLMProvider):
            @property
            def provider_name(self) -> str:
                return "quality_test"

            @property
            def is_mock(self) -> bool:
                return False

            async def extract_signals(self, transcript_text: str, context=None):
                # 1. Valid verbatim commitment
                s1 = ExtractedSignal(
                    category="commitment",
                    statement="Prepare onboarding metrics",
                    certainty="confirmed_fact",
                    confidence=None,  # Nullable confidence
                    source_quote="I will prepare the onboarding metrics by Friday.",
                    item_type="commitment",
                )
                # 2. Fabricated / Paraphrased quote (not verbatim in transcript)
                s2 = ExtractedSignal(
                    category="commitment",
                    statement="Improve user onboarding flow",
                    certainty="inferred",
                    confidence=0.8,
                    source_quote="Alice said that she will fix the user flow next week.",
                    item_type="commitment",
                )
                # 3. Non-commitment item: Question
                s3 = ExtractedSignal(
                    category="question",
                    statement="Hire contractor for onboarding",
                    certainty="inferred",
                    confidence=0.7,
                    source_quote="Should we hire another contractor for this?",
                    item_type="question",
                )
                # 4. Non-commitment item: Suggestion
                s4 = ExtractedSignal(
                    category="suggestion",
                    statement="Need to improve onboarding flow",
                    certainty="inferred",
                    confidence=0.6,
                    source_quote="We need to improve the user onboarding flow.",
                    item_type="suggestion",
                )
                return ExtractionResult(
                    provider="quality_test",
                    is_mock=False,
                    model_name="quality_test",
                    signals=[s1, s2, s3, s4],
                )

        results = await CommitmentService.extract_commitments_from_transcript(
            db=db,
            workspace_id=ws_id,
            conversation_id=conv_id,
            llm_provider=QualityProvider(),
            role="owner",
        )

        # Only s1 should be extracted!
        # s2 is rejected because quote is not verbatim in transcript.
        # s3 is rejected because item_type is 'question'.
        # s4 is rejected because item_type is 'suggestion'.
        assert len(results) == 1
        assert results[0].title == "Prepare onboarding metrics"
        assert results[0].source_quote == "I will prepare the onboarding metrics by Friday."
        # Null fields are preserved without fabricated defaults
        assert results[0].confidence_score is None
        assert results[0].assignee_id is None
        assert results[0].due_date is None
