"""Arena attempt persistence + deterministic Mission 01 runner."""

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
    RunMissionRequest,
    SaveAttemptRequest,
    TickLogEntry,
)


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


def _event_matches(event_name: str, state: dict[str, Any], setup: dict[str, Any]) -> bool:
    if event_name == "battery_low":
        return state["battery"] < setup["batteryThresholdLow"]
    if event_name == "battery_high":
        return state["battery"] > setup["batteryThresholdHigh"]
    if event_name == "too_cold":
        return state["temperature"] < setup["tempMin"]
    if event_name == "too_hot":
        return state["temperature"] > setup["tempMax"]
    if event_name == "glitch_tick":
        return state["tick"] == state["glitch_tick"]
    return False


def _eval_expr(expr: dict[str, Any] | None, state: dict[str, Any], setup: dict[str, Any]) -> Any:
    if not isinstance(expr, dict):
        return None
    op = expr.get("op")
    if op == "battery_level":
        return state["battery"]
    if op == "temperature":
        return state["temperature"]
    if op == "is_daylight":
        return state["is_daylight"]
    if op == "tick_number":
        return state["tick"]
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
class _TickControl:
    stop_tick: bool = False


def _run_statements(
    statements: list[dict[str, Any]],
    state: dict[str, Any],
    setup: dict[str, Any],
    commands: dict[str, Any],
    control: _TickControl,
    steps: list[int],
    max_steps: int,
    event_hits: set[str],
    effectful_ops: list[int] | None = None,
) -> None:
    if control.stop_tick:
        return
    for node in statements:
        if control.stop_tick:
            return
        steps[0] += 1
        if steps[0] > max_steps:
            raise ValueError("Execution exceeded maxSteps")
        op = node.get("op")
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
            commands["exit_safe_mode_next_tick"] = True
            if effectful_ops is not None:
                effectful_ops[0] += 1
        elif op == "wait_1_tick":
            control.stop_tick = True
        elif op == "if":
            cond_value = _eval_expr(node.get("cond"), state, setup)
            branch = node.get("then") if bool(cond_value) else node.get("else")
            if isinstance(branch, list):
                _run_statements(
                    branch, state, setup, commands, control, steps, max_steps, event_hits, effectful_ops
                )
        elif op == "when":
            args = node.get("args", {})
            event_name = str(args.get("event", ""))
            if event_name and event_name not in event_hits and _event_matches(event_name, state, setup):
                event_hits.add(event_name)
                body = node.get("body", [])
                if isinstance(body, list):
                    _run_statements(
                        body, state, setup, commands, control, steps, max_steps, event_hits, effectful_ops
                    )
        elif op == "repeat_until_end":
            body = node.get("body", [])
            if isinstance(body, list):
                _run_statements(
                    body, state, setup, commands, control, steps, max_steps, event_hits, effectful_ops
                )
            control.stop_tick = True
        elif op == "set_battery_threshold_low":
            setup["batteryThresholdLow"] = int(node.get("args", {}).get("value", setup["batteryThresholdLow"]))
        elif op == "set_battery_threshold_high":
            setup["batteryThresholdHigh"] = int(node.get("args", {}).get("value", setup["batteryThresholdHigh"]))
        elif op == "set_temp_threshold":
            setup["tempMin"] = int(node.get("args", {}).get("min", setup["tempMin"]))
            setup["tempMax"] = int(node.get("args", {}).get("max", setup["tempMax"]))
        elif op == "set_heater_power":
            setup["heaterPower"] = int(node.get("args", {}).get("value", setup["heaterPower"]))
        elif op == "enable_payload_mode":
            setup["payloadMode"] = str(node.get("args", {}).get("mode", setup["payloadMode"]))


def _grade_result(
    state: dict[str, Any],
    setup: dict[str, Any],
    world: dict[str, Any],
    *,
    effectful_main_ops: int,
) -> tuple[str, dict[str, Any]]:
    battery = state["battery"]
    temp = state["temperature"]
    temp_min = setup["tempMin"]
    temp_max = setup["tempMax"]
    mid_low = temp_min + int(world["midBandOffset"])
    mid_high = temp_max - int(world["midBandOffset"])
    if effectful_main_ops <= 0:
        grade = "fail"
    elif battery < int(world["riskyBatteryMin"]) or temp < temp_min or temp > temp_max:
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
    setup = dict(world["defaultSetup"])
    setup_body = _find_body(program_ast, "setup")
    main_body = _find_body(program_ast, "main_loop")
    _run_statements(
        setup_body,
        {
            "battery": int(world["startBattery"]),
            "temperature": int(world["startTemperature"]),
            "safe_mode": False,
            "tick": 1,
            "is_daylight": True,
            "glitch_tick": int(world["glitchTick"]),
        },
        setup,
        {
            "heater_on": False,
            "payload_on": setup.get("payloadMode") != "off",
            "enter_safe_mode": False,
            "exit_safe_mode_next_tick": False,
        },
        _TickControl(),
        [0],
        int(pack["limits"]["maxSteps"]),
        set(),
    )
    start = time.monotonic()
    state = {
        "battery": int(world["startBattery"]),
        "temperature": int(world["startTemperature"]),
        "safe_mode": False,
        "tick": 1,
        "is_daylight": True,
        "glitch_tick": int(world["glitchTick"]),
    }
    commands = {
        "heater_on": False,
        "payload_on": setup.get("payloadMode") != "off",
        "enter_safe_mode": False,
        "exit_safe_mode_next_tick": False,
    }
    max_steps = int(pack["limits"]["maxSteps"])
    wall_ms = int(pack["limits"]["wallMs"])
    steps = [0]
    effectful_main_ops = [0]
    ticks: list[TickLogEntry] = []
    daylight = [bool(v) for v in world["daylightByTick"]]

    for tick in range(1, int(world["ticks"]) + 1):
        if (time.monotonic() - start) * 1000 > wall_ms:
            raise ValueError("Execution exceeded wallMs")
        state["tick"] = tick
        state["is_daylight"] = daylight[tick - 1]
        if commands["exit_safe_mode_next_tick"]:
            state["safe_mode"] = False
            commands["exit_safe_mode_next_tick"] = False
        control = _TickControl()
        event_hits: set[str] = set()
        if tick < int(world["ticks"]):
            _run_statements(
                main_body,
                state,
                setup,
                commands,
                control,
                steps,
                max_steps,
                event_hits,
                effectful_main_ops,
            )

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

        battery_delta = int(world["batteryDayDelta"]) if state["is_daylight"] else int(world["batteryNightDelta"])
        heater_drain = round(setup["heaterPower"] / int(world["heaterDrainDivisor"])) if effective_heater_on else 0
        payload_drain = int(world["payloadDrain"]) if effective_payload_on else 0
        safe_bonus = int(world["safeModeBatteryBonus"]) if state["safe_mode"] else 0
        state["battery"] += battery_delta - heater_drain - payload_drain + safe_bonus
        glitch_applied = tick == int(world["glitchTick"])
        if glitch_applied:
            state["battery"] -= int(world["glitchBatteryDrop"])
        state["battery"] = max(0, min(100, int(state["battery"])))

        temp_delta = int(world["temperatureDayDelta"]) if state["is_daylight"] else int(world["temperatureNightDelta"])
        heater_heat = round(setup["heaterPower"] / int(world["heaterHeatDivisor"])) if effective_heater_on else 0
        payload_heat = int(world["payloadHeat"]) if effective_payload_on else 0
        state["temperature"] += temp_delta + heater_heat + payload_heat

        ticks.append(
            TickLogEntry(
                tick=tick,
                is_daylight=state["is_daylight"],
                glitch_applied=glitch_applied,
                battery=int(state["battery"]),
                temperature=int(state["temperature"]),
                safe_mode=bool(state["safe_mode"]),
                heater_on=effective_heater_on,
                payload_on=effective_payload_on,
            )
        )

    grade, result_state = _grade_result(state, setup, world, effectful_main_ops=effectful_main_ops[0])
    return MissionRunResponse(
        mission_id=mission_id,
        mission_version=_pack_version(pack),
        ticks=ticks,
        final_battery=int(state["battery"]),
        final_temperature=int(state["temperature"]),
        result=MissionRunResult(grade=grade, **result_state),
    )
