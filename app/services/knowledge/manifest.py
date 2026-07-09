"""Load and validate knowledge manifest."""

from __future__ import annotations

from pathlib import Path

import yaml

KNOWLEDGE_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "data" / "knowledge"
MANIFEST_PATH = KNOWLEDGE_ROOT / "manifest.yaml"

REQUIRED_FIELDS = {"id", "title", "module", "path", "type", "language"}
VALID_MODULES = {"space", "arena", "studio"}


def load_manifest() -> list[dict]:
    data = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    sources = list(data.get("sources", []))
    _validate_manifest(sources)
    return sources


def resolve_manifest_path(rel_path: str) -> Path:
    full_path = KNOWLEDGE_ROOT / rel_path
    if not full_path.exists():
        raise FileNotFoundError(f"Knowledge file not found: {full_path}")
    return full_path


def _validate_manifest(sources: list[dict]) -> None:
    seen_ids: set[str] = set()
    for source in sources:
        missing = REQUIRED_FIELDS - set(source.keys())
        if missing:
            raise ValueError(f"Manifest entry {source.get('id', '?')} missing fields: {missing}")
        if source["id"] in seen_ids:
            raise ValueError(f"Duplicate manifest id: {source['id']}")
        seen_ids.add(source["id"])
        if source["module"] not in VALID_MODULES:
            raise ValueError(f"Invalid module for {source['id']}: {source['module']}")
