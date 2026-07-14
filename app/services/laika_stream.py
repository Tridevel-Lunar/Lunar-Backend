from __future__ import annotations

import asyncio
import json
import queue
import threading
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from typing import Any

from sqlalchemy.orm import Session

from datetime import datetime, UTC

from app.core.config import Settings
from app.models.user import User
from app.schemas.laika import AssistRequest, LaikaSource
from app.services.laika import stream_laika_assist
from app.services.laika_errors import laika_provider_error_message
from app.services.rag.status import laika_status_message


def stream_event_to_ws_message(event_type: str, value: object) -> dict[str, Any]:
    if event_type == "status":
        phase = value
        assert isinstance(phase, str)
        return {
            "type": "status",
            "phase": phase,
            "message": laika_status_message(phase),  # type: ignore[arg-type]
        }
    if event_type == "token":
        return {"type": "token", "delta": value}
    if event_type == "done":
        if isinstance(value, dict):
            sources = value.get("sources", [])
            response = value.get("response", "")
            finish_reason = value.get("finish_reason")
            truncated = value.get("truncated", False)
        else:
            sources = value
            response = ""
            finish_reason = None
            truncated = False
        return {
            "type": "done",
            "sources": [
                source.model_dump() if hasattr(source, "model_dump") else source
                for source in sources  # type: ignore[union-attr]
            ],
            "response": response,
            "finish_reason": finish_reason,
            "truncated": truncated,
        }
    return {"type": "done", "sources": [], "response": ""}


def format_sse(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def stream_event_to_sse(event_type: str, value: object) -> str:
    message = stream_event_to_ws_message(event_type, value)
    kind = message["type"]
    if kind == "status":
        return format_sse(
            "status",
            {"phase": message["phase"], "message": message["message"]},
        )
    if kind == "token":
        return format_sse("token", {"delta": message["delta"]})
    return format_sse(
        "done",
        {
            "sources": message["sources"],
            "response": message.get("response", ""),
            "finish_reason": message.get("finish_reason"),
            "truncated": message.get("truncated", False),
        },
    )


def _save_streaming_buffer(
    db: Session,
    user: User,
    request: AssistRequest,
    buffer: list[str],
) -> None:
    """Save accumulated streaming text to the collection's tree in DB."""
    from app.services import studio as studio_service

    text = "".join(buffer).strip()
    if not text or not request.collection_id or not request.assistant_node_id:
        return

    import uuid
    try:
        cid = uuid.UUID(request.collection_id)
    except ValueError:
        return

    row = studio_service.get_collection(db, user, cid)
    if not row:
        return

    tree = row.tree
    nodes = tree.get("nodes", {})
    if not isinstance(nodes, dict):
        return

    node = nodes.get(request.assistant_node_id)
    if not isinstance(node, dict):
        return
    if node.get("role") != "assistant":
        return

    node["content"] = text
    tree["nodes"] = nodes

    row.tree = tree
    row.updated_at = datetime.now(UTC)
    db.commit()


def iter_laika_assist_sse(
    db: Session,
    settings: Settings,
    request: AssistRequest,
    user: User,
    cancel: threading.Event,
) -> Iterator[str]:
    """Sync SSE iterator — yields directly from the LLM stream without a thread queue.
    Accumulates tokens and auto-saves to DB on done or cancel.
    """
    buffer: list[str] = []
    try:
        for event_type, value in stream_laika_assist(
            db,
            settings,
            request,
            cancel_event=cancel,
        ):
            if cancel.is_set():
                _save_streaming_buffer(db, user, request, buffer)
                break
            if event_type == "token":
                buffer.append(str(value))
            yield stream_event_to_sse(event_type, value)
        if not cancel.is_set():
            _save_streaming_buffer(db, user, request, buffer)
    except GeneratorExit:
        cancel.set()
        _save_streaming_buffer(db, user, request, buffer)
        raise
    except Exception as exc:
        if not cancel.is_set():
            yield format_sse("error", {"detail": laika_provider_error_message(exc)})


def _produce_stream(
    out: queue.SimpleQueue[dict[str, Any]],
    db: Session,
    settings: Settings,
    request: AssistRequest,
    cancel: threading.Event,
) -> None:
    try:
        for event_type, value in stream_laika_assist(
            db, settings, request, cancel_event=cancel
        ):
            if cancel.is_set():
                out.put({"kind": "stopped"})
                return
            out.put(
                {
                    "kind": "message",
                    "event_type": event_type,
                    "value": value,
                }
            )
        if cancel.is_set():
            out.put({"kind": "stopped"})
        else:
            out.put({"kind": "finished"})
    except Exception as exc:
        out.put({"kind": "error", "detail": laika_provider_error_message(exc)})


async def _next_stream_item(
    out: queue.SimpleQueue[dict[str, Any]],
    thread: threading.Thread,
    *,
    cancel: threading.Event,
    is_disconnected: Callable[[], Awaitable[bool]] | None = None,
) -> dict[str, Any] | None:
    while thread.is_alive() or not out.empty():
        if is_disconnected and await is_disconnected():
            cancel.set()
            return None
        try:
            return out.get_nowait()
        except queue.Empty:
            await asyncio.sleep(0)
    return None


async def pump_laika_assist_sse(
    db: Session,
    settings: Settings,
    request: AssistRequest,
    cancel: threading.Event,
    *,
    is_disconnected: Callable[[], Awaitable[bool]] | None = None,
) -> AsyncIterator[str]:
    """Async SSE pump for callers that need disconnect polling (legacy)."""
    out: queue.SimpleQueue[dict[str, Any]] = queue.SimpleQueue()
    thread = threading.Thread(
        target=_produce_stream,
        args=(out, db, settings, request, cancel),
        daemon=True,
        name="laika-assist-stream",
    )
    thread.start()

    try:
        while True:
            item = await _next_stream_item(
                out,
                thread,
                cancel=cancel,
                is_disconnected=is_disconnected,
            )
            if item is None:
                break

            kind = item["kind"]
            if kind == "message":
                yield stream_event_to_sse(item["event_type"], item["value"])
                await asyncio.sleep(0)
            elif kind == "stopped":
                return
            elif kind == "finished":
                return
            elif kind == "error":
                yield format_sse("error", {"detail": item["detail"]})
                return
    finally:
        cancel.set()
        thread.join(timeout=2.0)
