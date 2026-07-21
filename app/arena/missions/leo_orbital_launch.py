"""Mission 01 deterministic satellite mission pack (static; no DB)."""

from __future__ import annotations

from typing import Any

LEO_ORBITAL_LAUNCH_PACK: dict[str, Any] = {
    "id": "leo-orbital-launch",
    "version": 3,
    "toolboxId": "m01-beginner",
    "title": "FIRST ORBIT SURVIVAL",
    "code": "MISSION 01",
    "level": "BEGINNER",
    "playable": True,
    "allowedOps": [
        "setup",
        "main_loop",
        "set_battery_threshold_low",
        "set_battery_threshold_high",
        "set_temp_threshold",
        "set_heater_power",
        "enable_payload_mode",
        "battery_level",
        "temperature",
        "is_daylight",
        "tick_number",
        "turn_heater",
        "turn_payload",
        "enter_safe_mode",
        "exit_safe_mode",
        "if",
        "when",
        "compare",
        "wait_1_tick",
        "repeat_until_end",
    ],
    "limits": {
        "maxBlocks": 80,
        "maxDepth": 12,
        "maxSteps": 500,
        "wallMs": 3000,
    },
    "world": {
        "ticks": 10,
        "startBattery": 55,
        "startTemperature": 50,
        "daylightByTick": [True, True, False, True, False, False, True, False, True, True],
        "glitchTick": 8,
        "glitchBatteryDrop": 25,
        "batteryDayDelta": 12,
        "batteryNightDelta": -8,
        "heaterDrainDivisor": 10,
        "payloadDrain": 4,
        "safeModeBatteryBonus": 2,
        "temperatureDayDelta": 3,
        "temperatureNightDelta": -4,
        "heaterHeatDivisor": 15,
        "payloadHeat": 1,
        "perfectBatteryMin": 40,
        "riskyBatteryMin": 15,
        "midBandOffset": 5,
        "defaultSetup": {
            "batteryThresholdLow": 20,
            "batteryThresholdHigh": 80,
            "tempMin": 15,
            "tempMax": 55,
            "heaterPower": 30,
            "payloadMode": "off",
        },
    },
    "resultPolicy": {
        "comms": {
            "perfect": "full",
            "risky": "partial",
            "fail": "missed",
        },
        "payloadBonusRequiresTick10On": True,
        "longevityImpact": {
            "perfect": "none",
            "risky": "minor",
            "fail": "major",
        },
    },
    "phaseBanners": [
        {"name": "Power Phase", "startTick": 1, "endTick": 3},
        {"name": "Thermal Phase", "startTick": 4, "endTick": 6},
        {"name": "OBC Phase", "startTick": 7, "endTick": 9},
        {"name": "Comms Check", "startTick": 10, "endTick": 10},
    ],
    "demo": {
        "fixedStartingCondition": True,
        "glitchDeterministic": True,
    },
    "legacy": {
        "phase": "pre_separation",
        "powerWh": 12,
        "payloadOn": False,
        "sensors": {"temp": False, "imu": False},
        "orbit": {"altitudeKm": 0, "stability": 0, "inLeo": False},
        "faults": [],
    },
    "success": [],
}

_PACKS: dict[str, dict[str, Any]] = {
    LEO_ORBITAL_LAUNCH_PACK["id"]: LEO_ORBITAL_LAUNCH_PACK,
}


def get_mission_pack(mission_id: str) -> dict[str, Any] | None:
    return _PACKS.get(mission_id)
