"""Reference Perfect-pass AST for Mission 01 (leo-orbit-one-lap)."""

from __future__ import annotations

from typing import Any

ONE_LAP_PASS_AST: dict[str, Any] = {
    "type": "program",
    "body": [
        {"id": "setup1", "op": "setup", "body": []},
        {
            "id": "main1",
            "op": "main_loop",
            "body": [
                {
                    "id": "i1",
                    "op": "if",
                    "cond": {
                        "id": "c1",
                        "op": "compare",
                        "args": {
                            "left": {"id": "l1", "op": "is_in_sunlight"},
                            "cmp": "eq",
                            "right": 1,
                        },
                    },
                    "then": [{"id": "h0", "op": "turn_heater", "args": {"on": False}}],
                    "else": [{"id": "h1", "op": "turn_heater", "args": {"on": True}}],
                },
                {
                    "id": "w_ecl",
                    "op": "when",
                    "args": {"event": "eclipse_enter"},
                    "body": [{"id": "tp0", "op": "turn_payload", "args": {"on": False}}],
                },
                {"id": "yield1", "op": "wait_1_tick"},
            ],
        },
    ],
}

# Back-compat alias for older imports
M01_PASS_AST = ONE_LAP_PASS_AST
