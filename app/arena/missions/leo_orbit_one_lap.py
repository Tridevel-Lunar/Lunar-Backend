"""Mission 01 — one full LEO orbit survival (per-second simulator)."""

from __future__ import annotations

from typing import Any

LEO_ORBIT_ONE_LAP_PACK: dict[str, Any] = {
    "id": "leo-orbit-one-lap",
    "version": 1,
    "toolboxId": "obc-eps-payload",
    "title": "ONE LAP AROUND EARTH",
    "code": "MISSION 01",
    "level": "BEGINNER",
    "playable": True,
    "enabledLibs": ["obc", "eps", "payload"],
    "payloadModuleId": "generic",
    "commLibVisible": False,
    "obcProgramMode": "single_file",
    "allowedOps": [
        "setup",
        "main_loop",
        "repeat_until_end",
        "if",
        "when",
        "compare",
        "wait_1_tick",
        "sim_sec",
        "orbit_phase",
        "battery_level",
        "is_in_sunlight",
        "is_in_eclipse",
        "temperature",
        "turn_heater",
        "enter_safe_mode",
        "exit_safe_mode",
        "turn_payload",
        # Compat shims (optional)
        "is_daylight",
        "tick_number",
    ],
    "limits": {
        "maxBlocks": 80,
        "maxDepth": 12,
        "maxSteps": 500_000,
        "wallMs": 60_000,
    },
    "setupPresets": {
        "eps": {
            "battery_threshold_low": 20,
            "battery_threshold_high": 80,
            "temp_min": 15,
            "temp_max": 55,
            "heater_power": 30,
            "locked": [],
        },
        "payload": {
            "payload_module": "generic",
            "default_on": False,
            "locked": ["payload_module", "default_on"],
        },
        "comm": {
            "pass_sim_sec": 5400,
            "downlink_policy": "auto",
            "locked": ["pass_sim_sec", "downlink_policy"],
        },
    },
    "world": {
        "altitudeKm": 400,
        "orbitPeriodSec": 5550,
        "secPerWindow": 1,
        "startPhase": 0,
        "eclipseFraction": 0.35,
        "traceSampleSec": 30,
        "startBattery": 70,
        "startTemperature": 25,
        "baseLoadPerSec": 0.008,
        "solarChargePerSec": 0.015,
        "heaterDrainPerSecAtFull": 0.02,
        "payloadDrainPerSec": 0.025,
        "safeModeBatteryBonusPerSec": 0.005,
        "tempSunDeltaPerSec": 0.002,
        "tempEclipseDeltaPerSec": -0.004,
        "radiativeCoolPerSec": 0.001,
        "heaterHeatPerSecAtFull": 0.006,
        "payloadHeatPerSec": 0.001,
        "perfectBatteryMin": 40,
        "riskyBatteryMin": 15,
        "tempMin": 15,
        "tempMax": 55,
        "midBandOffset": 5,
        "windowBudgetSec": 0.05,
        "passSimSec": 5400,
    },
    "grading": {
        "mode": "outcome_first",
        "failIfEclipseBatteryBelow": 15,
    },
}

_PACKS: dict[str, dict[str, Any]] = {
    LEO_ORBIT_ONE_LAP_PACK["id"]: LEO_ORBIT_ONE_LAP_PACK,
}


def get_mission_pack(mission_id: str) -> dict[str, Any] | None:
    return _PACKS.get(mission_id)
