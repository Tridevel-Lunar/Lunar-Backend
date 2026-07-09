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
    assert data["role"] == "learner"
    assert "id" in data
    assert "created_at" in data


def test_me_rejects_invalid_token(client):
    response = client.get("/auth/me", headers={"Authorization": "Bearer invalid.token"})

    assert response.status_code == 401


def test_google_login_returns_503_when_not_configured(client):
    response = client.get("/auth/google", follow_redirects=False)

    assert response.status_code == 503
    assert response.json()["detail"] == "Google OAuth is not configured"


def test_google_onetap_returns_503_when_not_configured(client):
    response = client.post("/auth/google/onetap", json={"credential": "fake-token"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Google sign-in is not configured"


def test_login_sets_auth_cookie(client):
    client.post(
        "/auth/register",
        json={"email": "cookie@lunar.dev", "password": "testpass123"},
    )
    response = client.post(
        "/auth/login",
        json={"email": "cookie@lunar.dev", "password": "testpass123"},
    )

    assert response.status_code == 200
    assert "lunar_token" in response.cookies
    assert response.cookies["lunar_token"]


def test_register_sets_auth_cookie(client):
    response = client.post(
        "/auth/register",
        json={"email": "regcookie@lunar.dev", "password": "testpass123"},
    )

    assert response.status_code == 201
    assert "lunar_token" in response.cookies


def test_me_works_with_cookie(client):
    login = client.post(
        "/auth/register",
        json={"email": "mecookie@lunar.dev", "password": "testpass123"},
    )
    client.cookies.set("lunar_token", login.cookies["lunar_token"])
    response = client.get("/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == "mecookie@lunar.dev"


def test_logout_clears_cookie(client):
    login = client.post(
        "/auth/register",
        json={"email": "logout@lunar.dev", "password": "testpass123"},
    )
    client.cookies.set("lunar_token", login.cookies["lunar_token"])
    response = client.post("/auth/logout")

    assert response.status_code == 200
    assert response.cookies.get("lunar_token") in ("", None) or "lunar_token" not in response.cookies


def test_google_onetap_invalid_credential_returns_401(client, google_client_id, monkeypatch):
    from app.services.google_auth import GoogleAuthError

    def mock_verify(_credential: str) -> dict:
        raise GoogleAuthError("Invalid Google credential")

    monkeypatch.setattr("app.api.routes.auth.verify_google_id_token", mock_verify)

    response = client.post("/auth/google/onetap", json={"credential": "fake-token"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid Google credential"


def test_google_onetap_success_creates_user(client, google_client_id, google_token_payload, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.auth.verify_google_id_token",
        lambda _credential: google_token_payload,
    )

    response = client.post("/auth/google/onetap", json={"credential": "valid-token"})

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert response.cookies["lunar_token"]

    client.cookies.set("lunar_token", response.cookies["lunar_token"])
    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "google@lunar.dev"
    assert me.json()["display_name"] == "Google User"


def test_google_onetap_links_existing_email_account(
    client, google_client_id, google_token_payload, monkeypatch
):
    client.post(
        "/auth/register",
        json={"email": "google@lunar.dev", "password": "testpass123", "display_name": "Local User"},
    )

    monkeypatch.setattr(
        "app.api.routes.auth.verify_google_id_token",
        lambda _credential: google_token_payload,
    )

    response = client.post("/auth/google/onetap", json={"credential": "valid-token"})

    assert response.status_code == 200
    client.cookies.set("lunar_token", response.cookies["lunar_token"])
    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "google@lunar.dev"
    assert me.json()["display_name"] == "Local User"


def test_google_onetap_conflict_when_email_linked_to_other_google(
    client, db, google_client_id, google_token_payload, monkeypatch
):
    from app.models.user import User

    db.add(
        User(
            email="google@lunar.dev",
            google_sub="other-google-sub",
            hashed_password=None,
            display_name="Other Google",
        )
    )
    db.commit()

    monkeypatch.setattr(
        "app.api.routes.auth.verify_google_id_token",
        lambda _credential: google_token_payload,
    )

    response = client.post("/auth/google/onetap", json={"credential": "valid-token"})

    assert response.status_code == 409
    assert response.json()["detail"] == "Email already linked to another account"
