"""Re-ingest knowledge sources already stored in the database."""

from __future__ import annotations

import argparse

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.knowledge.ingest import ingest_knowledge


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-ingest LAIKA knowledge sources from DB")
    parser.add_argument(
        "--source",
        default="all",
        help="Source UUID, manifest id, or 'all'",
    )
    args = parser.parse_args()

    settings = get_settings()
    db = SessionLocal()
    try:
        result = ingest_knowledge(db, settings, source_id=args.source)
    finally:
        db.close()

    for item in result.results:
        print(f"Ingested {item.chunks_ingested} chunks from {item.source_id}")
    print(f"Done — {result.total_chunks} chunks total")


if __name__ == "__main__":
    main()
