import os

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest")

from app.services.knowledge.manifest import load_manifest


def test_manifest_loads_all_modules() -> None:
    sources = load_manifest()
    modules = {s["module"] for s in sources}
    assert modules == {"space", "arena", "studio"}
    assert len(sources) == 10


def test_manifest_ids_are_unique() -> None:
    sources = load_manifest()
    ids = [s["id"] for s in sources]
    assert len(ids) == len(set(ids))
