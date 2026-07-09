import os
from datetime import UTC, datetime
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest")
os.environ.setdefault("GOOGLE_CLIENT_ID", "")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "")

from app.core.config import get_settings
from app.main import app
from app.services.knowledge.ingest import (
    IngestRunResult,
    IngestSourceResult,
    KnowledgeOverview,
    KnowledgeSourceOverview,
    UploadKnowledgeResult,
)
from tests.conftest import auth_headers, client  # noqa: F401


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def admin_headers(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    monkeypatch.setenv("ADMIN_EMAILS", "admin@lunar.dev")
    get_settings.cache_clear()
    response = client.post(
        "/auth/register",
        json={
            "email": "admin@lunar.dev",
            "password": "testpass123",
            "display_name": "Admin User",
        },
    )
    assert response.status_code == 201
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_backoffice_access_requires_auth(client: TestClient) -> None:
    response = client.get("/backoffice/access")
    assert response.status_code == 401


def test_backoffice_access_denied_for_learner(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/backoffice/access", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["allowed"] is False
    assert data["role"] == "learner"


def test_backoffice_access_allowed_for_admin(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.get("/backoffice/access", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["allowed"] is True
    assert data["role"] == "admin"


def test_knowledge_overview_requires_admin(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/backoffice/knowledge", headers=auth_headers)
    assert response.status_code == 403


@patch("app.api.routes.backoffice.get_knowledge_overview")
def test_knowledge_overview_returns_sources(
    mock_overview: MagicMock,
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    get_settings.cache_clear()
    created = datetime.now(UTC)
    mock_overview.return_value = KnowledgeOverview(
        total_chunks=12,
        embedding_provider="gemini:text-embedding-004",
        embedding_enabled=True,
        sources=[
            KnowledgeSourceOverview(
                id="11111111-1111-1111-1111-111111111111",
                manifest_id="space-cubesat-101-basics",
                title="LUNAR CubeSat Basics",
                filename="01-cubesat-basics.md",
                type="markdown",
                module="space",
                stage="cubesat-101",
                source_origin="manifest",
                language="th",
                topic="cubesat-101",
                license=None,
                chunk_count=4,
                last_ingested_at=None,
                created_at=created,
            )
        ],
    )

    response = client.get("/backoffice/knowledge", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_chunks"] == 12
    assert data["sources"][0]["module"] == "space"


@patch("app.api.routes.backoffice.sync_manifest_sources")
def test_knowledge_sync_manifest(
    mock_sync: MagicMock,
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    get_settings.cache_clear()
    mock_sync.return_value = IngestRunResult(
        total_chunks=10,
        results=[IngestSourceResult(source_id="space-cubesat-101-basics", chunks_ingested=2)],
    )

    response = client.post(
        "/backoffice/knowledge/sync-manifest",
        headers=admin_headers,
        json={"source_id": "all"},
    )
    assert response.status_code == 200
    assert response.json()["total_chunks"] == 10


@patch("app.api.routes.backoffice.ingest_knowledge")
def test_knowledge_ingest_all(
    mock_ingest: MagicMock,
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    get_settings.cache_clear()
    mock_ingest.return_value = IngestRunResult(
        total_chunks=7,
        results=[IngestSourceResult(source_id="11111111-1111-1111-1111-111111111111", chunks_ingested=7)],
    )

    response = client.post(
        "/backoffice/knowledge/ingest",
        headers=admin_headers,
        json={"source_id": "all"},
    )
    assert response.status_code == 200
    assert response.json()["total_chunks"] == 7


def test_knowledge_ingest_requires_admin(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/backoffice/knowledge/ingest",
        headers=auth_headers,
        json={"source_id": "all"},
    )
    assert response.status_code == 403


@patch("app.api.routes.backoffice.upload_and_ingest")
def test_knowledge_upload(
    mock_upload: MagicMock,
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    get_settings.cache_clear()
    mock_upload.return_value = UploadKnowledgeResult(
        source_id="22222222-2222-2222-2222-222222222222",
        title="Test Doc",
        filename="notes.md",
        source_type="markdown",
        chunks_ingested=3,
    )

    response = client.post(
        "/backoffice/knowledge/upload",
        headers=admin_headers,
        files={"file": ("notes.md", BytesIO(b"# Hello"), "text/markdown")},
        data={"title": "Test Doc", "topic": "demo", "language": "th"},
    )
    assert response.status_code == 200
    assert response.json()["chunks_ingested"] == 3


@pytest.fixture()
def learner_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/register",
        json={
            "email": "learner@lunar.dev",
            "password": "testpass123",
            "display_name": "Learner User",
        },
    )
    assert response.status_code == 201
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_users_list_requires_admin(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/backoffice/users", headers=auth_headers)
    assert response.status_code == 403


def test_users_list_returns_all_users(
    client: TestClient, admin_headers: dict[str, str], learner_headers: dict[str, str]
) -> None:
    response = client.get("/backoffice/users", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    emails = {u["email"] for u in data["users"]}
    assert "admin@lunar.dev" in emails
    assert "learner@lunar.dev" in emails
    assert data["admin_count"] >= 1


def test_users_update_role_promote(
    client: TestClient, admin_headers: dict[str, str], learner_headers: dict[str, str]
) -> None:
    list_response = client.get("/backoffice/users", headers=admin_headers)
    learner = next(u for u in list_response.json()["users"] if u["email"] == "learner@lunar.dev")

    response = client.patch(
        f"/backoffice/users/{learner['id']}",
        headers=admin_headers,
        json={"role": "admin"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_users_update_role_cannot_change_self(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    list_response = client.get("/backoffice/users", headers=admin_headers)
    admin = next(u for u in list_response.json()["users"] if u["email"] == "admin@lunar.dev")

    response = client.patch(
        f"/backoffice/users/{admin['id']}",
        headers=admin_headers,
        json={"role": "learner"},
    )
    assert response.status_code == 400
    assert "own role" in response.json()["detail"].lower()


def test_users_update_role_requires_admin(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.patch(
        "/backoffice/users/11111111-1111-1111-1111-111111111111",
        headers=auth_headers,
        json={"role": "admin"},
    )
    assert response.status_code == 403


@patch("app.api.routes.backoffice.get_knowledge_catalog")
def test_knowledge_catalog_returns_modules(
    mock_catalog: MagicMock,
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    from datetime import UTC, datetime

    from app.services.knowledge.ingest import (
        KnowledgeCatalog,
        KnowledgeCatalogItem,
        KnowledgeModuleGroup,
    )

    created = datetime.now(UTC)
    mock_catalog.return_value = KnowledgeCatalog(
        total_chunks=5,
        embedding_provider="gemini:text-embedding-004",
        embedding_enabled=True,
        modules=[
            KnowledgeModuleGroup(
                module="space",
                sources=[
                    KnowledgeCatalogItem(
                        manifest_id="space-cubesat-101-basics",
                        title="CubeSat Basics",
                        module="space",
                        stage="cubesat-101",
                        order=1,
                        path="space/cubesat-101/01-cubesat-basics.md",
                        type="markdown",
                        language="th",
                        topic="cubesat-101",
                        synced=True,
                        id="11111111-1111-1111-1111-111111111111",
                        filename="01-cubesat-basics.md",
                        chunk_count=4,
                        last_ingested_at=None,
                        created_at=created,
                    )
                ],
            )
        ],
        uploads=[],
    )

    response = client.get("/backoffice/knowledge/catalog", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["modules"][0]["module"] == "space"
    assert data["modules"][0]["sources"][0]["synced"] is True


def test_knowledge_catalog_requires_admin(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/backoffice/knowledge/catalog", headers=auth_headers)
    assert response.status_code == 403


@patch("app.api.routes.backoffice.get_knowledge_source_detail")
def test_knowledge_source_detail(
    mock_detail: MagicMock,
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    from app.services.knowledge.ingest import KnowledgeSourceDetail

    mock_detail.return_value = KnowledgeSourceDetail(
        id="11111111-1111-1111-1111-111111111111",
        manifest_id="space-cubesat-101-basics",
        title="CubeSat Basics",
        filename="01-cubesat-basics.md",
        type="markdown",
        module="space",
        stage="cubesat-101",
        source_origin="manifest",
        language="th",
        topic="cubesat-101",
        license=None,
        content="# Hello",
        content_editable=True,
        chunk_count=4,
        last_ingested_at=None,
    )

    response = client.get(
        "/backoffice/knowledge/sources/11111111-1111-1111-1111-111111111111",
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["content"] == "# Hello"


@patch("app.api.routes.backoffice.update_knowledge_source")
def test_knowledge_source_update(
    mock_update: MagicMock,
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    from app.services.knowledge.ingest import UpdateKnowledgeSourceResult

    mock_update.return_value = UpdateKnowledgeSourceResult(
        id="11111111-1111-1111-1111-111111111111",
        title="Updated Title",
        chunks_ingested=3,
    )

    response = client.patch(
        "/backoffice/knowledge/sources/11111111-1111-1111-1111-111111111111",
        headers=admin_headers,
        json={"title": "Updated Title", "content": "# Updated"},
    )
    assert response.status_code == 200
    assert response.json()["chunks_ingested"] == 3


def test_knowledge_upload_requires_admin(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/backoffice/knowledge/upload",
        headers=auth_headers,
        files={"file": ("notes.md", BytesIO(b"# Hello"), "text/markdown")},
    )
    assert response.status_code == 403
