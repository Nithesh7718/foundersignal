import uuid

from fastapi.testclient import TestClient


def create_authenticated_user(client: TestClient) -> tuple[str, str, str]:
    """Helper to register and return (email, token, default_workspace_id)."""
    email = f"ws_user_{uuid.uuid4().hex[:8]}@example.com"
    res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "full_name": "Workspace User"},
    )
    token = res.json()["access_token"]
    ws_res = client.get("/api/v1/workspaces", headers={"Authorization": f"Bearer {token}"})
    workspaces = ws_res.json()
    ws_id = workspaces[0]["id"]
    return email, token, ws_id


def test_list_workspaces_contains_default(client: TestClient) -> None:
    _email, token, ws_id = create_authenticated_user(client)
    res = client.get("/api/v1/workspaces", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    workspaces = res.json()
    assert len(workspaces) >= 1
    assert any(ws["id"] == ws_id for ws in workspaces)


def test_create_workspace_success(client: TestClient) -> None:
    _email, token, _ws_id = create_authenticated_user(client)
    res = client.post(
        "/api/v1/workspaces",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Engineering Operations"},
    )
    assert res.status_code == 201
    data = response_data = res.json()
    assert response_data["name"] == "Engineering Operations"
    assert "slug" in data
    assert data["role"] == "owner"


def test_cross_workspace_isolation_blocks_unauthorized_user(client: TestClient) -> None:
    # User A creates workspace
    _email_a, token_a, ws_a = create_authenticated_user(client)
    # User B
    _email_b, token_b, _ws_b = create_authenticated_user(client)

    # User B attempts to access User A's workspace
    res = client.get(f"/api/v1/workspaces/{ws_a}", headers={"Authorization": f"Bearer {token_b}"})
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "ACCESS_DENIED"


def test_revoked_membership_blocks_future_access(client: TestClient) -> None:
    from sqlalchemy import delete

    from app.core.database import SessionLocal
    from app.models.workspace import WorkspaceMembership

    _email, token, ws_id = create_authenticated_user(client)

    # Verify access works initially
    res_before = client.get(
        f"/api/v1/workspaces/{ws_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_before.status_code == 200

    # Simulate membership removal in database
    with SessionLocal() as db:
        db.execute(
            delete(WorkspaceMembership).where(WorkspaceMembership.workspace_id == uuid.UUID(ws_id))
        )
        db.commit()

    # Access must now be immediately denied
    res_after = client.get(
        f"/api/v1/workspaces/{ws_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_after.status_code == 403
    assert res_after.json()["error"]["code"] == "ACCESS_DENIED"


def test_user_cannot_set_arbitrary_owner_on_workspace_creation(client: TestClient) -> None:
    _email_a, token_a, _ws_a = create_authenticated_user(client)
    arbitrary_fake_owner_id = str(uuid.uuid4())

    # User attempts to inject an arbitrary owner_id or elevated role
    res = client.post(
        "/api/v1/workspaces",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "name": "Exploit Attempt Workspace",
            "owner_id": arbitrary_fake_owner_id,
            "role": "superadmin",
        },
    )
    assert res.status_code == 201
    created_ws = res.json()
    # Ensure injected owner_id was ignored and owner is bound strictly to current_user
    assert created_ws["owner_id"] != arbitrary_fake_owner_id
