import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest")

from app.core.config import get_settings
from tests.conftest import client  # noqa: F401


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_register_defaults_to_learner(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={"email": "learner@lunar.dev", "password": "testpass123"},
    )
    assert response.status_code == 201

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"})
    assert me.json()["role"] == "learner"


def test_admin_emails_bootstrap_on_register(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_EMAILS", "bootstrap@lunar.dev")
    get_settings.cache_clear()

    response = client.post(
        "/auth/register",
        json={"email": "bootstrap@lunar.dev", "password": "testpass123"},
    )
    assert response.status_code == 201

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"})
    assert me.json()["role"] == "admin"


def test_admin_emails_bootstrap_on_login(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    client.post(
        "/auth/register",
        json={"email": "promote@lunar.dev", "password": "testpass123"},
    )

    monkeypatch.setenv("ADMIN_EMAILS", "promote@lunar.dev")
    get_settings.cache_clear()

    login = client.post(
        "/auth/login",
        json={"email": "promote@lunar.dev", "password": "testpass123"},
    )
    assert login.status_code == 200

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert me.json()["role"] == "admin"
