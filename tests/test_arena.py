import pytest

from app.services.arena import clear_attempts


@pytest.fixture(autouse=True)
def _reset_attempts(db):
    clear_attempts(db)
    yield
    clear_attempts(db)


def test_get_mission_requires_auth(client):
    response = client.get("/arena/missions/leo-orbital-launch")
    assert response.status_code == 401


def test_get_mission_pack(client, auth_headers):
    response = client.get("/arena/missions/leo-orbital-launch", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "leo-orbital-launch"
    assert data["version"] == 3
    assert data["toolboxId"] == "m01-beginner"
    assert data["playable"] is True
    assert "setup" in data["allowedOps"]
    assert data["limits"]["maxBlocks"] == 80


def test_get_unknown_mission_404(client, auth_headers):
    response = client.get("/arena/missions/coming-soon", headers=auth_headers)
    assert response.status_code == 404


def test_attempt_save_load_round_trip(client, auth_headers):
    mission_id = "leo-orbital-launch"
    empty = client.get(f"/arena/missions/{mission_id}/attempt", headers=auth_headers)
    assert empty.status_code == 200
    assert empty.json()["ast"] is None
    assert empty.json()["mission_version"] == 3

    ast = {
        "type": "program",
        "body": [
            {
                "id": "b1",
                "op": "setup",
                "body": [{"id": "b2", "op": "set_battery_threshold_low", "args": {"value": 20}}],
            },
            {"id": "b3", "op": "main_loop", "body": [{"id": "b4", "op": "turn_payload", "args": {"on": False}}]},
        ],
    }
    save = client.put(
        f"/arena/missions/{mission_id}/attempt",
        headers=auth_headers,
        json={"ast": ast},
    )
    assert save.status_code == 200
    assert save.json()["ast"] == ast

    loaded = client.get(f"/arena/missions/{mission_id}/attempt", headers=auth_headers)
    assert loaded.status_code == 200
    assert loaded.json()["mission_id"] == mission_id
    assert loaded.json()["mission_version"] == 3
    assert loaded.json()["ast"] == ast


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
                or [{"id": "tp", "op": "turn_payload", "args": {"on": False}}, {"id": "w", "op": "wait_1_tick"}],
            },
        ],
    }


def test_run_mission_perfect_with_payload_bonus(client, auth_headers):
    mission_id = "leo-orbital-launch"
    ast = _program_for_run(
        setup_body=[
            {"id": "sb1", "op": "set_temp_threshold", "args": {"min": 30, "max": 85}},
            {"id": "sb2", "op": "set_heater_power", "args": {"value": 0}},
        ],
        loop_body=[
            {
                "id": "i1",
                "op": "if",
                "cond": {
                    "id": "c1",
                    "op": "compare",
                    "args": {"left": {"id": "l1", "op": "is_daylight"}, "cmp": "eq", "right": 1},
                },
                "then": [{"id": "tp1", "op": "turn_payload", "args": {"on": True}}],
                "else": [{"id": "tp0", "op": "turn_payload", "args": {"on": False}}],
            },
            {"id": "w1", "op": "wait_1_tick"},
        ],
    )
    run = client.post(
        f"/arena/missions/{mission_id}/runs",
        headers=auth_headers,
        json={"ast": ast},
    )
    assert run.status_code == 200
    data = run.json()
    assert data["mission_version"] == 3
    assert len(data["ticks"]) == 10
    assert data["result"]["grade"] == "perfect"
    assert data["result"]["comms"] == "full"
    assert data["result"]["payload_data"] == "full"
    assert data["result"]["satellite_survived"] is True


def test_run_mission_grading_boundaries(client, auth_headers):
    mission_id = "leo-orbital-launch"
    risky_ast = _program_for_run(
        setup_body=[
            {"id": "r1", "op": "set_temp_threshold", "args": {"min": 30, "max": 85}},
        ],
        loop_body=[
            {"id": "rp", "op": "turn_payload", "args": {"on": True}},
            {"id": "rw", "op": "wait_1_tick"},
        ],
    )
    risky = client.post(
        f"/arena/missions/{mission_id}/runs",
        headers=auth_headers,
        json={"ast": risky_ast},
    )
    assert risky.status_code == 200
    risky_data = risky.json()
    assert risky_data["result"]["grade"] == "risky"
    assert 15 <= risky_data["final_battery"] < 40

    fail_ast = _program_for_run(
        setup_body=[
            {"id": "f1", "op": "set_temp_threshold", "args": {"min": -10, "max": 40}},
            {"id": "f2", "op": "set_heater_power", "args": {"value": 100}},
        ],
        loop_body=[
            {"id": "fh", "op": "turn_heater", "args": {"on": True}},
            {"id": "fp", "op": "turn_payload", "args": {"on": True}},
            {"id": "fw", "op": "wait_1_tick"},
        ],
    )
    fail = client.post(
        f"/arena/missions/{mission_id}/runs",
        headers=auth_headers,
        json={"ast": fail_ast},
    )
    assert fail.status_code == 200
    fail_data = fail.json()
    assert fail_data["result"]["grade"] == "fail"
    assert fail_data["final_battery"] < 15 or fail_data["final_temperature"] > 40


def test_run_mission_safe_mode_conflict_priority(client, auth_headers):
    mission_id = "leo-orbital-launch"
    ast = _program_for_run(
        loop_body=[
            {"id": "p1", "op": "turn_payload", "args": {"on": True}},
            {"id": "h1", "op": "turn_heater", "args": {"on": True}},
            {"id": "s1", "op": "enter_safe_mode"},
            {"id": "w1", "op": "wait_1_tick"},
        ],
    )
    run = client.post(
        f"/arena/missions/{mission_id}/runs",
        headers=auth_headers,
        json={"ast": ast},
    )
    assert run.status_code == 200
    tick1 = run.json()["ticks"][0]
    assert tick1["safe_mode"] is True
    assert tick1["payload_on"] is False
    assert tick1["heater_on"] is False


def test_run_mission_invalid_op_422(client, auth_headers):
    mission_id = "leo-orbital-launch"
    ast = {"type": "program", "body": [{"id": "x", "op": "unknown_op"}]}
    run = client.post(
        f"/arena/missions/{mission_id}/runs",
        headers=auth_headers,
        json={"ast": ast},
    )
    assert run.status_code == 422


def test_run_mission_empty_workspace_422(client, auth_headers):
    mission_id = "leo-orbital-launch"
    ast = {
        "type": "program",
        "body": [
            {"id": "s", "op": "setup", "body": []},
            {"id": "m", "op": "main_loop", "body": []},
        ],
    }
    run = client.post(
        f"/arena/missions/{mission_id}/runs",
        headers=auth_headers,
        json={"ast": ast},
    )
    assert run.status_code == 422


def test_run_mission_orphan_blocks_422(client, auth_headers):
    mission_id = "leo-orbital-launch"
    ast = {
        "type": "program",
        "body": [{"id": "w", "op": "wait_1_tick"}],
    }
    run = client.post(
        f"/arena/missions/{mission_id}/runs",
        headers=auth_headers,
        json={"ast": ast},
    )
    assert run.status_code == 422


def test_run_mission_wait_only_422(client, auth_headers):
    mission_id = "leo-orbital-launch"
    ast = _program_for_run(loop_body=[{"id": "w", "op": "wait_1_tick"}])
    run = client.post(
        f"/arena/missions/{mission_id}/runs",
        headers=auth_headers,
        json={"ast": ast},
    )
    assert run.status_code == 422


def test_run_mission_no_effectful_ops_fail(client, auth_headers):
    mission_id = "leo-orbital-launch"
    ast = _program_for_run(
        loop_body=[
            {
                "id": "i1",
                "op": "if",
                "cond": {
                    "id": "c1",
                    "op": "compare",
                    "args": {"left": {"id": "l1", "op": "is_daylight"}, "cmp": "eq", "right": 0},
                },
                "then": [{"id": "tp1", "op": "turn_payload", "args": {"on": True}}],
            },
            {"id": "w1", "op": "wait_1_tick"},
        ],
    )
    run = client.post(
        f"/arena/missions/{mission_id}/runs",
        headers=auth_headers,
        json={"ast": ast},
    )
    assert run.status_code == 200
    data = run.json()
    assert data["result"]["grade"] == "fail"
    assert data["result"]["satellite_survived"] is False


def test_run_mission_reference_solution_perfect(client, auth_headers):
    from app.arena.missions.m01_pass_solution import M01_PASS_AST

    run = client.post(
        "/arena/missions/leo-orbital-launch/runs",
        headers=auth_headers,
        json={"ast": M01_PASS_AST},
    )
    assert run.status_code == 200
    data = run.json()
    assert data["result"]["grade"] == "perfect"
    assert data["result"]["payload_data"] == "full"


def test_attempt_reset_on_version_mismatch(client, auth_headers, monkeypatch):
    mission_id = "leo-orbital-launch"
    ast = _program_for_run()
    save = client.put(
        f"/arena/missions/{mission_id}/attempt",
        headers=auth_headers,
        json={"ast": ast},
    )
    assert save.status_code == 200
    assert save.json()["mission_version"] == 3

    from app.arena import missions as missions_mod

    original_get = missions_mod.get_mission_pack

    def fake_get(mid: str):
        pack = original_get(mid)
        if not pack:
            return pack
        patched = dict(pack)
        patched["version"] = 4
        return patched

    monkeypatch.setattr(missions_mod, "get_mission_pack", fake_get)
    from app.services import arena as arena_service

    monkeypatch.setattr(arena_service, "get_mission_pack", fake_get)

    loaded = client.get(f"/arena/missions/{mission_id}/attempt", headers=auth_headers)
    assert loaded.status_code == 200
    data = loaded.json()
    assert data["mission_version"] == 4
    assert data["ast"] is None
