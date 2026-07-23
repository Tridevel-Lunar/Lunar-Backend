from app.models.user import User
from app.services import arena as arena_service
from app.services.learning_context import resolve_learning_context
from app.services.rag.prompts import format_learning_context


def _user_id(db, auth_headers) -> str:
    del auth_headers  # ensures registration ran
    user = db.query(User).filter(User.email == "pytest@lunar.dev").one()
    return user.id


def test_resolve_learning_context_empty(db, client, auth_headers):
    arena_service.clear_attempts(db)
    ctx = resolve_learning_context(db, _user_id(db, auth_headers))
    assert ctx.course == "cubesat-for-beginner"
    assert ctx.completed_modules == []
    assert ctx.pending_modules == ["overview", "anatomy", "physics", "programming"]
    assert ctx.space_progress_percent == 0
    assert ctx.arena_missions == []


def test_resolve_learning_context_with_space_progress(db, client, auth_headers):
    complete = client.put(
        "/space/courses/cubesat-for-beginner/modules/physics/complete",
        headers=auth_headers,
    )
    assert complete.status_code == 200

    ctx = resolve_learning_context(db, _user_id(db, auth_headers))
    assert ctx.course == "cubesat-for-beginner"
    assert ctx.completed_modules == ["physics"]
    assert "physics" not in ctx.pending_modules
    assert ctx.space_progress_percent == 25
    assert any("Physics for Space" in topic for topic in ctx.completed_topics)

    formatted = format_learning_context(ctx.model_dump())
    assert "Space progress: 25%" in formatted
    assert "Completed modules:" in formatted
    assert "Not yet completed:" in formatted


def test_resolve_learning_context_with_arena_draft(db, client, auth_headers):
    arena_service.clear_attempts(db)
    save = client.put(
        "/arena/missions/leo-orbit-one-lap/attempt",
        headers=auth_headers,
        json={"ast": {"type": "Program", "body": []}},
    )
    assert save.status_code == 200

    ctx = resolve_learning_context(db, _user_id(db, auth_headers))
    assert len(ctx.arena_missions) == 1
    assert "Blockly draft saved" in ctx.arena_missions[0]


def test_laika_learning_context_endpoint(client, auth_headers):
    response = client.get("/laika/learning-context", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["course"] == "cubesat-for-beginner"
    assert "pending_modules" in data
    assert "space_progress_percent" in data
