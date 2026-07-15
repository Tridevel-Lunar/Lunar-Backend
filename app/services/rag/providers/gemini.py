from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

from app.core.config import Settings


def build_gemini_llm(settings: Settings) -> BaseChatModel:
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is required when LAIKA_LLM_PROVIDER=gemini")
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=0.3,
        timeout=settings.laika_timeout_seconds,
    )


def build_gemini_embeddings(settings: Settings) -> Embeddings:
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is required when LAIKA_EMBEDDING_PROVIDER=gemini")
    return GoogleGenerativeAIEmbeddings(
        model=settings.gemini_embedding_model,
        google_api_key=settings.gemini_api_key,
        output_dimensionality=768,
    )
