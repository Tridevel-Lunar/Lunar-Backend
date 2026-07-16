"""In-memory Arena attempt store (no DB this stage)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.arena.missions import get_mission_pack
from app.schemas.arena import AttemptResponse, MissionPackResponse, SaveAttemptRequest

# (user_id, mission_id) → AST dict
_ATTEMPTS: dict[tuple[UUID, str], dict[str, Any]] = {}


def clear_attempts() -> None:
    """Reset in-memory store (pytest)."""
    _ATTEMPTS.clear()


def get_mission(mission_id: str) -> MissionPackResponse | None:
    pack = get_mission_pack(mission_id)
    if not pack:
        return None
    return MissionPackResponse(
        id=pack["id"],
        toolboxId=pack["toolboxId"],
        title=pack["title"],
        code=pack["code"],
        level=pack["level"],
        playable=pack["playable"],
        allowedOps=list(pack["allowedOps"]),
        limits=pack["limits"],
    )


def get_attempt(user_id: UUID, mission_id: str) -> AttemptResponse | None:
    if get_mission_pack(mission_id) is None:
        return None
    ast = _ATTEMPTS.get((user_id, mission_id))
    return AttemptResponse(mission_id=mission_id, ast=ast)


def save_attempt(
    user_id: UUID,
    mission_id: str,
    payload: SaveAttemptRequest,
) -> AttemptResponse | None:
    if get_mission_pack(mission_id) is None:
        return None
    _ATTEMPTS[(user_id, mission_id)] = payload.ast
    return AttemptResponse(mission_id=mission_id, ast=payload.ast)
