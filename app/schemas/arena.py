from typing import Any

from pydantic import BaseModel, Field


class MissionLimits(BaseModel):
    maxBlocks: int
    maxDepth: int
    maxSteps: int
    wallMs: int


class EpsSetup(BaseModel):
    battery_threshold_low: int | None = None
    battery_threshold_high: int | None = None
    temp_min: int | None = None
    temp_max: int | None = None
    heater_power: int | None = None


class PayloadSetup(BaseModel):
    payload_module: str | None = None
    default_on: bool | None = None


class CommSetup(BaseModel):
    pass_sim_sec: int | None = None
    downlink_policy: str | None = None


class MissionSetupPresets(BaseModel):
    eps: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    comm: dict[str, Any] = Field(default_factory=dict)


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
    enabledLibs: list[str] = Field(default_factory=list)
    payloadModuleId: str | None = None
    commLibVisible: bool = False
    setupPresets: MissionSetupPresets | None = None
    orbitPeriodSec: int | None = None
    eclipseFraction: float | None = None


class AttemptResponse(BaseModel):
    mission_id: str
    mission_version: int | None = None
    ast: dict[str, Any] | None = None
    workspace: dict[str, Any] | None = None


class SaveAttemptRequest(BaseModel):
    ast: dict[str, Any] = Field(description="Program AST for run/grade")
    workspace: dict[str, Any] | None = Field(
        default=None,
        description="Blockly workspace serialization (layout/positions); optional for legacy clients",
    )


class RunMissionRequest(BaseModel):
    ast: dict[str, Any] = Field(description="Program AST to execute")
    epsSetup: EpsSetup | None = None
    payloadSetup: PayloadSetup | None = None
    commSetup: CommSetup | None = None


class OrbitTraceEntry(BaseModel):
    simSec: int
    phase: float
    isSunlit: bool
    battery: int
    temperature: int
    heaterOn: bool
    payloadOn: bool
    safeMode: bool


class OrbitSummary(BaseModel):
    eclipseEnterSec: int
    eclipseExitSec: int
    minBattery: int
    minBatteryDuringEclipse: int


class RunTiming(BaseModel):
    overrunCount: int = 0
    usedSecPerWindowSample: list[float] | None = None


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
    orbitPeriodSec: int
    simSecPerWindow: int = 1
    trace: list[OrbitTraceEntry]
    orbitSummary: OrbitSummary
    final_battery: int
    final_temperature: int
    timing: RunTiming | None = None
    result: MissionRunResult
