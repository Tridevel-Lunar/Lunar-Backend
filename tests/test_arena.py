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


def _poll_run_result(client, auth_headers, mission_id: str, ast: dict) -> dict:
    post = client.post(
        f"/arena/missions/{mission_id}/runs",
        headers=auth_headers,
        json={"ast": ast},
    )
    assert post.status_code == 200
    job = post.json()
    assert "job_id" in job
    assert job["status"] == "pending"

    poll = client.get(
        f"/arena/missions/{mission_id}/runs/{job['job_id']}",
        headers=auth_headers,
    )
    assert poll.status_code == 200
    data = poll.json()
    assert data["status"] == "finished"
    assert data["result"] is not None
    return data["result"]


def test_get_mission_requires_auth(client):
    response = client.get("/arena/missions/leo-orbital-launch")
    assert response.status_code == 401


def test_get_mission_pack(client, auth_headers):
    response = client.get("/arena/missions/leo-orbital-launch", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "leo-orbital-launch"
    assert data["toolboxId"] == "m01-beginner"
    assert data["playable"] is True
    assert "on_start" in data["allowedOps"]
    assert data["limits"]["maxBlocks"] == 40


def test_get_unknown_mission_404(client, auth_headers):
    response = client.get("/arena/missions/coming-soon", headers=auth_headers)
    assert response.status_code == 404


def test_attempt_save_load_round_trip(client, auth_headers):
    mission_id = "leo-orbital-launch"
    empty = client.get(f"/arena/missions/{mission_id}/attempt", headers=auth_headers)
    assert empty.status_code == 200
    assert empty.json()["ast"] is None
    assert empty.json()["last_result"] is None

    ast = {
        "type": "program",
        "body": [
            {
                "id": "b1",
                "op": "on_start",
                "body": [{"id": "b2", "op": "power_bus_on"}],
            }
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
    assert loaded.json()["ast"] == ast


def test_attempt_unknown_mission_404(client, auth_headers):
    response = client.put(
        "/arena/missions/unknown/attempt",
        headers=auth_headers,
        json={"ast": {"type": "program", "body": []}},
    )
    assert response.status_code == 404


def test_run_passing_ast(client, auth_headers):
    mission_id = "leo-orbital-launch"
    data = _poll_run_result(client, auth_headers, mission_id, PASSING_AST)
    assert data["status"] == "passed"
    assert data["failedChecks"] == []
    assert data["metrics"]["insertedToLeo"] is True
    assert data["finalWorld"]["orbit"]["inLeo"] is True

    attempt = client.get(f"/arena/missions/{mission_id}/attempt", headers=auth_headers)
    assert attempt.status_code == 200
    assert attempt.json()["ast"] == PASSING_AST
    assert attempt.json()["last_result"]["status"] == "passed"


def test_run_ascent_without_imu_error(client, auth_headers):
    ast = {
        "type": "program",
        "body": [
            {
                "id": "b1",
                "op": "on_start",
                "body": [
                    {"id": "b2", "op": "power_bus_on"},
                    {"id": "b5", "op": "begin_ascent"},
                ],
            }
        ],
    }
    data = _poll_run_result(client, auth_headers, "leo-orbital-launch", ast)
    assert data["status"] == "error"
    assert data["error"]["code"] == "sensor_required"
    assert data["error"]["blockId"] == "b5"


def test_run_unknown_op_422(client, auth_headers):
    ast = {
        "type": "program",
        "body": [{"id": "b1", "op": "on_start", "body": [{"id": "x", "op": "eval_hack"}]}],
    }
    response = client.post(
        "/arena/missions/leo-orbital-launch/runs",
        headers=auth_headers,
        json={"ast": ast},
    )
    assert response.status_code == 422


def test_run_unknown_mission_404(client, auth_headers):
    response = client.post(
        "/arena/missions/unknown/runs",
        headers=auth_headers,
        json={"ast": PASSING_AST},
    )
    assert response.status_code == 404


def test_run_job_not_found(client, auth_headers):
    response = client.get(
        "/arena/missions/leo-orbital-launch/runs/nonexistent-job",
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_pack_registered():
    assert get_mission_pack("leo-orbital-launch") is not None
