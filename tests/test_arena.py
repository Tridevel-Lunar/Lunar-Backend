import pytest

from app.services.arena import clear_attempts

MISSION_ID = "leo-orbit-one-lap"


@pytest.fixture(autouse=True)
def _reset_attempts(db):
    clear_attempts(db)
    yield
    clear_attempts(db)


def test_get_mission_requires_auth(client):
    response = client.get(f"/arena/missions/{MISSION_ID}")
    assert response.status_code == 401


def test_get_mission_pack(client, auth_headers):
    response = client.get(f"/arena/missions/{MISSION_ID}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == MISSION_ID
    assert data["version"] == 1
    assert data["toolboxId"] == "obc-eps-payload"
    assert data["playable"] is True
    assert "setup" in data["allowedOps"]
    assert "is_in_sunlight" in data["allowedOps"]
    assert data["limits"]["maxBlocks"] == 80
    assert data["orbitPeriodSec"] == 5550
    assert data["enabledLibs"] == ["obc", "eps", "payload"]
    assert data["setupPresets"]["eps"]["heater_power"] == 30


def test_get_unknown_mission_404(client, auth_headers):
    response = client.get("/arena/missions/coming-soon", headers=auth_headers)
    assert response.status_code == 404


def test_old_mission_id_404(client, auth_headers):
    response = client.get("/arena/missions/leo-orbital-launch", headers=auth_headers)
    assert response.status_code == 404


def test_attempt_save_load_round_trip(client, auth_headers):
    empty = client.get(f"/arena/missions/{MISSION_ID}/attempt", headers=auth_headers)
    assert empty.status_code == 200
    assert empty.json()["ast"] is None
    assert empty.json()["workspace"] is None
    assert empty.json()["mission_version"] == 1

    ast = {
        "type": "program",
        "body": [
            {"id": "b1", "op": "setup", "body": []},
            {
                "id": "b3",
                "op": "main_loop",
                "body": [{"id": "b4", "op": "turn_payload", "args": {"on": False}}],
            },
        ],
    }
    workspace = {
        "blocks": {
            "languageVersion": 0,
            "blocks": [{"type": "obc_on_start", "id": "b1", "x": 120, "y": 80}],
        }
    }
    save = client.put(
        f"/arena/missions/{MISSION_ID}/attempt",
        headers=auth_headers,
        json={"ast": ast, "workspace": workspace},
    )
    assert save.status_code == 200
    assert save.json()["ast"] == ast
    assert save.json()["workspace"] == workspace

    loaded = client.get(f"/arena/missions/{MISSION_ID}/attempt", headers=auth_headers)
    assert loaded.status_code == 200
    assert loaded.json()["mission_id"] == MISSION_ID
    assert loaded.json()["mission_version"] == 1
    assert loaded.json()["ast"] == ast
    assert loaded.json()["workspace"] == workspace


def test_attempt_save_without_workspace_ok(client, auth_headers):
    ast = {"type": "program", "body": [{"id": "s", "op": "setup", "body": []}]}
    save = client.put(
        f"/arena/missions/{MISSION_ID}/attempt",
        headers=auth_headers,
        json={"ast": ast},
    )
    assert save.status_code == 200
    assert save.json()["ast"] == ast
    assert save.json()["workspace"] is None


def test_attempt_unknown_mission_404(client, auth_headers):
    response = client.put(
        "/arena/missions/unknown/attempt",
        headers=auth_headers,
        json={"ast": {"type": "program", "body": []}},
    )
    assert response.status_code == 404


def _program_for_run(*, setup_body=None, loop_body=None):
    return {
        "type": "program",
        "body": [
            {"id": "s", "op": "setup", "body": setup_body or []},
            {
                "id": "m",
                "op": "main_loop",
                "body": loop_body
                or [
                    {"id": "tp", "op": "turn_payload", "args": {"on": False}},
                    {"id": "w", "op": "wait_1_tick"},
                ],
            },
        ],
    }


def test_run_mission_perfect_reference_solution(client, auth_headers):
    from app.arena.missions.one_lap_pass_solution import ONE_LAP_PASS_AST

    run = client.post(
        f"/arena/missions/{MISSION_ID}/runs",
        headers=auth_headers,
        json={"ast": ONE_LAP_PASS_AST},
    )
    assert run.status_code == 200
    data = run.json()
    assert data["mission_version"] == 1
    assert data["orbitPeriodSec"] == 5550
    assert data["simSecPerWindow"] == 1
    assert len(data["trace"]) >= 180  # ~5550/30 + last
    assert data["trace"][0]["simSec"] == 0
    assert data["trace"][0]["isSunlit"] is True
    assert data["orbitSummary"]["eclipseEnterSec"] > 0
    assert data["orbitSummary"]["eclipseExitSec"] > data["orbitSummary"]["eclipseEnterSec"]
    assert data["result"]["grade"] == "perfect"
    assert data["result"]["comms"] == "full"
    assert data["result"]["satellite_survived"] is True
    assert data["final_battery"] >= 40
    assert data["timing"]["overrunCount"] >= 0


def test_run_mission_with_setup_tabs(client, auth_headers):
    from app.arena.missions.one_lap_pass_solution import ONE_LAP_PASS_AST

    run = client.post(
        f"/arena/missions/{MISSION_ID}/runs",
        headers=auth_headers,
        json={
            "ast": ONE_LAP_PASS_AST,
            "epsSetup": {"heater_power": 40, "temp_min": 15, "temp_max": 55},
            "payloadSetup": {"default_on": False},
            "commSetup": {"pass_sim_sec": 5400},
        },
    )
    assert run.status_code == 200
    assert run.json()["result"]["grade"] == "perfect"


def test_run_mission_grading_fail_payload_always_on(client, auth_headers):
    """Payload left on drains battery across the full orbit → fail."""
    fail_ast = _program_for_run(
        loop_body=[
            {"id": "fp", "op": "turn_payload", "args": {"on": True}},
            {"id": "fw", "op": "wait_1_tick"},
        ],
    )
    fail = client.post(
        f"/arena/missions/{MISSION_ID}/runs",
        headers=auth_headers,
        json={"ast": fail_ast, "payloadSetup": {"default_on": True}},
    )
    assert fail.status_code == 200
    fail_data = fail.json()
    assert fail_data["result"]["grade"] == "fail"
    assert fail_data["result"]["satellite_survived"] is False


def test_run_mission_safe_mode_conflict_priority(client, auth_headers):
    ast = _program_for_run(
        loop_body=[
            {"id": "p1", "op": "turn_payload", "args": {"on": True}},
            {"id": "h1", "op": "turn_heater", "args": {"on": True}},
            {"id": "s1", "op": "enter_safe_mode"},
            {"id": "w1", "op": "wait_1_tick"},
        ],
    )
    run = client.post(
        f"/arena/missions/{MISSION_ID}/runs",
        headers=auth_headers,
        json={"ast": ast},
    )
    assert run.status_code == 200
    sample0 = run.json()["trace"][0]
    assert sample0["safeMode"] is True
    assert sample0["payloadOn"] is False
    assert sample0["heaterOn"] is False


def test_run_mission_invalid_op_422(client, auth_headers):
    ast = {"type": "program", "body": [{"id": "x", "op": "unknown_op"}]}
    run = client.post(
        f"/arena/missions/{MISSION_ID}/runs",
        headers=auth_headers,
        json={"ast": ast},
    )
    assert run.status_code == 422


def test_run_mission_empty_workspace_422(client, auth_headers):
    ast = {
        "type": "program",
        "body": [
            {"id": "s", "op": "setup", "body": []},
            {"id": "m", "op": "main_loop", "body": []},
        ],
    }
    run = client.post(
        f"/arena/missions/{MISSION_ID}/runs",
        headers=auth_headers,
        json={"ast": ast},
    )
    assert run.status_code == 422


def test_run_mission_orphan_blocks_422(client, auth_headers):
    ast = {
        "type": "program",
        "body": [{"id": "w", "op": "wait_1_tick"}],
    }
    run = client.post(
        f"/arena/missions/{MISSION_ID}/runs",
        headers=auth_headers,
        json={"ast": ast},
    )
    assert run.status_code == 422


def test_run_mission_wait_only_422(client, auth_headers):
    ast = _program_for_run(loop_body=[{"id": "w", "op": "wait_1_tick"}])
    run = client.post(
        f"/arena/missions/{MISSION_ID}/runs",
        headers=auth_headers,
        json={"ast": ast},
    )
    assert run.status_code == 422


def test_run_mission_no_effectful_ops_fail(client, auth_headers):
    """Control block present but branch never taken → fail grade."""
    ast = _program_for_run(
        loop_body=[
            {
                "id": "i1",
                "op": "if",
                "cond": {
                    "id": "c1",
                    "op": "compare",
                    "args": {
                        "left": {"id": "l1", "op": "is_in_sunlight"},
                        "cmp": "eq",
                        "right": 0,
                    },
                },
                # Branch only true in eclipse — but we never execute turn_* while
                # waiting for a branch that runs heater; use impossible compare.
                "then": [
                    {
                        "id": "i2",
                        "op": "if",
                        "cond": {
                            "id": "c2",
                            "op": "compare",
                            "args": {
                                "left": {"id": "l2", "op": "sim_sec"},
                                "cmp": "lt",
                                "right": 0,
                            },
                        },
                        "then": [{"id": "tp1", "op": "turn_payload", "args": {"on": True}}],
                    }
                ],
            },
            {"id": "w1", "op": "wait_1_tick"},
        ],
    )
    run = client.post(
        f"/arena/missions/{MISSION_ID}/runs",
        headers=auth_headers,
        json={"ast": ast},
    )
    assert run.status_code == 200
    data = run.json()
    assert data["result"]["grade"] == "fail"
    assert data["result"]["satellite_survived"] is False


def test_run_mission_eclipse_timeline(client, auth_headers):
    from app.arena.missions.one_lap_pass_solution import ONE_LAP_PASS_AST

    run = client.post(
        f"/arena/missions/{MISSION_ID}/runs",
        headers=auth_headers,
        json={"ast": ONE_LAP_PASS_AST},
    )
    data = run.json()
    enter = data["orbitSummary"]["eclipseEnterSec"]
    exit_sec = data["orbitSummary"]["eclipseExitSec"]
    # Find samples around eclipse band
    sunlit_before = [t for t in data["trace"] if t["simSec"] < enter]
    eclipse_samples = [t for t in data["trace"] if enter <= t["simSec"] < exit_sec]
    sunlit_after = [t for t in data["trace"] if t["simSec"] >= exit_sec]
    assert sunlit_before and all(t["isSunlit"] for t in sunlit_before)
    assert eclipse_samples and all(not t["isSunlit"] for t in eclipse_samples)
    assert sunlit_after and all(t["isSunlit"] for t in sunlit_after)


def test_attempt_reset_on_version_mismatch(client, auth_headers, monkeypatch):
    ast = _program_for_run()
    save = client.put(
        f"/arena/missions/{MISSION_ID}/attempt",
        headers=auth_headers,
        json={"ast": ast},
    )
    assert save.status_code == 200
    assert save.json()["mission_version"] == 1

    from app.arena import missions as missions_mod

    original_get = missions_mod.get_mission_pack

    def fake_get(mid: str):
        pack = original_get(mid)
        if not pack:
            return pack
        patched = dict(pack)
        patched["version"] = 2
        return patched

    monkeypatch.setattr(missions_mod, "get_mission_pack", fake_get)
    from app.services import arena as arena_service

    monkeypatch.setattr(arena_service, "get_mission_pack", fake_get)

    loaded = client.get(f"/arena/missions/{MISSION_ID}/attempt", headers=auth_headers)
    assert loaded.status_code == 200
    data = loaded.json()
    assert data["mission_version"] == 2
    assert data["ast"] is None
