import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest")
os.environ.setdefault("GOOGLE_CLIENT_ID", "")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")

from app.core.config import get_settings
from app.schemas.laika import AssistResponse, LaikaSource
from app.main import app
from tests.conftest import auth_headers, client  # noqa: F401


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_laika_health_disabled_without_keys(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "")
    get_settings.cache_clear()
    response = client.get("/laika/health")
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is False
    assert data["llm_provider"] == "gemini"
    assert data["context_window"] > 0
    assert data["max_history_tokens"] == 8000


def test_laika_health_enabled_with_key(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    get_settings.cache_clear()
    response = client.get("/laika/health")
    assert response.status_code == 200
    assert response.json()["enabled"] is True





from app.schemas.laika import AssistRequest


def test_assist_request_drops_empty_messages() -> None:
    request = AssistRequest.model_validate(
        {
            "entry_type": "note",
            "content": "คำถาม",
            "intent": "explain",
            "messages": [
                {"role": "user", "content": "สวัสดี"},
                {"role": "assistant", "content": ""},
                {"role": "user", "content": "   "},
                {"role": "assistant", "content": "ตอบแล้ว"},
            ],
        }
    )
    assert len(request.messages) == 2
    assert request.messages[0].content == "สวัสดี"
    assert request.messages[1].content == "ตอบแล้ว"



@patch("app.services.laika_stream.stream_laika_assist")
def test_laika_assist_stream_returns_sse(
    mock_stream: MagicMock,
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    get_settings.cache_clear()

    def fake_stream(_db, _settings, _request, cancel_event=None):
        yield ("status", "embedding")
        yield ("status", "searching")
        yield ("status", "generating")
        yield ("token", "สวัสดี")
        yield ("token", " LAIKA")
        yield (
            "done",
            [
                LaikaSource(
                    source_id="lunar-power-budget",
                    title="LUNAR Power Budget Notes",
                    page=None,
                    topic="power-budget",
                    snippet="Energy = 5 W × …",
                )
            ],
        )

    mock_stream.side_effect = fake_stream

    with client.stream(
        "POST",
        "/laika/assist/stream",
        headers=auth_headers,
        json={
            "entry_type": "note",
            "content": "แบต 30% พอไหม",
            "intent": "explain",
        },
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())

    assert "event: status" in body
    assert '"phase": "embedding"' in body
    assert "event: token" in body
    assert '"delta": "สวัสดี"' in body
    assert '"source_id": "lunar-power-budget"' in body
    assert "event: done" in body


def test_laika_assist_stream_requires_auth(client: TestClient) -> None:
    response = client.post(
        "/laika/assist/stream",
        json={
            "entry_type": "note",
            "content": "test note",
            "intent": "explain",
        },
    )
    assert response.status_code == 401


@patch("app.services.laika_stream.stream_laika_assist")
def test_laika_assist_stream_emits_error_event(
    mock_stream: MagicMock,
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    get_settings.cache_clear()

    def fake_stream(_db, _settings, _request, cancel_event=None):
        raise RuntimeError("CUDA error: shared object initialization failed")
        yield  # pragma: no cover

    mock_stream.side_effect = fake_stream

    with client.stream(
        "POST",
        "/laika/assist/stream",
        headers=auth_headers,
        json={
            "entry_type": "note",
            "content": "test",
            "intent": "explain",
        },
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    assert "event: error" in body
    assert "CUDA" in body or "Ollama" in body






@patch("app.api.routes.laika.run_studio_greeting")
def test_laika_studio_greeting_returns_text(
    mock_greeting: MagicMock,
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.schemas.laika import StudioGreetingResponse

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    get_settings.cache_clear()
    mock_greeting.return_value = StudioGreetingResponse(
        greeting="สวัสดี ยินดีต้อนรับสู่ Studio",
    )

    response = client.post(
        "/laika/studio/greeting",
        headers=auth_headers,
        json={
            "learning_context": {
                "course": "CUBESAT 101",
                "completed_topics": ["Physics (LEO)"],
                "arena_missions": [],
            },
        },
    )
    assert response.status_code == 200
    assert "Studio" in response.json()["greeting"] or "สวัสดี" in response.json()["greeting"]


def test_laika_studio_greeting_requires_auth(client: TestClient) -> None:
    response = client.post("/laika/studio/greeting", json={})
    assert response.status_code == 401


def test_laika_studio_greeting_503_when_llm_disabled(
    client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "")
    get_settings.cache_clear()
    response = client.post(
        "/laika/studio/greeting",
        headers=auth_headers,
        json={},
    )
    assert response.status_code == 503
