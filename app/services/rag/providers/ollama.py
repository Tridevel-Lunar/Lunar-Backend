from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama, OllamaEmbeddings

from app.core.config import Settings
from app.services.rag.tokens import resolve_ollama_num_ctx


def build_ollama_llm(settings: Settings) -> BaseChatModel:
    if not settings.ollama_base_url:
        raise ValueError("OLLAMA_BASE_URL is required when LAIKA_LLM_PROVIDER=ollama")
    num_ctx = resolve_ollama_num_ctx(settings)
    kwargs: dict[str, object] = {
        "model": settings.ollama_llm_model,
        "base_url": settings.ollama_base_url,
        "temperature": 0.3,
        "timeout": max(settings.laika_timeout_seconds, 300),
        "streaming": True,
        "num_predict": -1,
        "keep_alive": settings.ollama_keep_alive,
    }
    if num_ctx is not None:
        kwargs["num_ctx"] = num_ctx
    return ChatOllama(**kwargs)


def build_ollama_embeddings(settings: Settings) -> Embeddings:
    if not settings.ollama_base_url:
        raise ValueError("OLLAMA_BASE_URL is required when LAIKA_EMBEDDING_PROVIDER=ollama")
    return OllamaEmbeddings(
        model=settings.ollama_embed_model,
        base_url=settings.ollama_base_url,
    )
