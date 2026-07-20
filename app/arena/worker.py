"""Arena RQ worker entrypoint (docker compose arena_worker service)."""

from __future__ import annotations

import sys

from rq.cli import main as rq_main

from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    sys.argv = [
        "rq",
        "worker",
        settings.arena_rq_queue_name,
        "--url",
        settings.redis_url,
    ]
    rq_main()


if __name__ == "__main__":
    main()
