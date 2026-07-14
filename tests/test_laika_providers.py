import os

import pytest
from langchain_core.embeddings import Embeddings
from pydantic import ValidationError
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest")
os.environ.setdefault("GOOGLE_CLIENT_ID", "")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "")

from app.core.config import Settings
from app.services.rag.providers import get_embeddings, get_llm
from app.services.rag.sources import build_sources
from app.services.rag.prompts import RetrievedChunk


class _FakeEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 768 for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.1] * 768


def test_get_llm_gemini_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAIKA_LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        get_llm(settings)


def test_get_llm_deepseek_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAIKA_LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        get_llm(settings)


def test_get_llm_ollama_builds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAIKA_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    from app.core.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    llm = get_llm(settings)
    assert llm is not None


def test_invalid_embedding_provider_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAIKA_EMBEDDING_PROVIDER", "deepseek")
    from app.core.config import get_settings

    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        get_settings()


def test_build_sources_dedupes_by_source_and_page() -> None:
    chunks = [
        RetrievedChunk("a", "cubesat-101", "NASA CubeSat 101", 42, "power", 0.9),
        RetrievedChunk("b", "cubesat-101", "NASA CubeSat 101", 42, "power", 0.8),
        RetrievedChunk("c", "lunar-power", "LUNAR Power", None, "power", 0.7),
    ]
    sources = build_sources(chunks)
    assert len(sources) == 2
    assert sources[0].source_id == "cubesat-101"
    assert sources[0].page == 42
    assert sources[1].source_id == "lunar-power"


def test_build_sources_always_returns_list() -> None:
    assert build_sources([]) == []
