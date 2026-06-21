def test_register_returns_token(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "new@lunar.dev",
            "password": "testpass123",
            "display_name": "New User",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]


def test_register_duplicate_email_returns_409(client):
    payload = {
        "email": "dup@lunar.dev",
        "password": "testpass123",
    }
    assert client.post("/auth/register", json=payload).status_code == 201
    duplicate = client.post("/auth/register", json=payload)

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Email already registered"


def test_register_validates_password_length(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "short@lunar.dev",
            "password": "short",
        },
    )

    assert response.status_code == 422


def test_login_success(client):
    client.post(
        "/auth/register",
        json={"email": "login@lunar.dev", "password": "testpass123"},
    )
    response = client.post(
        "/auth/login",
        json={"email": "login@lunar.dev", "password": "testpass123"},
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_wrong_password_returns_401(client):
    client.post(
        "/auth/register",
        json={"email": "wrong@lunar.dev", "password": "testpass123"},
    )
    response = client.post(
        "/auth/login",
        json={"email": "wrong@lunar.dev", "password": "badpassword"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_unknown_email_returns_401(client):
    response = client.post(
        "/auth/login",
        json={"email": "missing@lunar.dev", "password": "testpass123"},
    )

    assert response.status_code == 401


def test_me_requires_auth(client):
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_me_returns_current_user(client, auth_headers):
    response = client.get("/auth/me", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "pytest@lunar.dev"
    assert data["display_name"] == "Pytest User"
    assert "id" in data
    assert "created_at" in data


def test_me_rejects_invalid_token(client):
    response = client.get("/auth/me", headers={"Authorization": "Bearer invalid.token"})

    assert response.status_code == 401


def test_google_login_returns_503_when_not_configured(client):
    response = client.get("/auth/google", follow_redirects=False)

    assert response.status_code == 503
    assert response.json()["detail"] == "Google OAuth is not configured"
