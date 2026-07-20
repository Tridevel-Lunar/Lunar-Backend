"""Mission 01 discrete world — LEO Orbital Launch."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.arena.world.base import MissionWorld, WorldError


def _get_path(state: dict[str, Any], key: str) -> Any:
    cur: Any = state
    for part in key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


class M01World(MissionWorld):
    """Hand-authored phase machine for leo-orbital-launch."""

    STANDBY_DRAW = 0.05
    SENSOR_DRAW = 0.08
    ASCENT_DRAW = 0.15
    PAYLOAD_MIN_POWER = 4.0

    def __init__(self, seed: dict[str, Any]) -> None:
        self.state = deepcopy(seed)
        self.state.setdefault("phase", "pre_separation")
        self.state.setdefault("powerWh", 12.0)
        self.state.setdefault("payloadOn", False)
        self.state.setdefault("payload_safe", True)
        self.state.setdefault("powerBusOn", False)
        self.state.setdefault("inserted_to_leo", False)
        self.state.setdefault("sensors", {"temp": False, "imu": False})
        self.state.setdefault("orbit", {"altitudeKm": 0.0, "stability": 0.0, "inLeo": False})
        self.state.setdefault("faults", [])

        self.ticks = 0
        self.peak_power_draw = 0.0
        self._correct_steps = 0
        self._ascent_started = False
        self._log: list[dict[str, Any]] = []
        self._highlights: list[str] = []

    def log(self, level: str, message_th: str, block_id: str | None = None) -> None:
        entry: dict[str, Any] = {
            "t": self.ticks,
            "level": level,
            "messageTh": message_th,
        }
        if block_id:
            entry["blockId"] = block_id
        self._log.append(entry)

    @property
    def run_log(self) -> list[dict[str, Any]]:
        return list(self._log)

    def apply(self, op: str, args: dict[str, Any] | None, block_id: str | None) -> Any:
        args = args or {}
        self._highlights = [block_id] if block_id else []

        if op == "power_bus_on":
            self.state["powerBusOn"] = True
            if self.state["phase"] == "pre_separation":
                self.state["phase"] = "ready_for_release"
            self._correct_steps = max(self._correct_steps, 1)
            self.log("info", "เปิดบัสพลังงานแล้ว", block_id)
            self.tick()
            return None

        if op == "await_phase":
            target = args.get("phase", "ready_for_release")
            if self.state["phase"] == "pre_separation" and self.state.get("powerBusOn"):
                self.state["phase"] = "ready_for_release"
            if self.state["phase"] != target and target == "ready_for_release":
                if self.state.get("powerBusOn"):
                    self.state["phase"] = "ready_for_release"
                else:
                    self.log("warn", "ยังไม่พร้อมปล่อย — ต้องเปิดบัสพลังงานก่อน", block_id)
            self.tick()
            return None

        if op == "read_power":
            return float(self.state["powerWh"])

        if op == "payload_set":
            on = bool(args.get("on", False))
            if on and float(self.state["powerWh"]) < self.PAYLOAD_MIN_POWER:
                self.state["payloadOn"] = True
                self.state["payload_safe"] = False
                self.log("error", "พลังงานไม่พอสำหรับ payload", block_id)
            else:
                self.state["payloadOn"] = on
                if on:
                    self.state["payload_safe"] = True
                    self._correct_steps = max(self._correct_steps, 6)
                    self.log("info", "เปิด payload แล้ว", block_id)
                else:
                    self.log("info", "ปิด payload แล้ว", block_id)
            self.tick()
            return None

        if op == "sensor_enable":
            sensor = str(args.get("sensor", "imu"))
            sensors = self.state["sensors"]
            if sensor in sensors:
                sensors[sensor] = True
                if sensor == "imu" and self.state.get("powerBusOn"):
                    self._correct_steps = max(self._correct_steps, 2)
                self.log("info", f"เปิดเซนเซอร์ {sensor} แล้ว", block_id)
            self.tick()
            return None

        if op == "sensor_read":
            sensor = str(args.get("sensor", "temp"))
            # Stub table values for M01
            table = {"temp": 22.5, "imu": 0.12}
            return float(table.get(sensor, 0.0))

        if op == "begin_ascent":
            if not self.state.get("powerBusOn"):
                raise WorldError(
                    "power_required",
                    "ต้องเปิดบัสพลังงานก่อนเริ่มขึ้นสู่วงโคจร",
                    block_id,
                )
            if not self.state["sensors"].get("imu"):
                raise WorldError(
                    "sensor_required",
                    "ต้องเปิดเซนเซอร์ IMU ก่อนเริ่มขึ้นสู่วงโคจร",
                    block_id,
                )
            self.state["phase"] = "ascent"
            self._ascent_started = True
            self._correct_steps = max(self._correct_steps, 3)
            self.state["orbit"]["altitudeKm"] = max(float(self.state["orbit"]["altitudeKm"]), 50.0)
            self.log("info", "เริ่มลำดับขึ้นสู่วงโคจร", block_id)
            self.tick()
            return None

        if op == "orbit_stability":
            return float(self.state["orbit"]["stability"])

        if op == "until_stable":
            threshold = float(args.get("threshold", 0.7))
            max_tries = int(args.get("maxTries", 5))
            if not self._ascent_started:
                self.log("warn", "ยังไม่ได้เริ่มขึ้นสู่วงโคจร — เสถียรภาพไม่เพิ่มขึ้น", block_id)
            for _ in range(max(1, max_tries)):
                if self._ascent_started:
                    # Advance stability toward 1.0 with correct prior steps
                    gain = 0.18 + (0.05 * min(self._correct_steps, 4))
                    self.state["orbit"]["stability"] = min(
                        1.0, float(self.state["orbit"]["stability"]) + gain
                    )
                    alt = float(self.state["orbit"]["altitudeKm"])
                    self.state["orbit"]["altitudeKm"] = min(420.0, alt + 60.0)
                self.tick()
                if float(self.state["orbit"]["stability"]) >= threshold:
                    self.state["phase"] = "leo_check"
                    self._correct_steps = max(self._correct_steps, 4)
                    self.log("info", "วงโคจรเสถียรพอแล้ว", block_id)
                    return True
            self.log("warn", "ลูปตรวจเสถียรภาพครบแล้ว แต่ยังไม่ถึงเกณฑ์", block_id)
            return False

        if op == "confirm_leo":
            stab = float(self.state["orbit"]["stability"])
            alt = float(self.state["orbit"]["altitudeKm"])
            if stab >= 0.7 and alt >= 200 and self._ascent_started:
                self.state["inserted_to_leo"] = True
                self.state["orbit"]["inLeo"] = True
                self.state["phase"] = "done"
                self._correct_steps = max(self._correct_steps, 5)
                self.log("info", "ยืนยันเข้าสู่ LEO สำเร็จ", block_id)
            else:
                self.log(
                    "warn",
                    "ยังเข้า LEO ไม่ได้ — ตรวจเสถียรภาพและความสูงอีกครั้ง",
                    block_id,
                )
            self.tick()
            return bool(self.state["inserted_to_leo"])

        if op == "safe_mode_payload_off":
            self.state["payloadOn"] = False
            self.state["payload_safe"] = True
            self.state["powerWh"] = min(12.0, float(self.state["powerWh"]) + 0.5)
            self.log("info", "โหมดฉุกเฉิน: ปิด payload แล้ว", block_id)
            self.tick()
            return None

        # Control-only ops handled by interpreter (on_start, if, compare)
        return None

    def tick(self) -> None:
        self.ticks += 1
        draw = 0.0
        if self.state.get("powerBusOn"):
            draw += self.STANDBY_DRAW
        sensors = self.state.get("sensors") or {}
        if sensors.get("imu"):
            draw += self.SENSOR_DRAW
        if sensors.get("temp"):
            draw += self.SENSOR_DRAW * 0.5
        if self.state["phase"] == "ascent":
            draw += self.ASCENT_DRAW
        if self.state.get("payloadOn"):
            draw += 0.2
        self.peak_power_draw = max(self.peak_power_draw, draw)
        self.state["powerWh"] = max(0.0, round(float(self.state["powerWh"]) - draw, 3))

    def snapshot(self) -> dict[str, Any]:
        return {
            "powerWh": round(float(self.state["powerWh"]), 3),
            "payloadOn": bool(self.state["payloadOn"]),
            "payload_safe": bool(self.state.get("payload_safe", True)),
            "phase": str(self.state["phase"]),
            "powerBusOn": bool(self.state.get("powerBusOn", False)),
            "inserted_to_leo": bool(self.state.get("inserted_to_leo", False)),
            "sensors": dict(self.state.get("sensors") or {}),
            "orbit": {
                "altitudeKm": round(float(self.state["orbit"]["altitudeKm"]), 2),
                "stability": round(float(self.state["orbit"]["stability"]), 3),
                "inLeo": bool(self.state["orbit"]["inLeo"]),
            },
            "faults": list(self.state.get("faults") or []),
        }

    def frame(self) -> dict[str, Any]:
        snap = self.snapshot()
        frame: dict[str, Any] = {
            "t": self.ticks,
            "altitudeKm": snap["orbit"]["altitudeKm"],
            "phase": snap["phase"],
            "powerWh": snap["powerWh"],
        }
        if self._highlights:
            frame["highlights"] = list(self._highlights)
        return frame

    def grade(self, success_rules: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
        # Expose grading keys on a flat-ish view
        view = {
            **self.state,
            "orbit.stability": self.state["orbit"]["stability"],
            "orbit.altitudeKm": self.state["orbit"]["altitudeKm"],
            "orbit.inLeo": self.state["orbit"]["inLeo"],
        }
        passed: list[str] = []
        failed: list[str] = []
        for rule in success_rules:
            rule_id = str(rule.get("id", "unknown"))
            rtype = rule.get("type")
            key = str(rule.get("key", ""))
            value = view.get(key)
            if value is None and "." in key:
                value = _get_path(self.state, key)

            ok = False
            if rtype == "flag":
                ok = value == rule.get("equals")
            elif rtype == "range":
                try:
                    num = float(value)
                except (TypeError, ValueError):
                    num = None
                if num is not None:
                    ok = True
                    if "min" in rule and num < float(rule["min"]):
                        ok = False
                    if "max" in rule and num > float(rule["max"]):
                        ok = False
            if ok:
                passed.append(rule_id)
            else:
                failed.append(rule_id)
        return passed, failed

    def metrics(self) -> dict[str, Any]:
        return {
            "peakPowerDraw": round(self.peak_power_draw, 3),
            "ticks": self.ticks,
            "stabilityFinal": round(float(self.state["orbit"]["stability"]), 3),
            "insertedToLeo": bool(self.state.get("inserted_to_leo", False)),
        }
