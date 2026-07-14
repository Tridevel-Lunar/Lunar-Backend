from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel

from app.core.config import Settings


def get_llm(settings: Settings) -> BaseChatModel:
    match settings.laika_llm_provider:
        case "gemini":
            from app.services.rag.providers.gemini import build_gemini_llm

            return build_gemini_llm(settings)
        case "deepseek":
            from app.services.rag.providers.deepseek import build_deepseek_llm

            return build_deepseek_llm(settings)
        case "ollama":
            from app.services.rag.providers.ollama import build_ollama_llm

            return build_ollama_llm(settings)
        case _:
            raise ValueError(f"Unknown LAIKA_LLM_PROVIDER: {settings.laika_llm_provider}")


def get_embeddings(settings: Settings) -> Embeddings:
    match settings.laika_embedding_provider:
        case "gemini":
            from app.services.rag.providers.gemini import build_gemini_embeddings

            return build_gemini_embeddings(settings)
        case "ollama":
            from app.services.rag.providers.ollama import build_ollama_embeddings

            return build_ollama_embeddings(settings)
        case _:
            raise ValueError("LAIKA_EMBEDDING_PROVIDER must be gemini or ollama")
