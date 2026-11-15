import uuid

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.models.audio_asset import AudioAsset
from app.models.transcript import Transcript


def create_user_and_workspace(client: TestClient) -> tuple[str, str, str]:
    """Helper returning (email, token, workspace_id)."""
    email = f"proj_user_{uuid.uuid4().hex[:8]}@example.com"
    res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "full_name": "Project Lead"},
    )
    token = res.json()["access_token"]
    ws_res = client.get("/api/v1/workspaces", headers={"Authorization": f"Bearer {token}"})
    ws_id = ws_res.json()[0]["id"]
    return email, token, ws_id


def test_project_crud_lifecycle(client: TestClient) -> None:
    _email, token, ws_id = create_user_and_workspace(client)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create project
    create_res = client.post(
        f"/api/v1/workspaces/{ws_id}/projects",
        headers=headers,
        json={
            "name": "Q4 Enterprise Launch",
            "description": "Enterprise security and tenant isolation milestone",
            "status": "active",
        },
    )
    assert create_res.status_code == 201
    project = create_res.json()
    assert project["name"] == "Q4 Enterprise Launch"
    assert project["status"] == "active"
    assert project["total_commitments"] == 0
    proj_id = project["id"]

    # 2. Get project detail
    get_res = client.get(f"/api/v1/workspaces/{ws_id}/projects/{proj_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == proj_id

    # 3. Update project
    patch_res = client.patch(
        f"/api/v1/workspaces/{ws_id}/projects/{proj_id}",
        headers=headers,
        json={"name": "Q4 Enterprise GA", "status": "completed"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "Q4 Enterprise GA"
    assert patch_res.json()["status"] == "completed"

    # 4. List projects
    list_res = client.get(f"/api/v1/workspaces/{ws_id}/projects", headers=headers)
    assert list_res.status_code == 200
    assert any(p["id"] == proj_id for p in list_res.json())

    # 5. Delete project
    del_res = client.delete(f"/api/v1/workspaces/{ws_id}/projects/{proj_id}", headers=headers)
    assert del_res.status_code == 204

    # 6. Verify deleted
    verify_res = client.get(f"/api/v1/workspaces/{ws_id}/projects/{proj_id}", headers=headers)
    assert verify_res.status_code == 404


def test_project_cross_tenant_isolation(client: TestClient) -> None:
    _email_a, token_a, ws_a = create_user_and_workspace(client)
    _email_b, token_b, _ws_b = create_user_and_workspace(client)

    # User A creates a project
    create_res = client.post(
        f"/api/v1/workspaces/{ws_a}/projects",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"name": "Confidential A Project"},
    )
    assert create_res.status_code == 201
    proj_a_id = create_res.json()["id"]

    # User B attempts to access User A's project
    res = client.get(
        f"/api/v1/workspaces/{ws_a}/projects/{proj_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res.status_code == 403

    # User B attempts to delete User A's project
    del_res = client.delete(
        f"/api/v1/workspaces/{ws_a}/projects/{proj_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert del_res.status_code == 403


def test_commitment_project_link_and_filtering(client: TestClient) -> None:
    _email, token, ws_id = create_user_and_workspace(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Create Project
    proj = client.post(
        f"/api/v1/workspaces/{ws_id}/projects",
        headers=headers,
        json={"name": "Billing Revamp"},
    ).json()

    # Create Conversation
    conv = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations",
        headers=headers,
        json={"title": "Billing Sync", "conversation_type": "meeting"},
    ).json()

    # Create Commitment linked to project
    comm1 = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv['id']}/commitments",
        headers=headers,
        json={
            "title": "Stripe Webhook Integration",
            "source_quote": "We will finalize Stripe webhooks tomorrow.",
            "status": "confirmed",
            "project_id": proj["id"],
        },
    ).json()
    assert comm1["project_id"] == proj["id"]

    # Create unlinked commitment
    comm2 = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv['id']}/commitments",
        headers=headers,
        json={
            "title": "Office Supplies",
            "source_quote": "Let's buy new markers.",
            "status": "confirmed",
        },
    ).json()
    assert comm2["project_id"] is None

    # Filter by project_id
    filtered = client.get(
        f"/api/v1/workspaces/{ws_id}/commitments?project_id={proj['id']}",
        headers=headers,
    ).json()
    assert len(filtered) == 1
    assert filtered[0]["id"] == comm1["id"]

    # Update unlinked commitment to link to project
    client.patch(
        f"/api/v1/workspaces/{ws_id}/commitments/{comm2['id']}",
        headers=headers,
        json={"project_id": proj["id"]},
    )
    updated_filtered = client.get(
        f"/api/v1/workspaces/{ws_id}/commitments?project_id={proj['id']}",
        headers=headers,
    ).json()
    assert len(updated_filtered) == 2


def test_project_delivery_summary(client: TestClient) -> None:
    _email, token, ws_id = create_user_and_workspace(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Create 1 active project and 1 completed project
    p1 = client.post(
        f"/api/v1/workspaces/{ws_id}/projects",
        headers=headers,
        json={"name": "Project Alpha", "status": "active"},
    ).json()

    client.post(
        f"/api/v1/workspaces/{ws_id}/projects",
        headers=headers,
        json={"name": "Project Beta", "status": "completed"},
    )

    conv = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations",
        headers=headers,
        json={"title": "Sprint 1", "conversation_type": "meeting"},
    ).json()

    # Add 1 completed and 1 in_progress commitment
    client.post(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv['id']}/commitments",
        headers=headers,
        json={
            "title": "Task One",
            "source_quote": "Task one will be done.",
            "status": "confirmed",
            "project_id": p1["id"],
        },
    )
    # Move to completed
    c1 = client.get(f"/api/v1/workspaces/{ws_id}/commitments", headers=headers).json()[0]
    client.patch(
        f"/api/v1/workspaces/{ws_id}/commitments/{c1['id']}",
        headers=headers,
        json={"status": "completed"},
    )

    client.post(
        f"/api/v1/workspaces/{ws_id}/conversations/{conv['id']}/commitments",
        headers=headers,
        json={
            "title": "Task Two",
            "source_quote": "Task two in progress.",
            "status": "confirmed",
            "project_id": p1["id"],
        },
    )

    summary_res = client.get(
        f"/api/v1/workspaces/{ws_id}/projects/delivery/summary",
        headers=headers,
    )
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert summary["total_projects"] == 2
    assert summary["active_projects"] == 1
    assert summary["completed_projects"] == 1
    assert summary["total_commitments"] == 2
    assert summary["completed_commitments"] == 1
    assert summary["delivery_completion_rate"] == 50.0


def test_workspace_commitments_invalid_status_and_pagination(client: TestClient) -> None:
    _email, token, ws_id = create_user_and_workspace(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Invalid status should return 422 or 400
    res = client.get(
        f"/api/v1/workspaces/{ws_id}/commitments?status=invalid_bogus_status",
        headers=headers,
    )
    assert res.status_code == 422 or res.status_code == 400

    # Test pagination
    conv = client.post(
        f"/api/v1/workspaces/{ws_id}/conversations",
        headers=headers,
        json={"title": "Pagination Check", "conversation_type": "meeting"},
    ).json()

    for i in range(5):
        client.post(
            f"/api/v1/workspaces/{ws_id}/conversations/{conv['id']}/commitments",
            headers=headers,
            json={
                "title": f"Commitment {i}",
                "source_quote": f"Quote for item {i}",
                "status": "inferred",
            },
        )

    paged = client.get(
        f"/api/v1/workspaces/{ws_id}/commitments?limit=2&offset=0",
        headers=headers,
    ).json()
    assert len(paged) == 2

    paged_next = client.get(
        f"/api/v1/workspaces/{ws_id}/commitments?limit=2&offset=2",
        headers=headers,
    ).json()
    assert len(paged_next) == 2
    assert paged[0]["id"] != paged_next[0]["id"]


def test_evidence_graph_generation_and_tenant_isolation(client: TestClient) -> None:
    _email_a, token_a, ws_a = create_user_and_workspace(client)
    _email_b, token_b, _ws_b = create_user_and_workspace(client)
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Create complete chain: Project, Conversation, Audio, Transcript, Commitment with speaker
    proj = client.post(
        f"/api/v1/workspaces/{ws_a}/projects",
        headers=headers_a,
        json={"name": "Core Platform"},
    ).json()

    conv = client.post(
        f"/api/v1/workspaces/{ws_a}/conversations",
        headers=headers_a,
        json={"title": "Strategy Sync", "conversation_type": "meeting"},
    ).json()

    with SessionLocal() as db:
        audio = AudioAsset(
            workspace_id=uuid.UUID(ws_a),
            conversation_id=uuid.UUID(conv["id"]),
            file_name="meeting_audio.webm",
            storage_path="audio/meeting_audio.webm",
            mime_type="audio/webm",
            file_size_bytes=10240,
            duration_seconds=30.0,
        )
        db.add(audio)
        tr = Transcript(
            workspace_id=uuid.UUID(ws_a),
            conversation_id=uuid.UUID(conv["id"]),
            provider="gnani_prisma",
            raw_transcript="Founder Nithesh commits to deploying the new infra by Friday.",
            language_code="en-IN",
            confidence=0.95,
        )
        db.add(tr)
        db.commit()

    client.post(
        f"/api/v1/workspaces/{ws_a}/conversations/{conv['id']}/commitments",
        headers=headers_a,
        json={
            "title": "Deploy new infra by Friday",
            "source_quote": "Deploying the new infra by Friday.",
            "status": "confirmed",
            "speaker": "Founder Nithesh",
            "project_id": proj["id"],
        },
    )

    # Fetch Evidence Graph for User A
    graph_res = client.get(f"/api/v1/workspaces/{ws_a}/evidence/graph", headers=headers_a)
    assert graph_res.status_code == 200
    graph = graph_res.json()
    assert graph["total_conversations"] >= 1
    assert graph["total_audio_assets"] >= 1
    assert graph["total_transcripts"] >= 1
    assert graph["total_commitments"] >= 1
    assert graph["total_projects"] >= 1

    node_types = {n["type"] for n in graph["nodes"]}
    assert "conversation" in node_types
    assert "audio" in node_types
    assert "transcript" in node_types
    assert "commitment" in node_types
    assert "project" in node_types
    assert "speaker" in node_types

    edge_types = {e["type"] for e in graph["edges"]}
    assert "has_audio" in edge_types
    assert "has_transcript" in edge_types
    assert "extracted_from" in edge_types
    assert "assigned_to_project" in edge_types
    assert "spoken_by" in edge_types

    # Cross-tenant check: User B cannot access User A's evidence graph
    blocked = client.get(
        f"/api/v1/workspaces/{ws_a}/evidence/graph",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert blocked.status_code == 403
