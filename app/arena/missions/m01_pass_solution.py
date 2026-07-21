"""Reference Perfect-pass AST for Mission 01 (leo-orbital-launch)."""

from __future__ import annotations

from typing import Any

M01_PASS_AST: dict[str, Any] = {
    "type": "program",
    "body": [
        {
            "id": "setup1",
            "op": "setup",
            "body": [
                {
                    "id": "sb1",
                    "op": "set_temp_threshold",
                    "args": {"min": 30, "max": 85},
                },
                {
                    "id": "sb2",
                    "op": "set_heater_power",
                    "args": {"value": 0},
                },
            ],
        },
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
                            "left": {"id": "l1", "op": "is_daylight"},
                            "cmp": "eq",
                            "right": 1,
                        },
                    },
                    "then": [{"id": "tp1", "op": "turn_payload", "args": {"on": True}}],
                    "else": [{"id": "tp0", "op": "turn_payload", "args": {"on": False}}],
                },
                {"id": "w1", "op": "wait_1_tick"},
            ],
        },
    ],
}
