"""Unit tests for Arena AST validator + M01 interpreter."""

from copy import deepcopy

from app.arena.ast.validator import AstValidationError, validate_ast
from app.arena.interpreter import interpret
from app.arena.missions import get_mission_pack

PASSING_AST = {
    "type": "program",
    "body": [
        {
            "id": "b1",
            "op": "on_start",
            "body": [
                {"id": "b2", "op": "power_bus_on"},
                {"id": "b3", "op": "sensor_enable", "args": {"sensor": "imu"}},
                {
                    "id": "b4",
                    "op": "if",
                    "cond": {
                        "op": "compare",
                        "args": {
                            "left": {"op": "read_power"},
                            "cmp": "gte",
                            "right": 4,
                        },
                    },
                    "then": [{"id": "b5", "op": "begin_ascent"}],
                    "else": [{"id": "b6", "op": "safe_mode_payload_off"}],
                },
                {
                    "id": "b7",
                    "op": "until_stable",
                    "args": {"threshold": 0.7, "maxTries": 5},
                },
                {"id": "b8", "op": "confirm_leo"},
                {"id": "b9", "op": "payload_set", "args": {"on": True}},
            ],
        }
    ],
}


def _pack(**limit_overrides):
    pack = deepcopy(get_mission_pack("leo-orbital-launch"))
    assert pack is not None
    pack["limits"] = {**pack["limits"], **limit_overrides}
    return pack


def test_validate_ok():
    pack = _pack()
    validate_ast(PASSING_AST, allowed_ops=pack["allowedOps"], limits=pack["limits"])


def test_validate_unknown_op():
    pack = _pack()
    bad = {
        "type": "program",
        "body": [{"id": "a", "op": "on_start", "body": [{"id": "b", "op": "hack"}]}],
    }
    try:
        validate_ast(bad, allowed_ops=pack["allowedOps"], limits=pack["limits"])
        assert False, "expected AstValidationError"
    except AstValidationError as exc:
        assert exc.code == "unknown_op"


def test_validate_too_many_blocks():
    pack = _pack(maxBlocks=2)
    try:
        validate_ast(PASSING_AST, allowed_ops=pack["allowedOps"], limits=pack["limits"])
        assert False, "expected AstValidationError"
    except AstValidationError as exc:
        assert exc.code == "too_many_blocks"


def test_interpret_pass():
    pack = _pack()
    result = interpret(PASSING_AST, mission_id="leo-orbital-launch", pack=pack)
    assert result["status"] == "passed"
    assert result["failedChecks"] == []
    assert result["metrics"]["insertedToLeo"] is True
    assert len(result["frames"]) > 0
    assert any(e["level"] == "info" for e in result["log"])


def test_interpret_missing_confirm_leo_fails():
    pack = _pack()
    ast = {
        "type": "program",
        "body": [
            {
                "id": "b1",
                "op": "on_start",
                "body": [
                    {"id": "b2", "op": "power_bus_on"},
                    {"id": "b3", "op": "sensor_enable", "args": {"sensor": "imu"}},
                    {"id": "b5", "op": "begin_ascent"},
                    {
                        "id": "b7",
                        "op": "until_stable",
                        "args": {"threshold": 0.7, "maxTries": 5},
                    },
                    {"id": "b9", "op": "payload_set", "args": {"on": True}},
                ],
            }
        ],
    }
    result = interpret(ast, mission_id="leo-orbital-launch", pack=pack)
    assert result["status"] == "failed"
    assert "inserted_to_leo" in result["failedChecks"]


def test_interpret_low_power_payload_fails_check():
    pack = _pack()
    # Drain power then open payload
    pack["world"]["powerWh"] = 3.0
    ast = {
        "type": "program",
        "body": [
            {
                "id": "b1",
                "op": "on_start",
                "body": [
                    {"id": "b2", "op": "power_bus_on"},
                    {"id": "b3", "op": "sensor_enable", "args": {"sensor": "imu"}},
                    {"id": "b5", "op": "begin_ascent"},
                    {
                        "id": "b7",
                        "op": "until_stable",
                        "args": {"threshold": 0.7, "maxTries": 5},
                    },
                    {"id": "b8", "op": "confirm_leo"},
                    {"id": "b9", "op": "payload_set", "args": {"on": True}},
                ],
            }
        ],
    }
    result = interpret(ast, mission_id="leo-orbital-launch", pack=pack)
    assert result["status"] == "failed"
    assert "payload_safe" in result["failedChecks"]
    assert result["finalWorld"]["payload_safe"] is False


def test_interpret_timeout():
    pack = _pack(maxSteps=3)
    result = interpret(PASSING_AST, mission_id="leo-orbital-launch", pack=pack)
    assert result["status"] == "timeout"
    assert result["error"]["code"] == "timeout"
