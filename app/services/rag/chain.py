from collections.abc import Iterator
from dataclasses import dataclass
from threading import Event
from typing import Any, Literal

from langchain_core.messages import AIMessageChunk, BaseMessage, HumanMessage, SystemMessage
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.schemas.laika import AssistRequest, AssistResponse, LaikaSource
from app.services.rag.context_window import build_human_prompt, trim_request_history
from app.services.rag.prompts import (
    INTENT_SYSTEM_PROMPTS,
    RetrievedChunk,
)
from app.services.rag.providers import get_llm
from app.services.rag.retriever import PgVectorRetriever
from app.services.rag.sources import build_sources
from app.services.rag.status import LaikaStatusPhase
from app.services.rag.web_search import format_web_results, search_web, web_results_to_sources

StreamDonePayload = dict[str, Any]

StreamEvent = (
    tuple[Literal["status"], LaikaStatusPhase]
    | tuple[Literal["token"], str]
    | tuple[Literal["done"], StreamDonePayload]
)


@dataclass
class LlmStreamMeta:
    finish_reason: str | None = None


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


def _is_cancelled(cancel_event: Event | None) -> bool:
    return cancel_event is not None and cancel_event.is_set()


def _stream_llm_deltas(
    llm: object,
    messages: list[BaseMessage],
    *,
    cancel_event: Event | None,
    meta: LlmStreamMeta,
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

    def _build_messages(
        self,
        request: AssistRequest,
        chunks: list[RetrievedChunk],
        *,
        web_context: str = "",
    ) -> list[BaseMessage]:
        from app.services.rag.prompts import format_context

        trimmed_request, _ = trim_request_history(self._settings, request)
        rag_context = format_context(chunks)
        if web_context:
            rag_context = f"{rag_context}\n\n## Web search results\n\n{web_context}"
        system_prompt = INTENT_SYSTEM_PROMPTS[trimmed_request.intent]
        human_prompt = build_human_prompt(
            trimmed_request,
            rag_context=rag_context,
            history=trimmed_request.messages,
        )
        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt),
        ]

    def _prepare(
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

    def run(self, request: AssistRequest) -> AssistResponse:
        messages, chunks, web_sources = self._prepare(request)
        response = self._llm.invoke(messages)
        text = _chunk_text(response.content)
        all_sources = build_sources(chunks) + web_sources
        return AssistResponse(response=text.strip(), sources=all_sources)

    def stream(
        self,
        request: AssistRequest,
        *,
        cancel_event: Event | None = None,
    ) -> Iterator[StreamEvent]:
        query = f"{request.intent}: {request.content}"

        if _is_cancelled(cancel_event):
            return

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
        stream_meta = LlmStreamMeta()
        full_response = ""
        for delta, current_text in _stream_llm_deltas(
            self._llm,
            messages,
            cancel_event=cancel_event,
            meta=stream_meta,
        ):
            full_response = current_text
            if delta:
                yield ("token", delta)

        if _is_cancelled(cancel_event):
            return

        finish_reason = stream_meta.finish_reason
        yield (
            "done",
            {
                "sources": sources,
                "response": full_response.strip(),
                "finish_reason": finish_reason,
                "truncated": finish_reason == "length",
            },
        )
