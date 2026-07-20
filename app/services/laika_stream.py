from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from datetime import datetime, UTC

from app.core.config import Settings
from app.models.user import User
from app.schemas.laika import AssistRequest, StreamAssistRequest, LaikaSource
from app.services import studio_tree
from app.services.laika import stream_laika_assist
from app.services.laika_errors import laika_provider_error_message
from app.services.rag.learner import resolve_learner_display_name
from app.services.rag.status import laika_status_message


def _serialize_source(item: object) -> dict[str, Any]:
    if hasattr(item, "model_dump"):
        return item.model_dump()  # type: ignore[no-any-return]
    if isinstance(item, dict):
        return item
    raise TypeError(f"Unsupported LAIKA source type: {type(item)!r}")


def _serialize_done_payload(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "sources": [],
            "response": "",
            "finish_reason": None,
            "truncated": False,
        }

    sources_raw = value.get("sources") or []
    sources = [_serialize_source(item) for item in sources_raw] if isinstance(sources_raw, list) else []
    response = value.get("response")
    finish_reason = value.get("finish_reason")
    return {
        "sources": sources,
        "response": response if isinstance(response, str) else "",
        "finish_reason": finish_reason if isinstance(finish_reason, str) else None,
        "truncated": value.get("truncated") is True,
    }


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
        return {"type": "done", **_serialize_done_payload(value)}
    return {
        "type": "done",
        "sources": [],
        "response": "",
        "finish_reason": None,
        "truncated": False,
    }


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
            "sources": message.get("sources", []),
            "response": message.get("response", ""),
            "finish_reason": message.get("finish_reason"),
            "truncated": message.get("truncated", False),
        },
    )


def _save_streaming_buffer(
    db: Session,
    user: User,
    collection_id: str,
    assistant_node_id: str,
    buffer: list[str],
) -> None:
    """Save accumulated streaming text to the collection's tree in DB."""
    from app.services import studio as studio_service

    text = "".join(buffer).strip()
    if not text or not collection_id or not assistant_node_id:
        return

    import uuid
    try:
        cid = uuid.UUID(collection_id)
    except ValueError:
        return

    row = studio_service.get_collection(db, user, cid)
    if not row:
        return

    tree = row.tree
    nodes = tree.get("nodes", {})
    if not isinstance(nodes, dict):
        return

    node = nodes.get(assistant_node_id)
    if not isinstance(node, dict):
        return
    if node.get("role") != "assistant":
        return

    node["content"] = text
    tree["nodes"] = nodes

    row.tree = tree
    row.updated_at = datetime.now(UTC)
    flag_modified(row, "tree")
    db.commit()


def _prepare_tree(
    db: Session,
    user: User,
    request: StreamAssistRequest,
) -> tuple[str, str, AssistRequest]:
    """Create/update nodes in DB tree, return (user_node_id, assistant_node_id, full_request)."""
    from app.services import studio as studio_service

    import uuid
    try:
        cid = uuid.UUID(request.collection_id)
    except ValueError:
        raise ValueError(f"Invalid collection_id: {request.collection_id}")

    row = studio_service.get_collection(db, user, cid)
    if not row:
        raise ValueError(f"Collection not found: {request.collection_id}")

    tree = row.tree or {}
    new_tree, user_node_id, assistant_node_id = studio_tree.prepare_tree_for_stream(
        tree,
        mode=request.mode,
        content=request.content,
        intent=request.intent,
        node_id=request.node_id,
        parent_node_id=request.parent_node_id,
    )

    row.tree = new_tree
    row.updated_at = datetime.now(UTC)
    db.commit()

    # Build full AssistRequest with fields derived from DB
    messages = studio_tree.messages_from_tree(new_tree)
    if request.content.strip():
        messages.append({"role": "user", "content": request.content, "created_at": None})

    full_request = AssistRequest(
        entry_type=row.type,
        content=request.content,
        intent=request.intent,
        entry_content=row.content,
        messages=messages,
        learning_context=request.learning_context,
        client_now=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        learner_display_name=resolve_learner_display_name(user.display_name, user.email),
        web_search=request.web_search,
        mode=request.laika_mode,
    )

    return user_node_id, assistant_node_id, full_request


def iter_laika_assist_sse(
    db: Session,
    settings: Settings,
    request: StreamAssistRequest,
    user: User,
    cancel: threading.Event,
) -> Iterator[str]:
    """
    Sync SSE iterator — creates nodes from request, emits meta event, streams, auto-saves.
    """
    buffer: list[str] = []

    try:
        uid, aid, full_request = _prepare_tree(db, user, request)
        yield format_sse("meta", {"user_node_id": uid, "assistant_node_id": aid})
    except ValueError as exc:
        yield format_sse("error", {"detail": str(exc)})
        return

    try:
        for event_type, value in stream_laika_assist(
            db,
            settings,
            full_request,
            cancel_event=cancel,
        ):
            if cancel.is_set():
                _save_streaming_buffer(db, user, request.collection_id, aid, buffer)
                break
            if event_type == "token":
                buffer.append(str(value))
            elif event_type == "done":
                # Save BEFORE yielding done — frontend calls refreshConversation() on done
                _save_streaming_buffer(db, user, request.collection_id, aid, buffer)
            yield stream_event_to_sse(event_type, value)
    except GeneratorExit:
        cancel.set()
        _save_streaming_buffer(db, user, request.collection_id, aid, buffer)
        raise
    except Exception as exc:
        if not cancel.is_set():
            yield format_sse("error", {"detail": laika_provider_error_message(exc)})
