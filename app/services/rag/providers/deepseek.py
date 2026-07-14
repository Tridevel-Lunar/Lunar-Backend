"""DeepSeek LLM provider (OpenAI-compatible API).

Uses ``langchain-openai``'s ``ChatOpenAI`` with ``base_url`` set to
``https://api.deepseek.com/v1`` for the DeepSeek API.

Requires ``DEEPSEEK_API_KEY`` in environment.
"""

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.core.config import Settings


def build_deepseek_llm(settings: Settings) -> BaseChatModel:
    if not settings.deepseek_api_key:
        raise ValueError("DEEPSEEK_API_KEY is required when LAIKA_LLM_PROVIDER=deepseek")
    return ChatOpenAI(
        model=settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        base_url="https://api.deepseek.com/v1",
        temperature=0.3,
        timeout=settings.laika_timeout_seconds,
        streaming=True,
    )
