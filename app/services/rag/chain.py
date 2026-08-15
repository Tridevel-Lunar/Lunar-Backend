from collections.abc import Iterator
from dataclasses import dataclass
from threading import Event
from typing import Any, Literal

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.schemas.laika import AssistRequest, AssistResponse, LaikaSource
from app.services.rag.context_window import build_human_prompt, trim_request_history
from app.services.rag.prompts import get_intent_system_prompt, RetrievedChunk
from app.services.rag.providers import get_llm
from app.services.rag.retriever import PgVectorRetriever
from app.services.rag.sources import build_sources
from app.services.rag.status import LaikaStatusPhase
from app.services.rag.tools import (
    MAX_TOOL_ROUNDS,
    execute_tool_call,
    make_knowledge_tool,
    make_web_tool,
    tool_name_to_status,
)
from app.services.rag.web_search import format_web_results, search_web, web_results_to_sources

StreamDonePayload = dict[str, Any]

StreamEvent = (
    tuple[Literal["status"], LaikaStatusPhase]
    | tuple[Literal["token"], str]
    | tuple[Literal["done"], StreamDonePayload]
)


def _is_cancelled(cancel_event: Event | None) -> bool:
    return cancel_event is not None and cancel_event.is_set()


def _chunk_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(content) if content else ""


@dataclass
class _LlmStreamMeta:
    finish_reason: str | None = None


def _stream_llm_deltas(
    llm: object,
    messages: list[BaseMessage],
    *,
    cancel_event: Event | None,
    meta: _LlmStreamMeta,
) -> Iterator[tuple[str, str]]:
    """Yield (delta, full_text_so_far) using LangChain chunk merge for reliable deltas."""
    gathered: AIMessageChunk | None = None
    previous_text = ""

    for chunk in llm.stream(messages):  # type: ignore[attr-defined]
        if _is_cancelled(cancel_event):
            return
        if isinstance(chunk, AIMessageChunk):
            gathered = chunk if gathered is None else gathered + chunk
            current_text = _chunk_text(gathered.content)
            reason = (chunk.response_metadata or {}).get("done_reason")
            if reason:
                meta.finish_reason = str(reason)
        else:
            piece = _chunk_text(getattr(chunk, "content", chunk))
            current_text = previous_text + piece

        delta = current_text[len(previous_text) :]
        previous_text = current_text
        if delta:
            yield delta, current_text


class RagChain:
    def __init__(self, db: Session, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._retriever = PgVectorRetriever(db, settings)
        self._llm = get_llm(settings)
        self._tools = [make_knowledge_tool(self._retriever), make_web_tool()]
        self._llm_with_tools = self._llm.bind_tools(self._tools)

    # ── Standard mode helpers (pre-fetch RAG + optional web) ──────────────

    def _build_messages(
        self, request: AssistRequest, chunks: list[RetrievedChunk], *, web_context: str = ""
    ) -> list[BaseMessage]:
        from app.services.rag.prompts import format_context

        trimmed_request, _ = trim_request_history(self._settings, request)
        rag_context = format_context(chunks)
        if web_context:
            rag_context = f"{rag_context}\n\n## Web search results\n\n{web_context}"
        system_prompt = get_intent_system_prompt(trimmed_request.intent)
        human_prompt = build_human_prompt(
            trimmed_request, rag_context=rag_context, history=trimmed_request.messages,
        )
        return [SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)]

    def _prepare_standard(
        self, request: AssistRequest
    ) -> tuple[list[BaseMessage], list[RetrievedChunk], list[LaikaSource]]:
        query = f"{request.intent}: {request.content}"
        chunks = self._retriever.retrieve(query)
        web_sources: list[LaikaSource] = []
        web_context = ""
        if request.web_search:
            web_results = search_web(query, max_results=3)
            web_context = format_web_results(web_results)
            web_sources = web_results_to_sources(web_results)
        return self._build_messages(request, chunks, web_context=web_context), chunks, web_sources

    # ── Extra mode helpers (agentic tool-calling) ─────────────────────────

    def _build_initial_messages(self, request: AssistRequest) -> list[BaseMessage]:
        trimmed_request, _ = trim_request_history(self._settings, request)
        system_prompt = get_intent_system_prompt(trimmed_request.intent)
        human_prompt = build_human_prompt(trimmed_request, rag_context="", history=trimmed_request.messages)
        return [SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)]

    # ── Dispatch ──────────────────────────────────────────────────────────

    def run(self, request: AssistRequest) -> AssistResponse:
        if request.mode == "extra":
            return self._run_extra(request)
        return self._run_standard(request)

    def stream(
        self, request: AssistRequest, *, cancel_event: Event | None = None
    ) -> Iterator[StreamEvent]:
        if request.mode == "extra":
            yield from self._stream_extra(request, cancel_event=cancel_event)
        else:
            yield from self._stream_standard(request, cancel_event=cancel_event)

    # ── Standard mode ─────────────────────────────────────────────────────

    def _run_standard(self, request: AssistRequest) -> AssistResponse:
        messages, chunks, web_sources = self._prepare_standard(request)
        response = self._llm.invoke(messages)
        text = _chunk_text(response.content)
        all_sources = build_sources(chunks) + web_sources
        return AssistResponse(response=text.strip(), sources=all_sources)

    def _stream_standard(
        self, request: AssistRequest, *, cancel_event: Event | None = None
    ) -> Iterator[StreamEvent]:
        if _is_cancelled(cancel_event):
            return
        query = f"{request.intent}: {request.content}"
        yield ("status", "embedding")
        query_vector = self._retriever.embed_query(query)

        if _is_cancelled(cancel_event):
            return

        web_sources: list[LaikaSource] = []
        web_context = ""
        if request.web_search:
            yield ("status", "searching_web")
            web_results = search_web(query, max_results=3)
            web_context = format_web_results(web_results)
            web_sources = web_results_to_sources(web_results)

        yield ("status", "searching")
        chunks = self._retriever.search(query_vector)
        messages = self._build_messages(request, chunks, web_context=web_context)
        sources = build_sources(chunks) + web_sources

        if _is_cancelled(cancel_event):
            return

        yield ("status", "generating")
        stream_meta = _LlmStreamMeta()
        full_response = ""
        for delta, current_text in _stream_llm_deltas(self._llm, messages, cancel_event=cancel_event, meta=stream_meta):
            full_response = current_text
            if delta:
                yield ("token", delta)

        if _is_cancelled(cancel_event):
            return

        yield ("done", {
            "sources": sources, "response": full_response.strip(),
            "finish_reason": stream_meta.finish_reason, "truncated": stream_meta.finish_reason == "length",
        })

    # ── Extra / Agentic mode ──────────────────────────────────────────────

    def _run_extra(self, request: AssistRequest) -> AssistResponse:
        messages = self._build_initial_messages(request)
        all_sources: list[LaikaSource] = []

        for _round in range(MAX_TOOL_ROUNDS):
            response = self._llm_with_tools.invoke(messages)
            if not isinstance(response, AIMessage):
                break
            tool_calls = getattr(response, "tool_calls", [])
            if not tool_calls:
                return AssistResponse(response=_chunk_text(response.content).strip(), sources=all_sources)
            messages.append(response)
            for tc in tool_calls:
                result_text, result_sources = execute_tool_call(tc, self._retriever)
                all_sources.extend(result_sources)
                messages.append(ToolMessage(content=result_text, tool_call_id=tc["id"]))

        final = self._llm_with_tools.invoke(messages)
        return AssistResponse(response=_chunk_text(final.content).strip(), sources=all_sources)

    def _stream_extra(
        self, request: AssistRequest, *, cancel_event: Event | None = None
    ) -> Iterator[StreamEvent]:
        if _is_cancelled(cancel_event):
            return
        yield ("status", "embedding")
        messages = self._build_initial_messages(request)
        all_sources: list[LaikaSource] = []

        for _round in range(MAX_TOOL_ROUNDS):
            if _is_cancelled(cancel_event):
                return
            yield ("status", "reasoning")
            response = self._llm_with_tools.invoke(messages)
            if not isinstance(response, AIMessage):
                break

            tool_calls = getattr(response, "tool_calls", [])
            if tool_calls:
                messages.append(response)
                for tc in tool_calls:
                    yield ("status", tool_name_to_status(tc["name"]))
                    result_text, result_sources = execute_tool_call(tc, self._retriever)
                    all_sources.extend(result_sources)
                    messages.append(ToolMessage(content=result_text, tool_call_id=tc["id"]))
                continue

            messages.append(response)
            yield ("status", "generating")
            finish_reason = None
            full_response = ""
            for chunk in self._llm_with_tools.stream(messages):
                if _is_cancelled(cancel_event):
                    return
                if isinstance(chunk, AIMessageChunk):
                    reason = _extract_finish_reason(chunk)
                    if reason:
                        finish_reason = reason
                    piece = _chunk_text(chunk.content)
                    if piece:
                        full_response += piece
                        yield ("token", piece)

            if not full_response:
                final = _chunk_text(response.content)
                if final:
                    full_response = final
                    yield ("token", final)

            yield ("done", {
                "sources": all_sources, "response": full_response.strip(),
                "finish_reason": finish_reason, "truncated": finish_reason == "length",
            })
            return

        if _is_cancelled(cancel_event):
            return
        yield ("status", "generating")
        final = self._llm_with_tools.invoke(messages)
        text = _chunk_text(final.content)
        yield ("token", text)
        yield ("done", {"sources": all_sources, "response": text.strip(), "finish_reason": None, "truncated": False})


def _extract_finish_reason(chunk: object) -> str | None:
    """Extract finish reason from an LLM chunk if available."""
    meta = getattr(chunk, "response_metadata", None) or {}
    return meta.get("done_reason") if isinstance(meta, dict) else None
