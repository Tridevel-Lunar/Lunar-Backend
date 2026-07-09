from langchain_core.language_models import BaseChatModel
from langchain_groq import ChatGroq

from app.core.config import Settings


def build_groq_llm(settings: Settings) -> BaseChatModel:
    if not settings.groq_api_key:
        raise ValueError("GROQ_API_KEY is required when LAIKA_LLM_PROVIDER=groq")
    return ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=0.3,
        timeout=settings.laika_timeout_seconds,
    )
