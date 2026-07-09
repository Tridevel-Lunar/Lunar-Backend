import asyncio
import contextlib
import threading

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.api.deps import get_current_user, get_ws_user
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.user import User
from app.models.user import User
from app.schemas.laika import (
    AssistRequest,
    AssistResponse,
    ContextUsageRequest,
    ContextUsageResponse,
    ContextUsageSegment,
    LaikaHealthResponse,
    StudioGreetingRequest,
    StudioGreetingResponse,
)
from app.services.laika import run_laika_assist
from app.services.laika_errors import laika_provider_error_message
from app.services.laika_stream import iter_laika_assist_sse
from app.services.laika_ws import pump_laika_assist, watch_for_stop
from app.services.rag.context_window import compute_context_usage
from app.services.rag.learner import resolve_learner_display_name
from app.services.rag.tokens import resolve_context_window
from app.services.studio_greeting import run_studio_greeting

router = APIRouter(prefix="/laika", tags=["laika"])


def _assist_request_for_user(payload: AssistRequest, user: User) -> AssistRequest:
    data = payload.model_dump()
    data["learner_display_name"] = resolve_learner_display_name(
        user.display_name,
        user.email,
    )
    return AssistRequest.model_validate(data)


def _llm_model_name(settings: Settings) -> str:
    if settings.laika_llm_provider == "gemini":
        return settings.gemini_model
    if settings.laika_llm_provider == "groq":
        return settings.groq_model
    return settings.ollama_llm_model


def _embedding_model_name(settings: Settings) -> str:
    if settings.laika_embedding_provider == "gemini":
        return settings.gemini_embedding_model
    return settings.ollama_embed_model


@router.get(
    "/health",
    response_model=LaikaHealthResponse,
    summary="LAIKA provider health",
)
def laika_health(settings: Settings = Depends(get_settings)) -> LaikaHealthResponse:
    enabled = settings.laika_enabled
    return LaikaHealthResponse(
        status="ok" if enabled else "disabled",
        llm_provider=settings.laika_llm_provider,
        embedding_provider=settings.laika_embedding_provider,
        llm_model=_llm_model_name(settings),
        embedding_model=_embedding_model_name(settings),
        enabled=enabled,
        context_window=resolve_context_window(settings),
        max_history_tokens=settings.laika_max_history_tokens,
        reserved_output_tokens=settings.laika_reserved_output_tokens,
    )


@router.post(
    "/context/usage",
    response_model=ContextUsageResponse,
    summary="Estimate LAIKA context window usage",
)
def laika_context_usage(
    payload: ContextUsageRequest,
    _user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ContextUsageResponse:
    usage = compute_context_usage(
        settings,
        intent=payload.intent,
        entry_content=payload.entry_content,
        current_content=payload.current_content,
        draft=payload.draft,
        messages=payload.messages,
        learning_context=(
            payload.learning_context.model_dump() if payload.learning_context else None
        ),
    )
    return ContextUsageResponse(
        context_window=usage.context_window,
        reserved_output=usage.reserved_output,
        input_budget=usage.input_budget,
        used_input=usage.used_input,
        remaining_input=usage.remaining_input,
        usage_ratio=usage.usage_ratio,
        segments=[
            ContextUsageSegment(key=s.key, label=s.label, tokens=s.tokens)
            for s in usage.segments
        ],
        history_message_count=usage.history_message_count,
        history_trimmed_count=usage.history_trimmed_count,
        history_kept_count=usage.history_kept_count,
    )


@router.post(
    "/studio/greeting",
    response_model=StudioGreetingResponse,
    summary="LAIKA Studio landing greeting",
    responses={
        503: {"description": "LAIKA disabled or provider misconfigured"},
        504: {"description": "LLM timeout"},
    },
)
def laika_studio_greeting(
    payload: StudioGreetingRequest,
    _user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> StudioGreetingResponse:
    if not settings.laika_llm_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LAIKA LLM is disabled — configure active LLM provider",
        )
    try:
        return run_studio_greeting(settings, payload.learning_context)
    except TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="LAIKA request timed out",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=laika_provider_error_message(exc),
        ) from exc


@router.post(
    "/assist",
    response_model=AssistResponse,
    summary="LAIKA mentor assist",
    responses={
        503: {"description": "LAIKA disabled or provider misconfigured"},
        504: {"description": "LLM timeout"},
    },
)
def laika_assist(
    payload: AssistRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AssistResponse:
    if not settings.laika_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LAIKA is disabled — configure active LLM and embedding providers",
        )
    request = _assist_request_for_user(payload, user)
    try:
        return run_laika_assist(db, settings, request)
    except TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="LAIKA request timed out",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=laika_provider_error_message(exc),
        ) from exc


@router.post(
    "/assist/stream",
    summary="LAIKA mentor assist (SSE stream)",
    responses={
        503: {"description": "LAIKA disabled or provider misconfigured"},
    },
)
def laika_assist_stream(
    payload: AssistRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    if not settings.laika_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LAIKA is disabled — configure active LLM and embedding providers",
        )

    request = _assist_request_for_user(payload, user)
    cancel = threading.Event()

    return StreamingResponse(
        iter_laika_assist_sse(db, settings, request, cancel),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.websocket("/assist/ws")
async def laika_assist_ws(
    websocket: WebSocket,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> None:
    try:
        user = get_ws_user(websocket, db)
    except HTTPException:
        await websocket.close(code=4401)
        return

    await websocket.accept()

    try:
        incoming = await websocket.receive_json()
    except WebSocketDisconnect:
        return

    if incoming.get("type") != "assist":
        await websocket.send_json({"type": "error", "detail": "Expected assist message"})
        await websocket.close()
        return

    try:
        payload = AssistRequest.model_validate(incoming.get("payload"))
        request = _assist_request_for_user(payload, user)
    except ValidationError as exc:
        await websocket.send_json({"type": "error", "detail": str(exc)})
        await websocket.close()
        return

    if not settings.laika_enabled:
        await websocket.send_json(
            {
                "type": "error",
                "detail": "LAIKA is disabled — configure active LLM and embedding providers",
            }
        )
        await websocket.close()
        return

    cancel = threading.Event()
    watch_task = asyncio.create_task(watch_for_stop(websocket, cancel))

    try:
        await pump_laika_assist(websocket, db, settings, request, cancel)
    except WebSocketDisconnect:
        cancel.set()
    finally:
        cancel.set()
        watch_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await watch_task
        with contextlib.suppress(Exception):
            await websocket.close(code=1000, reason="assist_complete")
