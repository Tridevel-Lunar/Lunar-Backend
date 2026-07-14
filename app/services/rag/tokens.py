"""Heuristic token estimates for LAIKA context budgeting (Thai + English mixed text)."""

from __future__ import annotations

from app.core.config import Settings

# Conservative Ollama budget when OLLAMA_NUM_CTX / LAIKA_CONTEXT_WINDOW unset.
OLLAMA_DEFAULT_NUM_CTX = 4096

# Theoretical model limits (cloud / fully configured local).
MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "gemini-2.0-flash": 1_048_576,
    "gemini-2.5-flash": 1_048_576,
    "llama-3.3-70b": 131_072,
    "deepseek-chat": 64_000,
    "deepseek-reasoner": 64_000,
    "qwen2.5:7b": 32_768,
    "qwen2.5": 32_768,
    "gemma4:e4b": 131_072,
    "gemma4:e2b": 131_072,
    "gemma4:12b": 262_144,
    "gemma4:26b": 262_144,
    "gemma4:31b": 262_144,
    "gemma4": 131_072,
    "gemma3:4b-it": 8_192,
    "gemma3:4b": 8_192,
    "gemma3:1b": 32_768,
    "gemma3:12b": 8_192,
    "gemma3:27b": 8_192,
    "gemma3": 8_192,
    "gemma2:2b": 8_192,
    "gemma2": 8_192,
}

# Ingest chunk_size from laika.md + citation overhead per chunk.
RAG_CHUNK_CHAR_ESTIMATE = 1_120
RAG_EMPTY_CONTEXT_CHARS = 34


def estimate_tokens(text: str) -> int:
    """Rough BPE-style estimate: ~2.5 chars/token for Thai-heavy text."""
    if not text:
        return 0
    return max(1, (len(text) + 2) // 3)


def llm_model_label(settings: Settings) -> str:
    if settings.laika_llm_provider == "gemini":
        return settings.gemini_model
    if settings.laika_llm_provider == "deepseek":
        return settings.deepseek_model
    return settings.ollama_llm_model


def resolve_context_window(settings: Settings) -> int:
    if settings.laika_context_window > 0:
        return settings.laika_context_window
    if settings.laika_llm_provider == "ollama":
        num_ctx = resolve_ollama_num_ctx(settings)
        if num_ctx is not None:
            return num_ctx
        # Do not assume 128K — local Ollama defaults are much smaller unless configured.
        return OLLAMA_DEFAULT_NUM_CTX
    model = llm_model_label(settings).lower()
    for key in sorted(MODEL_CONTEXT_WINDOWS.keys(), key=len, reverse=True):
        if key in model:
            return MODEL_CONTEXT_WINDOWS[key]
    if settings.laika_llm_provider == "gemini":
        return 1_048_576
    if settings.laika_llm_provider == "deepseek":
        return 64_000
    return 8_192


def resolve_ollama_num_ctx(settings: Settings) -> int | None:
    """VRAM-safe num_ctx for Ollama inference. None = let Ollama use model default."""
    if settings.ollama_num_ctx > 0:
        return min(settings.ollama_num_ctx, 65_536)
    return None
