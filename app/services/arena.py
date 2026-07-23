"""Arena attempt persistence + per-second LEO orbit mission runner."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.arena.missions import get_mission_pack
from app.models.arena_attempt import ArenaAttempt
from app.schemas.arena import (
    AttemptResponse,
    MissionPackResponse,
    MissionRunResponse,
    MissionRunResult,
    MissionSetupPresets,
    OrbitSummary,
    OrbitTraceEntry,
    RunMissionRequest,
    RunTiming,
    SaveAttemptRequest,
)

# Abstract RTOS cost per op (seconds of CPU budget within one sim window)
BLOCK_TIME_SEC: dict[str, float] = {
    "battery_level": 0.002,
    "temperature": 0.002,
    "is_in_sunlight": 0.002,
    "is_in_eclipse": 0.002,
    "is_daylight": 0.002,
    "sim_sec": 0.002,
    "tick_number": 0.002,
    "orbit_phase": 0.002,
    "compare": 0.002,
    "if": 0.003,
    "when": 0.004,
    "turn_heater": 0.005,
    "turn_payload": 0.005,
    "enter_safe_mode": 0.008,
    "exit_safe_mode": 0.008,
    "wait_1_tick": 0.001,
    "repeat_until_end": 0.001,
}


def _pack_version(pack: dict[str, Any]) -> int:
    return int(pack.get("version", 1))


def clear_attempts(db: Session | None = None) -> None:
    """Reset arena attempts (pytest)."""
    if db is None:
        return
    for row in db.scalars(select(ArenaAttempt)).all():
        db.delete(row)
    db.commit()


def _get_attempt_row(db: Session, user_id: UUID, mission_id: str) -> ArenaAttempt | None:
    return db.scalar(
        select(ArenaAttempt).where(
            ArenaAttempt.user_id == user_id,
            ArenaAttempt.mission_id == mission_id,
        )
    )


def get_mission(mission_id: str) -> MissionPackResponse | None:
    pack = get_mission_pack(mission_id)
    if not pack:
        return None
    world = pack.get("world", {})
    presets = pack.get("setupPresets")
    return MissionPackResponse(
        id=pack["id"],
        version=_pack_version(pack),
        toolboxId=pack["toolboxId"],
        title=pack["title"],
        code=pack["code"],
        level=pack["level"],
        playable=pack["playable"],
        allowedOps=list(pack["allowedOps"]),
        limits=pack["limits"],
        enabledLibs=list(pack.get("enabledLibs", [])),
        payloadModuleId=pack.get("payloadModuleId"),
        commLibVisible=bool(pack.get("commLibVisible", False)),
        setupPresets=MissionSetupPresets(**presets) if isinstance(presets, dict) else None,
        orbitPeriodSec=int(world["orbitPeriodSec"]) if "orbitPeriodSec" in world else None,
        eclipseFraction=float(world["eclipseFraction"]) if "eclipseFraction" in world else None,
    )


def get_attempt(db: Session, user_id: UUID, mission_id: str) -> AttemptResponse | None:
    pack = get_mission_pack(mission_id)
    if pack is None:
        return None
    mission_version = _pack_version(pack)
    row = _get_attempt_row(db, user_id, mission_id)
    if row is None:
        return AttemptResponse(
            mission_id=mission_id,
            mission_version=mission_version,
            ast=None,
            workspace=None,
        )

    if int(row.mission_version) != mission_version:
        db.delete(row)
        db.commit()
        return AttemptResponse(
            mission_id=mission_id,
            mission_version=mission_version,
            ast=None,
            workspace=None,
        )

    return AttemptResponse(
        mission_id=mission_id,
        mission_version=mission_version,
        ast=row.ast,
        workspace=row.workspace,
    )


def save_attempt(
    db: Session,
    user_id: UUID,
    mission_id: str,
    payload: SaveAttemptRequest,
) -> AttemptResponse | None:
    pack = get_mission_pack(mission_id)
    if pack is None:
        return None
    mission_version = _pack_version(pack)
    now = datetime.now(UTC)
    row = _get_attempt_row(db, user_id, mission_id)
    if row is None:
        row = ArenaAttempt(
            user_id=user_id,
            mission_id=mission_id,
            ast=payload.ast,
            workspace=payload.workspace,
            mission_version=mission_version,
            last_result=None,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        row.ast = payload.ast
        row.workspace = payload.workspace
        row.mission_version = mission_version
        row.updated_at = now

    db.commit()
    db.refresh(row)
    return AttemptResponse(
        mission_id=mission_id,
        mission_version=mission_version,
        ast=row.ast,
        workspace=row.workspace,
    )


def _iter_nodes(program_ast: dict[str, Any]) -> list[tuple[dict[str, Any], int]]:
    out: list[tuple[dict[str, Any], int]] = []
    stack: list[tuple[dict[str, Any], int]] = []
    for node in reversed(program_ast.get("body", [])):
        if isinstance(node, dict):
            stack.append((node, 1))
    while stack:
        node, depth = stack.pop()
        out.append((node, depth))
        for key in ("body", "then", "else"):
            children = node.get(key, [])
            if isinstance(children, list):
                for child in reversed(children):
                    if isinstance(child, dict):
                        stack.append((child, depth + 1))
        cond = node.get("cond")
        if isinstance(cond, dict):
            stack.append((cond, depth + 1))
    return out


def _find_body(program_ast: dict[str, Any], op: str) -> list[dict[str, Any]]:
    for node in program_ast.get("body", []):
        if isinstance(node, dict) and node.get("op") == op and isinstance(node.get("body"), list):
            return [x for x in node["body"] if isinstance(x, dict)]
    return []


_CONTAINER_OPS = frozenset({"setup", "main_loop"})
_MAIN_LOOP_CONTROL_OPS = frozenset(
    {"turn_heater", "turn_payload", "enter_safe_mode", "exit_safe_mode", "if", "when", "repeat_until_end"}
)
_EFFECTFUL_OPS = frozenset({"turn_heater", "turn_payload", "enter_safe_mode", "exit_safe_mode"})


def _main_loop_has_control_block(main_body: list[dict[str, Any]]) -> bool:
    stack = list(main_body)
    while stack:
        node = stack.pop()
        op = node.get("op")
        if op in _MAIN_LOOP_CONTROL_OPS:
            return True
        for key in ("body", "then", "else"):
            children = node.get(key, [])
            if isinstance(children, list):
                stack.extend(child for child in children if isinstance(child, dict))
        cond = node.get("cond")
        if isinstance(cond, dict):
            stack.append(cond)
    return False


def _validate_ast(program_ast: dict[str, Any], pack: dict[str, Any]) -> None:
    if program_ast.get("type") != "program" or not isinstance(program_ast.get("body"), list):
        raise ValueError("Invalid AST program root")
    body = program_ast.get("body", [])
    has_setup = any(isinstance(node, dict) and node.get("op") == "setup" for node in body)
    has_main_loop = any(isinstance(node, dict) and node.get("op") == "main_loop" for node in body)
    if not has_setup or not has_main_loop:
        raise ValueError("Program must include setup and main_loop blocks")
    for node in body:
        if isinstance(node, dict):
            op = str(node.get("op", ""))
            if op and op not in _CONTAINER_OPS:
                raise ValueError("All blocks must be inside setup or main_loop")
    main_body = _find_body(program_ast, "main_loop")
    if not _main_loop_has_control_block(main_body):
        raise ValueError("main_loop must include at least one control block")
    nodes = _iter_nodes(program_ast)
    limits = pack["limits"]
    if len(nodes) > int(limits["maxBlocks"]):
        raise ValueError("AST exceeds maxBlocks")
    max_depth = max((depth for _, depth in nodes), default=0)
    if max_depth > int(limits["maxDepth"]):
        raise ValueError("AST exceeds maxDepth")
    allowed = set(pack["allowedOps"])
    for node, _ in nodes:
        op = str(node.get("op", ""))
        if op and op not in allowed:
            raise ValueError(f"Operation not allowed: {op}")


def _orbit_phase(sim_sec: int, period: int) -> float:
    if period <= 0:
        return 0.0
    return (sim_sec % period) / period


def _is_sunlit(phase: float, eclipse_fraction: float) -> bool:
    sunlit_fraction = 1.0 - eclipse_fraction
    sunlit_half = sunlit_fraction / 2.0
    if phase < sunlit_half or phase >= sunlit_half + eclipse_fraction:
        return True
    return False


def _eclipse_bounds(period: int, eclipse_fraction: float) -> tuple[int, int]:
    sunlit_half = (1.0 - eclipse_fraction) / 2.0
    enter = int(round(sunlit_half * period))
    exit_sec = int(round((sunlit_half + eclipse_fraction) * period))
    return enter, exit_sec


def _merge_setup(pack: dict[str, Any], payload: RunMissionRequest) -> dict[str, Any]:
    presets = pack.get("setupPresets", {})
    eps_p = dict(presets.get("eps", {}))
    payload_p = dict(presets.get("payload", {}))
    comm_p = dict(presets.get("comm", {}))

    eps = payload.epsSetup
    if eps is not None:
        if eps.battery_threshold_low is not None:
            eps_p["battery_threshold_low"] = eps.battery_threshold_low
        if eps.battery_threshold_high is not None:
            eps_p["battery_threshold_high"] = eps.battery_threshold_high
        if eps.temp_min is not None:
            eps_p["temp_min"] = eps.temp_min
        if eps.temp_max is not None:
            eps_p["temp_max"] = eps.temp_max
        if eps.heater_power is not None:
            eps_p["heater_power"] = eps.heater_power

    pl = payload.payloadSetup
    if pl is not None:
        if pl.payload_module is not None:
            payload_p["payload_module"] = pl.payload_module
        if pl.default_on is not None:
            payload_p["default_on"] = pl.default_on

    cm = payload.commSetup
    if cm is not None:
        if cm.pass_sim_sec is not None:
            comm_p["pass_sim_sec"] = cm.pass_sim_sec
        if cm.downlink_policy is not None:
            comm_p["downlink_policy"] = cm.downlink_policy

    world = pack["world"]
    return {
        "batteryThresholdLow": int(eps_p.get("battery_threshold_low", 20)),
        "batteryThresholdHigh": int(eps_p.get("battery_threshold_high", 80)),
        "tempMin": int(eps_p.get("temp_min", world.get("tempMin", 15))),
        "tempMax": int(eps_p.get("temp_max", world.get("tempMax", 55))),
        "heaterPower": int(eps_p.get("heater_power", 30)),
        "payloadMode": "on" if bool(payload_p.get("default_on", False)) else "off",
        "payloadModule": str(payload_p.get("payload_module", "generic")),
        "passSimSec": int(comm_p.get("pass_sim_sec", world.get("passSimSec", 5400))),
        "downlinkPolicy": str(comm_p.get("downlink_policy", "auto")),
    }


def _event_matches(event_name: str, state: dict[str, Any], setup: dict[str, Any]) -> bool:
    if event_name == "battery_low":
        return state["battery"] < setup["batteryThresholdLow"]
    if event_name == "battery_high":
        return state["battery"] > setup["batteryThresholdHigh"]
    if event_name == "too_cold":
        return state["temperature"] < setup["tempMin"]
    if event_name == "too_hot":
        return state["temperature"] > setup["tempMax"]
    if event_name == "eclipse_enter":
        return (not state["is_sunlit"]) and state["prev_is_sunlit"]
    if event_name == "eclipse_exit":
        return state["is_sunlit"] and (not state["prev_is_sunlit"])
    if event_name == "comm_pass":
        return int(state["sim_sec"]) == int(setup["passSimSec"])
    return False


def _eval_expr(expr: dict[str, Any] | None, state: dict[str, Any], setup: dict[str, Any]) -> Any:
    if not isinstance(expr, dict):
        return None
    op = expr.get("op")
    if op == "battery_level":
        return int(round(state["battery"]))
    if op == "temperature":
        return int(round(state["temperature"]))
    if op in ("is_in_sunlight", "is_daylight"):
        return 1 if state["is_sunlit"] else 0
    if op == "is_in_eclipse":
        return 0 if state["is_sunlit"] else 1
    if op in ("sim_sec", "tick_number"):
        return state["sim_sec"]
    if op == "orbit_phase":
        return state["phase"]
    if op == "compare":
        args = expr.get("args", {})
        if isinstance(args, dict) and "left" in args:
            left = _eval_expr(args.get("left"), state, setup)
            cmp = str(args.get("cmp", "lt"))
            right = args.get("right")
        else:
            left = _eval_expr(expr.get("left"), state, setup)
            cmp = str(expr.get("cmp", "lt"))
            right = expr.get("right")
        try:
            left_n = float(left)
            right_n = float(right)
        except (TypeError, ValueError):
            return False
        if cmp == "lt":
            return left_n < right_n
        if cmp == "lte":
            return left_n <= right_n
        if cmp == "gt":
            return left_n > right_n
        if cmp == "gte":
            return left_n >= right_n
        if cmp == "eq":
            return left_n == right_n
        return False
    return None


@dataclass
class _WindowControl:
    stop_window: bool = False
    budget_overrun: bool = False


def _charge_budget(control: _WindowControl, used: list[float], budget: float, op: str) -> bool:
    cost = float(BLOCK_TIME_SEC.get(op, 0.002))
    if used[0] + cost > budget:
        control.budget_overrun = True
        control.stop_window = True
        return False
    used[0] += cost
    return True


def _run_statements(
    statements: list[dict[str, Any]],
    state: dict[str, Any],
    setup: dict[str, Any],
    commands: dict[str, Any],
    control: _WindowControl,
    steps: list[int],
    max_steps: int,
    event_hits: set[str],
    used_sec: list[float],
    window_budget: float,
    effectful_ops: list[int] | None = None,
) -> None:
    if control.stop_window:
        return
    for node in statements:
        if control.stop_window:
            return
        steps[0] += 1
        if steps[0] > max_steps:
            raise ValueError("Execution exceeded maxSteps")
        op = str(node.get("op", ""))
        if op and not _charge_budget(control, used_sec, window_budget, op):
            return
        if op == "turn_heater":
            commands["heater_on"] = bool(node.get("args", {}).get("on", False))
            if effectful_ops is not None:
                effectful_ops[0] += 1
        elif op == "turn_payload":
            commands["payload_on"] = bool(node.get("args", {}).get("on", False))
            if effectful_ops is not None:
                effectful_ops[0] += 1
        elif op == "enter_safe_mode":
            commands["enter_safe_mode"] = True
            if effectful_ops is not None:
                effectful_ops[0] += 1
        elif op == "exit_safe_mode":
            commands["exit_safe_mode_next"] = True
            if effectful_ops is not None:
                effectful_ops[0] += 1
        elif op == "wait_1_tick":
            control.stop_window = True
        elif op == "if":
            cond_value = _eval_expr(node.get("cond"), state, setup)
            # charge for nested compare ops already counted via cond walk? cond eval is free of budget —
            # blocks inside cond are not executed as statements. Acceptable for M01.
            branch = node.get("then") if bool(cond_value) else node.get("else")
            if isinstance(branch, list):
                _run_statements(
                    branch,
                    state,
                    setup,
                    commands,
                    control,
                    steps,
                    max_steps,
                    event_hits,
                    used_sec,
                    window_budget,
                    effectful_ops,
                )
        elif op == "when":
            args = node.get("args", {})
            event_name = str(args.get("event", ""))
            if event_name and event_name not in event_hits and _event_matches(event_name, state, setup):
                event_hits.add(event_name)
                body = node.get("body", [])
                if isinstance(body, list):
                    _run_statements(
                        body,
                        state,
                        setup,
                        commands,
                        control,
                        steps,
                        max_steps,
                        event_hits,
                        used_sec,
                        window_budget,
                        effectful_ops,
                    )
        elif op == "repeat_until_end":
            body = node.get("body", [])
            if isinstance(body, list):
                _run_statements(
                    body,
                    state,
                    setup,
                    commands,
                    control,
                    steps,
                    max_steps,
                    event_hits,
                    used_sec,
                    window_budget,
                    effectful_ops,
                )
            control.stop_window = True


def _apply_physics(
    state: dict[str, Any],
    setup: dict[str, Any],
    world: dict[str, Any],
    *,
    heater_on: bool,
    payload_on: bool,
) -> None:
    heater_frac = max(0.0, min(1.0, float(setup["heaterPower"]) / 100.0))
    base = float(world["baseLoadPerSec"])
    solar = float(world["solarChargePerSec"]) if state["is_sunlit"] else 0.0
    heater_drain = float(world["heaterDrainPerSecAtFull"]) * heater_frac if heater_on else 0.0
    payload_drain = float(world["payloadDrainPerSec"]) if payload_on else 0.0
    safe_bonus = float(world["safeModeBatteryBonusPerSec"]) if state["safe_mode"] else 0.0
    state["battery"] += solar - base - heater_drain - payload_drain + safe_bonus
    state["battery"] = max(0.0, min(100.0, float(state["battery"])))

    if state["is_sunlit"]:
        temp_delta = float(world["tempSunDeltaPerSec"])
    else:
        temp_delta = float(world["tempEclipseDeltaPerSec"])
    heater_heat = float(world["heaterHeatPerSecAtFull"]) * heater_frac if heater_on else 0.0
    payload_heat = float(world["payloadHeatPerSec"]) if payload_on else 0.0
    cool = float(world["radiativeCoolPerSec"])
    state["temperature"] += temp_delta + heater_heat + payload_heat - cool


def _grade_result(
    state: dict[str, Any],
    setup: dict[str, Any],
    world: dict[str, Any],
    grading: dict[str, Any],
    *,
    effectful_main_ops: int,
    min_battery_during_eclipse: float,
    failed_hard_limit_midflight: bool,
) -> tuple[str, dict[str, Any]]:
    battery = int(round(state["battery"]))
    temp = int(round(state["temperature"]))
    temp_min = setup["tempMin"]
    temp_max = setup["tempMax"]
    mid_low = temp_min + int(world["midBandOffset"])
    mid_high = temp_max - int(world["midBandOffset"])
    eclipse_fail_floor = grading.get("failIfEclipseBatteryBelow")
    if effectful_main_ops <= 0:
        grade = "fail"
    elif failed_hard_limit_midflight:
        grade = "fail"
    elif battery < int(world["riskyBatteryMin"]) or temp < temp_min or temp > temp_max:
        grade = "fail"
    elif eclipse_fail_floor is not None and min_battery_during_eclipse < float(eclipse_fail_floor):
        grade = "fail"
    elif battery >= int(world["perfectBatteryMin"]) and mid_low <= temp <= mid_high:
        grade = "perfect"
    else:
        grade = "risky"

    payload_data = "none"
    comms = "missed"
    longevity = "major"
    if grade == "perfect":
        comms = "full"
        longevity = "none"
        payload_data = "full" if state.get("payload_on") else "partial"
    elif grade == "risky":
        comms = "partial"
        longevity = "minor"
        payload_data = "partial" if state.get("payload_on") else "none"

    return grade, {
        "comms": comms,
        "payload_data": payload_data,
        "longevity_impact": longevity,
        "satellite_survived": grade != "fail",
        "sent_to_earth": grade != "fail",
    }


def run_mission(user_id: UUID, mission_id: str, payload: RunMissionRequest) -> MissionRunResponse | None:
    _ = user_id
    pack = get_mission_pack(mission_id)
    if pack is None:
        return None
    program_ast = payload.ast
    _validate_ast(program_ast, pack)
    world = pack["world"]
    grading = pack.get("grading", {"mode": "outcome_first"})
    setup = _merge_setup(pack, payload)

    # Setup AST body is allowed but typically empty (thresholds come from tabs).
    setup_body = _find_body(program_ast, "setup")
    main_body = _find_body(program_ast, "main_loop")
    # Unwrap a single top-level repeat_until_end so the outer container matches Blockly compile.
    if len(main_body) == 1 and main_body[0].get("op") == "repeat_until_end":
        inner = main_body[0].get("body", [])
        if isinstance(inner, list):
            main_body = [x for x in inner if isinstance(x, dict)]

    period = int(world["orbitPeriodSec"])
    eclipse_fraction = float(world["eclipseFraction"])
    window_budget = float(world.get("windowBudgetSec", 0.05))
    sample_sec = max(1, int(world.get("traceSampleSec", 30)))
    eclipse_enter, eclipse_exit = _eclipse_bounds(period, eclipse_fraction)

    start = time.monotonic()
    state: dict[str, Any] = {
        "battery": float(world["startBattery"]),
        "temperature": float(world["startTemperature"]),
        "safe_mode": False,
        "sim_sec": 0,
        "phase": 0.0,
        "is_sunlit": True,
        "prev_is_sunlit": True,
        "heater_on": False,
        "payload_on": setup.get("payloadMode") != "off",
    }
    commands = {
        "heater_on": False,
        "payload_on": setup.get("payloadMode") != "off",
        "enter_safe_mode": False,
        "exit_safe_mode_next": False,
    }

    # Run setup statements once at simSec 0 (no physics).
    if setup_body:
        _run_statements(
            setup_body,
            state,
            setup,
            commands,
            _WindowControl(),
            [0],
            int(pack["limits"]["maxSteps"]),
            set(),
            [0.0],
            window_budget,
        )

    max_steps = int(pack["limits"]["maxSteps"])
    wall_ms = int(pack["limits"]["wallMs"])
    steps = [0]
    effectful_main_ops = [0]
    overrun_count = 0
    used_samples: list[float] = []
    trace: list[OrbitTraceEntry] = []
    min_battery = float(state["battery"])
    min_battery_eclipse = 100.0
    failed_hard = False
    hard_bat = int(world["riskyBatteryMin"])
    hard_tmin = setup["tempMin"]
    hard_tmax = setup["tempMax"]

    for sim_sec in range(period):
        if (time.monotonic() - start) * 1000 > wall_ms:
            raise ValueError("Execution exceeded wallMs")

        phase = _orbit_phase(sim_sec, period)
        is_sunlit = _is_sunlit(phase, eclipse_fraction)
        state["sim_sec"] = sim_sec
        state["phase"] = phase
        state["prev_is_sunlit"] = state["is_sunlit"] if sim_sec > 0 else is_sunlit
        # On first second, prev equals current so edge events do not fire spuriously.
        if sim_sec == 0:
            state["prev_is_sunlit"] = is_sunlit
        state["is_sunlit"] = is_sunlit

        if commands["exit_safe_mode_next"]:
            state["safe_mode"] = False
            commands["exit_safe_mode_next"] = False

        control = _WindowControl()
        event_hits: set[str] = set()
        used_sec = [0.0]
        _run_statements(
            main_body,
            state,
            setup,
            commands,
            control,
            steps,
            max_steps,
            event_hits,
            used_sec,
            window_budget,
            effectful_main_ops,
        )
        if control.budget_overrun:
            overrun_count += 1
        if sim_sec % sample_sec == 0 or sim_sec == period - 1:
            used_samples.append(round(used_sec[0], 4))

        if commands["enter_safe_mode"]:
            state["safe_mode"] = True
            commands["enter_safe_mode"] = False
        if state["safe_mode"]:
            effective_heater_on = False
            effective_payload_on = False
        else:
            effective_heater_on = bool(commands["heater_on"])
            effective_payload_on = bool(commands["payload_on"])

        state["heater_on"] = effective_heater_on
        state["payload_on"] = effective_payload_on

        _apply_physics(
            state,
            setup,
            world,
            heater_on=effective_heater_on,
            payload_on=effective_payload_on,
        )

        bat = float(state["battery"])
        temp = float(state["temperature"])
        min_battery = min(min_battery, bat)
        if not is_sunlit:
            min_battery_eclipse = min(min_battery_eclipse, bat)
        if bat < hard_bat or temp < hard_tmin or temp > hard_tmax:
            failed_hard = True

        if sim_sec % sample_sec == 0 or sim_sec == period - 1:
            trace.append(
                OrbitTraceEntry(
                    simSec=sim_sec,
                    phase=round(phase, 6),
                    isSunlit=is_sunlit,
                    battery=int(round(bat)),
                    temperature=int(round(temp)),
                    heaterOn=effective_heater_on,
                    payloadOn=effective_payload_on,
                    safeMode=bool(state["safe_mode"]),
                )
            )

    if min_battery_eclipse > 99.0:
        # Never entered eclipse (should not happen); treat as start battery.
        min_battery_eclipse = float(world["startBattery"])

    grade, result_state = _grade_result(
        state,
        setup,
        world,
        grading,
        effectful_main_ops=effectful_main_ops[0],
        min_battery_during_eclipse=min_battery_eclipse,
        failed_hard_limit_midflight=failed_hard,
    )
    return MissionRunResponse(
        mission_id=mission_id,
        mission_version=_pack_version(pack),
        orbitPeriodSec=period,
        simSecPerWindow=int(world.get("secPerWindow", 1)),
        trace=trace,
        orbitSummary=OrbitSummary(
            eclipseEnterSec=eclipse_enter,
            eclipseExitSec=eclipse_exit,
            minBattery=int(round(min_battery)),
            minBatteryDuringEclipse=int(round(min_battery_eclipse)),
        ),
        final_battery=int(round(state["battery"])),
        final_temperature=int(round(state["temperature"])),
        timing=RunTiming(overrunCount=overrun_count, usedSecPerWindowSample=used_samples[:20]),
        result=MissionRunResult(grade=grade, **result_state),
    )
