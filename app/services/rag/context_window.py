from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.schemas.laika import AssistRequest, ChatMessage, LaikaIntent
from app.services.rag.learner import format_learner_identity
from app.services.rag.prompts import INTENT_SYSTEM_PROMPTS, format_learning_context
from app.services.rag.session_time import (
    format_conversation_timing_hint,
    format_datetime_bangkok,
    format_message_timestamp,
    resolve_now,
)
from app.services.rag.tokens import (
    RAG_CHUNK_CHAR_ESTIMATE,
    RAG_EMPTY_CONTEXT_CHARS,
    estimate_tokens,
    resolve_context_window,
)


@dataclass(frozen=True)
class ContextSegment:
    key: str
    label: str
    tokens: int


@dataclass(frozen=True)
class ContextUsage:
    context_window: int
    reserved_output: int
    input_budget: int
    used_input: int
    remaining_input: int
    usage_ratio: float
    segments: list[ContextSegment]
    history_message_count: int
    history_trimmed_count: int
    history_kept_count: int


def estimate_rag_tokens(top_k: int) -> int:
    if top_k <= 0:
        return estimate_tokens("x" * RAG_EMPTY_CONTEXT_CHARS)
    per_chunk = estimate_tokens("x" * RAG_CHUNK_CHAR_ESTIMATE)
    return per_chunk * top_k + 24


def estimate_system_tokens(intent: LaikaIntent) -> int:
    return estimate_tokens(INTENT_SYSTEM_PROMPTS[intent])


def estimate_learning_tokens(learning_context: dict[str, object] | None) -> int:
    return estimate_tokens(format_learning_context(learning_context))


def _format_history(messages: list[ChatMessage]) -> str:
    if not messages:
        return ""
    parts: list[str] = []
    for msg in messages:
        speaker = "Learner" if msg.role == "user" else "LAIKA"
        ts = format_message_timestamp(msg.created_at)
        prefix = f"[{ts}] " if ts else ""
        parts.append(f"{prefix}{speaker}:\n{msg.content}")
    return "\n\n".join(parts)


def trim_messages(
    messages: list[ChatMessage],
    *,
    max_tokens: int,
) -> tuple[list[ChatMessage], int]:
    if max_tokens <= 0 or not messages:
        return [], len(messages)

    kept: list[ChatMessage] = []
    total = 0
    for msg in reversed(messages):
        msg_tokens = estimate_tokens(msg.content) + 8
        if kept and total + msg_tokens > max_tokens:
            break
        total += msg_tokens
        kept.insert(0, msg)

    dropped = len(messages) - len(kept)
    return kept, dropped


def normalize_assist_messages(request: AssistRequest) -> AssistRequest:
    """If the last history item duplicates `content`, treat it as the current turn."""
    messages = [m for m in request.messages if m.content.strip()]
    request = request.model_copy(update={"messages": messages})
    if not request.messages:
        return request
    last = request.messages[-1]
    if last.role == "user" and last.content.strip() == request.content.strip():
        return request.model_copy(update={"messages": request.messages[:-1]})
    return request


def build_human_prompt(
    request: AssistRequest,
    *,
    rag_context: str,
    history: list[ChatMessage],
) -> str:
    learning_context = format_learning_context(
        request.learning_context.model_dump() if request.learning_context else None
    )
    pinned = (request.entry_content or "").strip()
    history_text = _format_history(history)
    now = resolve_now(request.client_now)
    timing_hint = format_conversation_timing_hint(history, client_now=request.client_now)

    parts = [
        format_learner_identity(request.learner_display_name),
        f"Current date/time (Asia/Bangkok): {format_datetime_bangkok(now)}",
        f"Conversation continuity:\n{timing_hint}",
        f"Context:\n{rag_context}",
        f"Learner progress:\n{learning_context}",
        f"Entry type: {request.entry_type}",
    ]
    if pinned:
        parts.append(f"Original learner entry:\n{pinned}")
    if history_text:
        parts.append(f"Conversation history:\n{history_text}")
    parts.append(f"Current learner message:\n{request.content}")
    return "\n\n".join(parts)


WEB_SEARCH_TOKEN_ESTIMATE = 600  # ~3 DuckDuckGo results


def compute_context_usage(
    settings: Settings,
    *,
    intent: LaikaIntent,
    entry_content: str,
    current_content: str,
    draft: str = "",
    messages: list[ChatMessage] | None = None,
    learning_context: dict[str, object] | None = None,
    web_search: bool = False,
    mode: str = "standard",
) -> ContextUsage:
    context_window = resolve_context_window(settings)
    reserved_output = settings.laika_reserved_output_tokens
    input_budget = max(0, context_window - reserved_output)

    pending = (draft or current_content).strip()
    fixed_tokens = (
        estimate_system_tokens(intent)
        + estimate_rag_tokens(settings.laika_top_k)
        + estimate_learning_tokens(learning_context)
        + estimate_tokens(entry_content.strip())
        + estimate_tokens(pending)
        + 48
    )
    if web_search:
        fixed_tokens += WEB_SEARCH_TOKEN_ESTIMATE

    history_budget = max(0, settings.laika_max_history_tokens)
    history_budget = min(history_budget, max(0, input_budget - fixed_tokens))

    all_messages = list(messages or [])
    trimmed, dropped = trim_messages(all_messages, max_tokens=history_budget)
    history_tokens = estimate_tokens(_format_history(trimmed))

    segments = [
        ContextSegment("system", "System / persona", estimate_system_tokens(intent)),
        ContextSegment("rag", "Knowledge (RAG)", estimate_rag_tokens(settings.laika_top_k)),
        ContextSegment("learning", "Learning progress", estimate_learning_tokens(learning_context)),
        ContextSegment("entry", "โน้ตต้นทาง", estimate_tokens(entry_content.strip())),
    ]
    if web_search:
        segments.append(
            ContextSegment("web", "ค้นหาจากอินเทอร์เน็ต", WEB_SEARCH_TOKEN_ESTIMATE)
        )
    if mode == "extra":
        segments.append(
            ContextSegment("tool_loop", "Agentic tool loop", WEB_SEARCH_TOKEN_ESTIMATE * 2)
        )
    segments.append(ContextSegment("history", "ประวัติแชท", history_tokens))
    if pending:
        label = "กำลังพิมพ์" if draft.strip() else "ข้อความถัดไป"
        segments.append(ContextSegment("pending", label, estimate_tokens(pending)))

    used_input = sum(seg.tokens for seg in segments) + 48
    remaining_input = max(0, input_budget - used_input)
    usage_ratio = min(1.0, used_input / input_budget) if input_budget else 1.0

    return ContextUsage(
        context_window=context_window,
        reserved_output=reserved_output,
        input_budget=input_budget,
        used_input=used_input,
        remaining_input=remaining_input,
        usage_ratio=usage_ratio,
        segments=segments,
        history_message_count=len(all_messages),
        history_trimmed_count=dropped,
        history_kept_count=len(trimmed),
    )


def trim_request_history(
    settings: Settings,
    request: AssistRequest,
) -> tuple[AssistRequest, int]:
    request = normalize_assist_messages(request)
    context_window = resolve_context_window(settings)
    reserved = settings.laika_reserved_output_tokens
    input_budget = max(0, context_window - reserved)

    pinned = (request.entry_content or request.content).strip()
    fixed = (
        estimate_system_tokens(request.intent)
        + estimate_rag_tokens(settings.laika_top_k)
        + estimate_learning_tokens(
            request.learning_context.model_dump() if request.learning_context else None
        )
        + estimate_tokens(pinned)
        + estimate_tokens(request.content.strip())
        + 64
    )
    history_budget = min(
        settings.laika_max_history_tokens,
        max(0, input_budget - fixed),
    )
    trimmed, dropped = trim_messages(request.messages, max_tokens=history_budget)
    return request.model_copy(update={"messages": trimmed}), dropped
