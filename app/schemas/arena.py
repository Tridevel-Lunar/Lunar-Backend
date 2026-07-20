from typing import Any, Literal

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


class RunError(BaseModel):
    blockId: str = ""
    code: str
    messageTh: str


class OrbitState(BaseModel):
    altitudeKm: float
    stability: float
    inLeo: bool


class FinalWorld(BaseModel):
    powerWh: float
    payloadOn: bool
    payload_safe: bool = True
    phase: str
    powerBusOn: bool = False
    inserted_to_leo: bool = False
    sensors: dict[str, bool] = Field(default_factory=dict)
    orbit: OrbitState
    faults: list[Any] = Field(default_factory=list)


class RunMetrics(BaseModel):
    peakPowerDraw: float
    ticks: int
    stabilityFinal: float
    insertedToLeo: bool


class RunFrame(BaseModel):
    t: int
    altitudeKm: float
    phase: str
    powerWh: float
    highlights: list[str] | None = None


class RunLogEntry(BaseModel):
    t: int
    level: Literal["info", "warn", "error"]
    messageTh: str
    blockId: str | None = None


class RunResult(BaseModel):
    status: Literal["passed", "failed", "error", "timeout"]
    passedChecks: list[str]
    failedChecks: list[str]
    error: RunError | None = None
    finalWorld: FinalWorld
    metrics: RunMetrics
    frames: list[RunFrame]
    log: list[RunLogEntry]


class AttemptResponse(BaseModel):
    mission_id: str
    ast: dict[str, Any] | None = None
    last_result: RunResult | None = None


class SaveAttemptRequest(BaseModel):
    ast: dict[str, Any] = Field(description="Blockly workspace JSON AST")


class RunRequest(BaseModel):
    ast: dict[str, Any] = Field(description="Blockly workspace JSON AST to simulate")


RunJobStatus = Literal["pending", "running", "finished", "failed"]


class RunJobResponse(BaseModel):
    job_id: str
    status: RunJobStatus
    mission_id: str


class RunJobStatusResponse(BaseModel):
    job_id: str
    status: RunJobStatus
    mission_id: str
    result: RunResult | None = None
    error: str | None = None
