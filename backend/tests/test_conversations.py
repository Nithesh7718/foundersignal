import io

from fastapi.testclient import TestClient

from tests.test_workspaces import create_authenticated_user


def create_minimal_wav_bytes() -> bytes:
    """Create minimal valid 44-byte WAV audio header."""
    return (
        b"RIFF"
        + (36).to_bytes(4, "little")
        + b"WAVE"
        + b"fmt "
        + (16).to_bytes(4, "little")
        + (1).to_bytes(2, "little")
        + (1).to_bytes(2, "little")
        + (44100).to_bytes(4, "little")
        + (88200).to_bytes(4, "little")
        + (2).to_bytes(2, "little")
        + (16).to_bytes(2, "little")
        + b"data"
        + (0).to_bytes(4, "little")
    )


def test_conversation_lifecycle(client: TestClient) -> None:
    _email, token, ws_id = create_authenticated_user(client)

    # 1. Create conversation
    create_res = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Client Sync - Roadmap Review",
            "conversation_type": "meeting",
        },
    )
    assert create_res.status_code == 201
    conv = create_res.json()
    conv_id = conv["id"]
    assert conv["title"] == "Client Sync - Roadmap Review"
    assert conv["status"] == "draft"

    # 2. List conversations
    list_res = client.get(
        f"/api/v1/workspaces/{ws_id}/conversations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_res.status_code == 200
    conv_list = list_res.json()
    assert any(c["id"] == conv_id for c in conv_list)

    # 3. Get conversation detail
    detail_res = client.get(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["id"] == conv_id
    assert "audio_assets" in detail
    assert "commitments" in detail


def test_conversation_audio_upload_valid(client: TestClient) -> None:
    _email, token, ws_id = create_authenticated_user(client)

    conv_res = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Voice Note with Founder", "conversation_type": "voice_note"},
    )
    conv_id = conv_res.json()["id"]

    wav_bytes = create_minimal_wav_bytes()
    upload_res = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/audio",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("meeting.wav", io.BytesIO(wav_bytes), "audio/wav")},
    )
    assert upload_res.status_code == 201
    asset = upload_res.json()
    assert asset["file_name"] == "meeting.wav"
    assert asset["mime_type"] == "audio/wav"
    assert asset["status"] == "ready"

    # Verify conversation status transitioned to 'uploaded'
    detail = client.get(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert detail["status"] == "uploaded"
    assert len(detail["audio_assets"]) == 1


def test_audio_upload_invalid_magic_bytes_rejected(client: TestClient) -> None:
    _email, token, ws_id = create_authenticated_user(client)

    conv_res = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Corrupt Audio Upload", "conversation_type": "voice_note"},
    )
    conv_id = conv_res.json()["id"]

    fake_audio = b"This is plain text disguised as an audio file for malicious testing."
    upload_res = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/audio",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("spoofed.wav", io.BytesIO(fake_audio), "audio/wav")},
    )
    assert upload_res.status_code == 422
    assert upload_res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_cross_workspace_conversation_access_denied(client: TestClient) -> None:
    _email_a, token_a, ws_a = create_authenticated_user(client)
    _email_b, token_b, ws_b = create_authenticated_user(client)

    conv_res = client.post(
        f"/api/v1/workspaces/{ws_a}/conversations",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"title": "Workspace A Secret", "conversation_type": "meeting"},
    )
    conv_a_id = conv_res.json()["id"]

    # User B tries to view User A's conversation under User A's workspace
    res1 = client.get(
        f"/api/v1/workspaces/{ws_a}/conversations/{conv_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res1.status_code == 403

    # User B tries to view User A's conversation ID queried under User B's workspace ID
    res2 = client.get(
        f"/api/v1/workspaces/{ws_b}/conversations/{conv_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res2.status_code == 404


def test_delete_conversation_cleans_up_physical_audio_file(client: TestClient) -> None:
    from pathlib import Path

    from app.core.config import settings

    _email, token, ws_id = create_authenticated_user(client)

    conv_res = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "To be deleted", "conversation_type": "meeting"},
    )
    conv_id = conv_res.json()["id"]

    wav_bytes = create_minimal_wav_bytes()
    upload_res = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}/audio",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("cleanup_test.wav", io.BytesIO(wav_bytes), "audio/wav")},
    )
    assert upload_res.status_code == 201
    asset_data = upload_res.json()
    asset_id = asset_data["id"]

    base_dir = Path(settings.AUDIO_STORAGE_PATH).resolve()
    target_file = base_dir / str(ws_id) / f"{asset_id}.wav"
    assert target_file.exists(), f"Expected physical audio file {target_file} to exist on disk"

    # Delete conversation
    del_res = client.delete(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_res.status_code == 204

    # Verify conversation is gone from DB
    get_res = client.get(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_res.status_code == 404

    # Verify physical file was cleanly removed from disk and NOT orphaned
    assert not target_file.exists(), (
        "Physical file on disk must be removed when conversation is deleted"
    )


def test_cross_workspace_delete_denied(client: TestClient) -> None:
    _email_a, token_a, ws_a = create_authenticated_user(client)
    _email_b, token_b, ws_b = create_authenticated_user(client)

    conv_res = client.post(
        f"/api/v1/workspaces/{ws_a}/conversations",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"title": "Protected Conversation", "conversation_type": "meeting"},
    )
    conv_a_id = conv_res.json()["id"]

    # User B tries to delete User A's conversation under User A's workspace
    res1 = client.delete(
        f"/api/v1/workspaces/{ws_a}/conversations/{conv_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res1.status_code == 403

    # User B tries to delete User A's conversation using User B's workspace ID
    res2 = client.delete(
        f"/api/v1/workspaces/{ws_b}/conversations/{conv_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res2.status_code == 404

    # Verify conversation still exists
    verify_res = client.get(
        f"/api/v1/workspaces/{ws_a}/conversations/{conv_a_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert verify_res.status_code == 200
