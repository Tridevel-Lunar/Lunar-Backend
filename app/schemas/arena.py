from typing import Any

from pydantic import BaseModel, Field


class MissionLimits(BaseModel):
    maxBlocks: int
    maxDepth: int
    maxSteps: int
    wallMs: int


class MissionPackResponse(BaseModel):
    id: str
    version: int = 1
    toolboxId: str
    title: str
    code: str
    level: str
    playable: bool
    allowedOps: list[str]
    limits: MissionLimits


class AttemptResponse(BaseModel):
    mission_id: str
    mission_version: int | None = None
    ast: dict[str, Any] | None = None


class SaveAttemptRequest(BaseModel):
    ast: dict[str, Any] = Field(description="Blockly workspace JSON AST")


class RunMissionRequest(BaseModel):
    ast: dict[str, Any] = Field(description="Program AST to execute")


class TickLogEntry(BaseModel):
    tick: int
    is_daylight: bool
    glitch_applied: bool
    battery: int
    temperature: int
    safe_mode: bool
    heater_on: bool
    payload_on: bool


class MissionRunResult(BaseModel):
    grade: str
    comms: str
    payload_data: str
    longevity_impact: str
    satellite_survived: bool
    sent_to_earth: bool


class MissionRunResponse(BaseModel):
    mission_id: str
    mission_version: int
    ticks: list[TickLogEntry]
    final_battery: int
    final_temperature: int
    result: MissionRunResult
