"""RQ queue helpers for Arena mission runs."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from redis import Redis
from rq import Queue
from rq.job import Job

from app.core.config import get_settings
from app.schemas.arena import RunJobStatus, RunJobStatusResponse, RunResult

# In-process job store when ARENA_RUN_SYNC=true (pytest / no Redis).
_SYNC_JOBS: dict[str, RunJobStatusResponse] = {}


def clear_sync_jobs() -> None:
    """Reset sync job store (pytest)."""
    _SYNC_JOBS.clear()


def get_redis_connection() -> Redis:
    settings = get_settings()
    return Redis.from_url(settings.redis_url)


def get_queue() -> Queue:
    settings = get_settings()
    return Queue(
        settings.arena_rq_queue_name,
        connection=get_redis_connection(),
        default_timeout=settings.arena_run_job_timeout,
    )


def _map_rq_status(rq_status: str) -> RunJobStatus:
    if rq_status in ("queued", "deferred", "scheduled"):
        return "pending"
    if rq_status == "started":
        return "running"
    if rq_status == "finished":
        return "finished"
    return "failed"


def enqueue_run(
    db: Session,
    user_id: UUID,
    mission_id: str,
    ast: dict[str, Any],
) -> str:
    settings = get_settings()
    job_id = str(uuid4())

    if settings.arena_run_sync:
        from app.arena.engine import execute_run

        result = execute_run(
            mission_id=mission_id,
            ast=ast,
            user_id=user_id,
            db=db,
        )
        _SYNC_JOBS[job_id] = RunJobStatusResponse(
            job_id=job_id,
            status="finished",
            mission_id=mission_id,
            result=result,
            error=None,
        )
        return job_id

    from app.arena.tasks import run_mission_task

    queue = get_queue()
    job = queue.enqueue(
        run_mission_task,
        str(user_id),
        mission_id,
        ast,
        job_id=job_id,
        meta={"user_id": str(user_id), "mission_id": mission_id},
    )
    return job.id


def fetch_job_status(
    *,
    user_id: UUID,
    mission_id: str,
    job_id: str,
) -> RunJobStatusResponse | None:
    settings = get_settings()

    if settings.arena_run_sync:
        stored = _SYNC_JOBS.get(job_id)
        if stored is None:
            return None
        if stored.mission_id != mission_id:
            return None
        return stored

    try:
        job = Job.fetch(job_id, connection=get_redis_connection())
    except Exception:
        return None

    meta = job.meta or {}
    if meta.get("user_id") != str(user_id):
        return None
    if meta.get("mission_id") != mission_id:
        return None

    status = _map_rq_status(job.get_status())

    if status == "finished":
        raw = job.return_value
        result = RunResult.model_validate(raw) if raw is not None else None
        return RunJobStatusResponse(
            job_id=job_id,
            status="finished",
            mission_id=mission_id,
            result=result,
            error=None,
        )

    if status == "failed":
        err = job.exc_info or "Worker failed"
        return RunJobStatusResponse(
            job_id=job_id,
            status="failed",
            mission_id=mission_id,
            result=None,
            error=str(err)[:500],
        )

    return RunJobStatusResponse(
        job_id=job_id,
        status=status,
        mission_id=mission_id,
        result=None,
        error=None,
    )
