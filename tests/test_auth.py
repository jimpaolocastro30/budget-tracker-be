def test_register_and_login(client):
    register = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Jane Doe",
            "email": "jane@example.com",
            "password": "SecurePass123",
            "base_currency": "PHP",
            "timezone": "UTC",
        },
    )
    assert register.status_code == 201
    body = register.json()
    assert "access_token" in body
    assert body["user"]["email"] == "jane@example.com"

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "jane@example.com", "password": "SecurePass123"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["full_name"] == "Jane Doe"


def test_get_profile(client, user):
    response = client.get("/api/v1/users/me", headers=user["headers"])
    assert response.status_code == 200
    assert response.json()["email"] == user["email"]


def test_duplicate_email_rejected(client, user):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Another",
            "email": user["email"],
            "password": "SecurePass123",
        },
    )
    assert response.status_code == 409
