from typing import Any

from pydantic import BaseModel, Field


class MissionLimits(BaseModel):
    maxBlocks: int
    maxDepth: int
    maxSteps: int
    wallMs: int


class MissionPackResponse(BaseModel):
    id: str
    toolboxId: str
    title: str
    code: str
    level: str
    playable: bool
    allowedOps: list[str]
    limits: MissionLimits


class AttemptResponse(BaseModel):
    mission_id: str
    ast: dict[str, Any] | None = None


class SaveAttemptRequest(BaseModel):
    ast: dict[str, Any] = Field(description="Blockly workspace JSON AST")
