import pytest

from app.services.arena import clear_attempts


@pytest.fixture(autouse=True)
def _reset_attempts():
    clear_attempts()
    yield
    clear_attempts()


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
