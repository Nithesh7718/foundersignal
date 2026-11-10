import uuid

from fastapi.testclient import TestClient


def test_register_user_success(client: TestClient) -> None:
    unique_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email,
            "password": "SecurePassword123!",
            "full_name": "Test Founder",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == unique_email
    assert data["user"]["full_name"] == "Test Founder"
    assert "hashed_password" not in data["user"]


def test_register_duplicate_email_fails(client: TestClient) -> None:
    unique_email = f"dup_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "email": unique_email,
        "password": "SecurePassword123!",
        "full_name": "Original User",
    }
    first_res = client.post("/api/v1/auth/register", json=payload)
    assert first_res.status_code == 201

    second_res = client.post("/api/v1/auth/register", json=payload)
    assert second_res.status_code == 409
    error = second_res.json()
    assert error["error"]["code"] == "RESOURCE_CONFLICT"


def test_login_success(client: TestClient) -> None:
    email = f"login_{uuid.uuid4().hex[:8]}@example.com"
    password = "CorrectPassword123!"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Login User"},
    )

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200
    data = login_res.json()
    assert "access_token" in data
    assert data["user"]["email"] == email


def test_login_invalid_password_fails(client: TestClient) -> None:
    email = f"wrong_{uuid.uuid4().hex[:8]}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "RightPassword123!", "full_name": "User"},
    )

    res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPassword999!"},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_get_me_authenticated(client: TestClient) -> None:
    email = f"me_{uuid.uuid4().hex[:8]}@example.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "full_name": "Me User"},
    )
    token = reg.json()["access_token"]

    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["email"] == email


def test_get_me_unauthenticated_fails(client: TestClient) -> None:
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_logout_revokes_token(client: TestClient) -> None:
    email = f"logout_{uuid.uuid4().hex[:8]}@example.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "full_name": "Logout User"},
    )
    token = reg.json()["access_token"]

    # Verify token works
    res_before = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_before.status_code == 200

    # Logout
    logout_res = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_res.status_code == 200

    # Token should now be rejected
    res_after = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_after.status_code == 401
    assert res_after.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
