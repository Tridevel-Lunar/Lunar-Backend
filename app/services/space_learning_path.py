"""Persist and sanitize Space learning paths; stream LAIKA path-building chat."""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.space_learning_path import SpaceLearningPath
from app.schemas.space_learning_path import (
    LearningPathResponse,
    LearningPathWrite,
    PathChatMessage,
    PathEdge,
    PathProposal,
    PathStep,
    PathStreamRequest,
)
from app.services.laika_errors import laika_provider_error_message
from app.services.laika_stream import format_sse
from app.services.rag.chain import _LlmStreamMeta, _stream_llm_deltas
from app.services.rag.prompts import SPACE_PATH_OPENING, get_space_path_system_prompt
from app.services.rag.providers import get_llm
from app.services.space_catalog import iter_courses

_PATH_FENCE = re.compile(r"```path\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
_PATH_OPEN = re.compile(r"```path\b", re.IGNORECASE)


def catalog_course_ids() -> set[str]:
    return {item.id for item in iter_courses()}


def sanitize_steps(steps: list[PathStep] | list[dict]) -> list[PathStep]:
    allowed = catalog_course_ids()
    seen: set[str] = set()
    out: list[PathStep] = []
    for raw in steps:
        step = raw if isinstance(raw, PathStep) else PathStep.model_validate(raw)
        course_id = step.courseId.strip()
        if course_id not in allowed or course_id in seen:
            continue
        seen.add(course_id)
        note = step.note.strip() if step.note else None
        out.append(PathStep(courseId=course_id, note=note or None))
    return out


def _edges_form_cycle(course_ids: set[str], edges: list[PathEdge]) -> bool:
    indeg = {cid: 0 for cid in course_ids}
    adj: dict[str, list[str]] = {cid: [] for cid in course_ids}
    for edge in edges:
        adj[edge.from_].append(edge.to)
        indeg[edge.to] += 1
    queue = [cid for cid, degree in indeg.items() if degree == 0]
    seen = 0
    while queue:
        node = queue.pop()
        seen += 1
        for nxt in adj[node]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)
    return seen < len(course_ids)


def sanitize_edges(
    edges: list[PathEdge] | list[dict],
    course_ids: set[str],
) -> list[PathEdge]:
    seen: set[tuple[str, str]] = set()
    out: list[PathEdge] = []
    for raw in edges:
        edge = raw if isinstance(raw, PathEdge) else PathEdge.model_validate(raw)
        src = edge.from_.strip()
        dst = edge.to.strip()
        if src not in course_ids or dst not in course_ids or src == dst:
            continue
        key = (src, dst)
        if key in seen:
            continue
        candidate = [*out, PathEdge.model_validate({"from": src, "to": dst})]
        if _edges_form_cycle(course_ids, candidate):
            continue
        seen.add(key)
        out = candidate
    return out


def sanitize_proposal(payload: dict | PathProposal) -> PathProposal:
    data = payload if isinstance(payload, PathProposal) else PathProposal.model_validate(payload)
    tags = [t.strip() for t in data.intentTags if isinstance(t, str) and t.strip()]
    steps = sanitize_steps(data.steps)
    ids = {s.courseId for s in steps}
    return PathProposal(
        intentTags=tags[:12],
        steps=steps,
        edges=sanitize_edges(data.edges, ids),
        final=data.final,
    )


def proposal_event_payload(proposal: PathProposal) -> dict:
    return {
        "intentTags": proposal.intentTags,
        "steps": [s.model_dump() for s in proposal.steps],
        "edges": [e.model_dump(by_alias=True) for e in proposal.edges],
        "final": proposal.final,
    }


def parse_path_fence(text: str) -> PathProposal | None:
    matches = list(_PATH_FENCE.finditer(text))
    if not matches:
        return None
    try:
        raw = json.loads(matches[-1].group(1))
        if not isinstance(raw, dict):
            return None
        return sanitize_proposal(raw)
    except (json.JSONDecodeError, ValueError):
        return None


def visible_chat_text(full: str) -> str:
    stripped = _PATH_FENCE.sub("", full)
    open_at = None
    for match in _PATH_OPEN.finditer(stripped):
        open_at = match.start()
    if open_at is not None and "```" not in stripped[open_at + 3 :]:
        stripped = stripped[:open_at]
    return stripped.rstrip()


def empty_path_response() -> LearningPathResponse:
    return LearningPathResponse(status="none")


def _row_to_response(row: SpaceLearningPath | None) -> LearningPathResponse:
    if row is None:
        return empty_path_response()
    if row.generated_by == "skipped" or row.skipped_at is not None:
        return LearningPathResponse(
            status="skipped",
            generatedBy="skipped",
            skippedAt=row.skipped_at,
            updatedAt=row.updated_at,
        )
    steps = sanitize_steps(row.steps or [])
    ids = {s.courseId for s in steps}
    edges = sanitize_edges(row.edges or [], ids)
    transcript = [PathChatMessage.model_validate(m) for m in (row.chat_transcript or [])]
    if steps:
        return LearningPathResponse(
            status="active",
            intentText=row.intent_text,
            intentTags=list(row.intent_tags or []),
            steps=steps,
            edges=edges,
            chatTranscript=transcript,
            generatedBy="laika",
            updatedAt=row.updated_at,
        )
    if transcript:
        return LearningPathResponse(
            status="draft",
            intentText=row.intent_text,
            intentTags=list(row.intent_tags or []),
            chatTranscript=transcript,
            generatedBy="laika",
            updatedAt=row.updated_at,
        )
    return LearningPathResponse(status="none", updatedAt=row.updated_at)


def get_path(db: Session, user_id: UUID) -> LearningPathResponse:
    row = db.query(SpaceLearningPath).filter(SpaceLearningPath.user_id == user_id).one_or_none()
    return _row_to_response(row)


def _get_or_create_row(db: Session, user_id: UUID) -> SpaceLearningPath:
    row = db.query(SpaceLearningPath).filter(SpaceLearningPath.user_id == user_id).one_or_none()
    if row is None:
        row = SpaceLearningPath(
            user_id=user_id,
            generated_by="laika",
            intent_tags=[],
            steps=[],
            edges=[],
            chat_transcript=[],
        )
        db.add(row)
        db.flush()
    return row


def upsert_path(db: Session, user_id: UUID, payload: LearningPathWrite) -> LearningPathResponse:
    now = datetime.now(UTC)
    row = _get_or_create_row(db, user_id)
    row.updated_at = now
    if payload.status == "skipped":
        row.generated_by = "skipped"
        row.skipped_at = now
        row.intent_text = None
        row.intent_tags = []
        row.steps = []
        row.edges = []
        row.chat_transcript = [m.model_dump() for m in payload.chatTranscript]
        db.commit()
        db.refresh(row)
        return _row_to_response(row)

    if payload.status == "draft":
        row.generated_by = "laika"
        row.skipped_at = None
        row.chat_transcript = [m.model_dump() for m in payload.chatTranscript]
        db.commit()
        db.refresh(row)
        return _row_to_response(row)

    steps = sanitize_steps(payload.steps)
    if not steps:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Learning path must include at least one catalog course id",
        )
    ids = {s.courseId for s in steps}
    edges = sanitize_edges(payload.edges, ids)
    row.generated_by = "laika"
    row.skipped_at = None
    row.intent_text = payload.intentText
    row.intent_tags = payload.intentTags
    row.steps = [s.model_dump() for s in steps]
    row.edges = [e.model_dump(by_alias=True) for e in edges]
    row.chat_transcript = [m.model_dump() for m in payload.chatTranscript]
    db.commit()
    db.refresh(row)
    return _row_to_response(row)


def delete_path(db: Session, user_id: UUID) -> None:
    row = db.query(SpaceLearningPath).filter(SpaceLearningPath.user_id == user_id).one_or_none()
    if row is None:
        return
    db.delete(row)
    db.commit()


def _persist_chat_turn(
    db: Session,
    user_id: UUID,
    transcript: list[PathChatMessage],
    proposal: PathProposal | None,
) -> None:
    """Save chat after each LAIKA turn so the learner can resume the session."""
    if not transcript:
        return
    row = _get_or_create_row(db, user_id)
    row.generated_by = "laika"
    row.skipped_at = None
    row.chat_transcript = [m.model_dump() for m in transcript]
    row.updated_at = datetime.now(UTC)
    if proposal and proposal.final and proposal.steps:
        intent = next((m.content for m in reversed(transcript) if m.role == "user"), None)
        row.intent_text = intent
        row.intent_tags = proposal.intentTags
        row.steps = [s.model_dump() for s in proposal.steps]
        row.edges = [e.model_dump(by_alias=True) for e in proposal.edges]
    db.commit()


def iter_path_stream_sse(
    db: Session,
    settings: Settings,
    request: PathStreamRequest,
    user_id: UUID,
    cancel: threading.Event,
) -> Iterator[str]:
    if not settings.laika_llm_enabled:
        yield format_sse("error", {"detail": "LAIKA LLM is disabled — configure active LLM provider"})
        return

    history = [m for m in request.messages if m.content.strip()]
    content = request.content.strip()
    if content:
        history.append(PathChatMessage(role="user", content=content))
    if not history:
        yield format_sse("token", {"delta": SPACE_PATH_OPENING})
        yield format_sse("done", {"response": SPACE_PATH_OPENING})
        return

    messages: list = [SystemMessage(content=get_space_path_system_prompt())]
    if request.currentPlan and request.currentPlan.steps:
        plan = sanitize_proposal(request.currentPlan)
        if plan.steps:
            messages.append(
                SystemMessage(
                    content=(
                        "Current map already on the learner's screen. "
                        "Do NOT emit a ```path block unless they ask to change it, "
                        "add/remove courses, fix the map, or confirm final. "
                        "Casual chat and acknowledgments keep this map unchanged — Thai reply only.\n"
                        f"{plan.model_dump_json(by_alias=True)}"
                    )
                )
            )
    for item in history:
        if item.role == "user":
            messages.append(HumanMessage(content=item.content))
        else:
            messages.append(AIMessage(content=item.content))

    llm = get_llm(settings)
    meta = _LlmStreamMeta()
    visible_prev = ""
    last_proposal: PathProposal | None = None
    full_text = ""

    try:
        yield format_sse("status", {"phase": "generating", "message": "LAIKA กำลังคิดเส้นทาง…"})
        for delta, current in _stream_llm_deltas(llm, messages, cancel_event=cancel, meta=meta):
            if cancel.is_set():
                break
            _ = delta
            full_text = current
            visible = visible_chat_text(current)
            chunk = visible[len(visible_prev) :]
            if chunk:
                yield format_sse("token", {"delta": chunk})
                visible_prev = visible
            proposal = parse_path_fence(current)
            if proposal and proposal.steps and proposal != last_proposal:
                last_proposal = proposal
                event = "plan" if proposal.final else "plan_delta"
                yield format_sse(event, proposal_event_payload(proposal))
    except Exception as exc:
        yield format_sse("error", {"detail": laika_provider_error_message(exc)})
        return

    visible = visible_chat_text(full_text) if full_text else visible_prev
    proposal = parse_path_fence(full_text) if full_text else last_proposal
    if proposal and proposal.steps:
        last_proposal = proposal
        yield format_sse(
            "plan" if proposal.final else "plan_delta",
            proposal_event_payload(proposal),
        )

    if not cancel.is_set() and visible:
        transcript = list(history)
        transcript.append(PathChatMessage(role="assistant", content=visible))
        _persist_chat_turn(db, user_id, transcript, last_proposal)

    yield format_sse(
        "done",
        {
            "response": visible,
            "finish_reason": meta.finish_reason,
            "truncated": meta.finish_reason == "length",
        },
    )
