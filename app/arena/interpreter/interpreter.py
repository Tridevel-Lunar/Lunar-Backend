"""Tree-walking AST interpreter for Arena missions."""

from __future__ import annotations

import time
from typing import Any

from app.arena.world.base import MissionWorld, WorldError
from app.arena.world.m01 import M01World


class InterpretTimeout(Exception):
    pass


def _make_world(mission_id: str, seed: dict[str, Any]) -> MissionWorld:
    if mission_id == "leo-orbital-launch":
        return M01World(seed)
    return M01World(seed)


def interpret(
    ast: dict[str, Any],
    *,
    mission_id: str,
    pack: dict[str, Any],
) -> dict[str, Any]:
    """Run AST against a fresh MissionWorld; return a RunResult-shaped dict."""
    limits = pack.get("limits") or {}
    max_steps = int(limits.get("maxSteps", 500))
    wall_ms = int(limits.get("wallMs", 3000))
    success_rules = list(pack.get("success") or [])
    world_seed = dict(pack.get("world") or {})

    world = _make_world(mission_id, world_seed)
    frames: list[dict[str, Any]] = []
    steps = 0
    started = time.perf_counter()

    def check_limits() -> None:
        nonlocal steps
        steps += 1
        if steps > max_steps:
            raise InterpretTimeout()
        elapsed_ms = (time.perf_counter() - started) * 1000
        if elapsed_ms > wall_ms:
            raise InterpretTimeout()

    def capture_frame() -> None:
        if isinstance(world, M01World):
            frames.append(world.frame())
        else:
            snap = world.snapshot()
            frames.append(
                {
                    "t": steps,
                    "altitudeKm": (snap.get("orbit") or {}).get("altitudeKm", 0),
                    "phase": snap.get("phase", ""),
                    "powerWh": snap.get("powerWh", 0),
                }
            )

    def eval_expr(node: dict[str, Any] | Any) -> Any:
        if not isinstance(node, dict):
            return node
        op = node.get("op")
        if op is None:
            return node
        check_limits()
        if op == "compare":
            args = node.get("args") or {}
            left = eval_expr(args.get("left"))
            right = eval_expr(args.get("right"))
            cmp_op = args.get("cmp", "gte")
            try:
                left_n = float(left)
                right_n = float(right)
            except (TypeError, ValueError):
                return False
            if cmp_op in ("gte", ">="):
                return left_n >= right_n
            if cmp_op in ("gt", ">"):
                return left_n > right_n
            if cmp_op in ("lte", "<="):
                return left_n <= right_n
            if cmp_op in ("lt", "<"):
                return left_n < right_n
            if cmp_op in ("eq", "=="):
                return left_n == right_n
            return False

        if op in ("read_power", "sensor_read", "orbit_stability"):
            return world.apply(op, node.get("args"), node.get("id"))

        return world.apply(str(op), node.get("args"), node.get("id"))

    def exec_node(node: dict[str, Any]) -> None:
        check_limits()
        op = node.get("op")
        block_id = node.get("id")

        if op == "on_start":
            for child in node.get("body") or []:
                if isinstance(child, dict):
                    exec_node(child)
                    capture_frame()
            return

        if op == "if":
            cond = node.get("cond")
            ok = bool(eval_expr(cond)) if cond is not None else False
            branch = node.get("then") if ok else node.get("else")
            for child in branch or []:
                if isinstance(child, dict):
                    exec_node(child)
                    capture_frame()
            return

        if op == "compare":
            eval_expr(node)
            return

        world.apply(str(op), node.get("args"), block_id)
        capture_frame()

    try:
        body = ast.get("body") or []
        for top in body:
            if isinstance(top, dict):
                exec_node(top)
        if not frames:
            capture_frame()

        passed, failed = world.grade(success_rules)
        status = "passed" if not failed else "failed"

        return {
            "status": status,
            "passedChecks": passed,
            "failedChecks": failed,
            "finalWorld": world.snapshot(),
            "metrics": world.metrics(),
            "frames": frames,
            "log": world.run_log if isinstance(world, M01World) else [],
        }

    except InterpretTimeout:
        passed, failed = world.grade(success_rules)
        return {
            "status": "timeout",
            "passedChecks": passed,
            "failedChecks": failed,
            "error": {
                "blockId": "",
                "code": "timeout",
                "messageTh": "การจำลองใช้เวลานานเกินไป หรือมีขั้นตอนมากเกินไป",
            },
            "finalWorld": world.snapshot(),
            "metrics": world.metrics(),
            "frames": frames,
            "log": world.run_log if isinstance(world, M01World) else [],
        }

    except WorldError as exc:
        passed, failed = world.grade(success_rules)
        return {
            "status": "error",
            "passedChecks": passed,
            "failedChecks": failed,
            "error": {
                "blockId": exc.block_id or "",
                "code": exc.code,
                "messageTh": exc.message_th,
            },
            "finalWorld": world.snapshot(),
            "metrics": world.metrics(),
            "frames": frames,
            "log": world.run_log if isinstance(world, M01World) else [],
        }
