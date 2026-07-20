"""Optional integration tests — require Redis (docker compose)."""

import os

import pytest

pytestmark = pytest.mark.integration

PASSING_AST = {
    "type": "program",
    "body": [
        {
            "id": "b1",
            "op": "on_start",
            "body": [{"id": "b2", "op": "power_bus_on"}],
        }
    ],
}


@pytest.fixture()
def rq_settings(monkeypatch):
    monkeypatch.setenv("ARENA_RUN_SYNC", "false")
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("REDIS_URL", redis_url)
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.skipif(
    os.environ.get("RUN_ARENA_RQ_INTEGRATION") != "1",
    reason="Set RUN_ARENA_RQ_INTEGRATION=1 with Redis + arena_worker running",
)
def test_rq_enqueue_and_worker(client, auth_headers, rq_settings):
    from rq import SimpleWorker

    from app.arena.queue import get_queue

    mission_id = "leo-orbital-launch"
    post = client.post(
        f"/arena/missions/{mission_id}/runs",
        headers=auth_headers,
        json={"ast": PASSING_AST},
    )
    assert post.status_code == 200
    job_id = post.json()["job_id"]

    worker = SimpleWorker([get_queue()], connection=get_queue().connection)
    worker.work(burst=True)

    poll = client.get(
        f"/arena/missions/{mission_id}/runs/{job_id}",
        headers=auth_headers,
    )
    assert poll.status_code == 200
    data = poll.json()
    assert data["status"] == "finished"
    assert data["result"] is not None
