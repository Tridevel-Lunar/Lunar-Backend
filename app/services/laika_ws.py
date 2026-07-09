from __future__ import annotations

import asyncio
import queue
import threading
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.schemas.laika import AssistRequest
from app.services.laika_stream import (
    _next_stream_item,
    _produce_stream,
    stream_event_to_ws_message,
)


async def pump_laika_assist(
    websocket: WebSocket,
    db: Session,
    settings: Settings,
    request: AssistRequest,
    cancel: threading.Event,
) -> None:
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
            if cancel.is_set() and out.empty() and not thread.is_alive():
                break

            item = await _next_stream_item(out, thread, cancel=cancel)
            if item is None:
                break

            kind = item["kind"]
            if kind == "message":
                await websocket.send_json(
                    stream_event_to_ws_message(item["event_type"], item["value"])
                )
                await asyncio.sleep(0)
            elif kind == "stopped":
                await websocket.send_json({"type": "stopped"})
                return
            elif kind == "finished":
                return
            elif kind == "error":
                await websocket.send_json({"type": "error", "detail": item["detail"]})
                return

        if cancel.is_set():
            await websocket.send_json({"type": "stopped"})
    except WebSocketDisconnect:
        cancel.set()
        raise
    finally:
        cancel.set()
        thread.join(timeout=2.0)


async def watch_for_stop(websocket: WebSocket, cancel: threading.Event) -> None:
    try:
        while not cancel.is_set():
            message = await websocket.receive_json()
            if message.get("type") == "stop":
                cancel.set()
                return
    except WebSocketDisconnect:
        cancel.set()
