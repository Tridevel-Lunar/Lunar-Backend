"""Mission 01 — LEO Orbital Launch pack (static; no DB)."""

from __future__ import annotations

from typing import Any

LEO_ORBITAL_LAUNCH_PACK: dict[str, Any] = {
    "id": "leo-orbital-launch",
    "toolboxId": "m01-beginner",
    "title": "LEO ORBITAL LAUNCH",
    "code": "MISSION 01",
    "level": "BEGINNER",
    "playable": True,
    "allowedOps": [
        "on_start",
        "await_phase",
        "power_bus_on",
        "read_power",
        "payload_set",
        "sensor_enable",
        "sensor_read",
        "begin_ascent",
        "orbit_stability",
        "until_stable",
        "confirm_leo",
        "if",
        "compare",
        "safe_mode_payload_off",
    ],
    "limits": {
        "maxBlocks": 40,
        "maxDepth": 12,
        "maxSteps": 500,
        "wallMs": 3000,
    },
    "world": {
        "phase": "pre_separation",
        "powerWh": 12,
        "payloadOn": False,
        "sensors": {"temp": False, "imu": False},
        "orbit": {"altitudeKm": 0, "stability": 0, "inLeo": False},
        "faults": [],
    },
    "success": [
        {"id": "inserted_to_leo", "type": "flag", "key": "inserted_to_leo", "equals": True},
        {"id": "stability_ok", "type": "range", "key": "orbit.stability", "min": 0.7},
        {"id": "power_reserve", "type": "range", "key": "powerWh", "min": 2},
        {"id": "payload_safe", "type": "flag", "key": "payload_safe", "equals": True},
    ],
}

_PACKS: dict[str, dict[str, Any]] = {
    LEO_ORBITAL_LAUNCH_PACK["id"]: LEO_ORBITAL_LAUNCH_PACK,
}


def get_mission_pack(mission_id: str) -> dict[str, Any] | None:
    return _PACKS.get(mission_id)
