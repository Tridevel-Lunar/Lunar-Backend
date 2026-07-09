"""Sync knowledge manifest from data/knowledge/ into the database."""

from __future__ import annotations

import argparse

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.knowledge.ingest import sync_manifest_sources


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync LAIKA knowledge manifest")
    parser.add_argument(
        "--source",
        default="all",
        help="Manifest source id or 'all'",
    )
    parser.add_argument(
        "--no-ingest",
        action="store_true",
        help="Sync files to DB only, skip embedding ingest",
    )
    args = parser.parse_args()

    settings = get_settings()
    db = SessionLocal()
    try:
        result = sync_manifest_sources(
            db,
            settings,
            source_id=args.source,
            auto_ingest=not args.no_ingest,
        )
    finally:
        db.close()

    for item in result.results:
        print(f"Synced {item.source_id} — {item.chunks_ingested} chunks ingested")
    print(f"Done — {result.total_chunks} chunks total")


if __name__ == "__main__":
    main()
