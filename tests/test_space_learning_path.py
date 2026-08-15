from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessageChunk

from app.services.rag.prompts import get_space_path_system_prompt
from app.services.space_learning_path import (
    parse_path_fence,
    sanitize_edges,
    sanitize_proposal,
    sanitize_steps,
    visible_chat_text,
)
from app.schemas.space_learning_path import PathStep


def test_space_path_prompt_includes_digest_and_opening() -> None:
    prompt = get_space_path_system_prompt()
    assert "cubesat-for-beginner" in prompt
    assert "space-for-thailand" in prompt
    assert "Recommend ONLY" in prompt or "Never invent" in prompt
    assert "ผู้ช่วยเรียนรู้บน Lunar" in prompt
    assert "map, not a forced timeline" in prompt
    assert "Honor catalog" in prompt
    assert "Do not collapse a path onto" in prompt
    assert "space-for-thailand" in prompt
    assert "earth-from-orbit" in prompt
    assert "ground-and-ops" in prompt
    assert "Freedom first" in prompt
    assert "NOT locked to lessons" in prompt
    assert "do not know how to start" in prompt
    assert "Guardrails" in prompt
    assert "MAY answer briefly" in prompt
    assert "off-topic" in prompt

def test_sanitize_drops_unknown_course_ids() -> None:
    steps = sanitize_steps(
        [
            PathStep(courseId="not-a-real-course"),
            PathStep(courseId="cubesat-for-beginner", note="pilot"),
            PathStep(courseId="cubesat-for-beginner"),
        ]
    )
    assert [s.courseId for s in steps] == ["cubesat-for-beginner"]


def test_sanitize_proposal_keeps_non_cubesat_path() -> None:
    proposal = sanitize_proposal(
        {
            "intentTags": ["earth-app", ""],
            "steps": [
                {"courseId": "space-in-plain-sight", "note": "เริ่มจากรอบตัว"},
                {"courseId": "invented-course"},
                {"courseId": "space-for-thailand"},
            ],
            "final": False,
        }
    )
    assert [s.courseId for s in proposal.steps] == [
        "space-in-plain-sight",
        "space-for-thailand",
    ]
    assert "cubesat-for-beginner" not in [s.courseId for s in proposal.steps]
    assert proposal.intentTags == ["earth-app"]


def test_sanitize_edges_keeps_branches_and_drops_cycles() -> None:
    ids = {"space-in-plain-sight", "space-for-thailand", "cubesat-for-beginner"}
    edges = sanitize_edges(
        [
            {"from": "space-in-plain-sight", "to": "space-for-thailand"},
            {"from": "space-in-plain-sight", "to": "cubesat-for-beginner"},
            {"from": "ghost", "to": "space-for-thailand"},
            {"from": "space-for-thailand", "to": "space-in-plain-sight"},
            {"from": "space-in-plain-sight", "to": "space-in-plain-sight"},
        ],
        ids,
    )
    pairs = [(e.from_, e.to) for e in edges]
    assert ("space-in-plain-sight", "space-for-thailand") in pairs
    assert ("space-in-plain-sight", "cubesat-for-beginner") in pairs
    assert ("ghost", "space-for-thailand") not in pairs
    assert ("space-for-thailand", "space-in-plain-sight") not in pairs


def test_sanitize_proposal_keeps_branch_edges() -> None:
    proposal = sanitize_proposal(
        {
            "intentTags": ["earth-app"],
            "steps": [
                {"courseId": "space-in-plain-sight"},
                {"courseId": "space-for-thailand"},
                {"courseId": "cubesat-for-beginner"},
            ],
            "edges": [
                {"from": "space-in-plain-sight", "to": "space-for-thailand"},
                {"from": "space-in-plain-sight", "to": "cubesat-for-beginner"},
                {"from": "invented", "to": "space-for-thailand"},
            ],
            "final": False,
        }
    )
    pairs = [(e.from_, e.to) for e in proposal.edges]
    assert pairs == [
        ("space-in-plain-sight", "space-for-thailand"),
        ("space-in-plain-sight", "cubesat-for-beginner"),
    ]


def test_parse_path_fence_and_visible_text() -> None:
    text = (
        "ลองเริ่มจากอวกาศรอบตัวก่อนนะ\n"
        "```path\n"
        '{"intentTags":["why-space"],"steps":[{"courseId":"space-in-plain-sight"},'
        '{"courseId":"ghost-id"}],"final":false}\n'
        "```"
    )
    proposal = parse_path_fence(text)
    assert proposal is not None
    assert [s.courseId for s in proposal.steps] == ["space-in-plain-sight"]
    assert "```path" not in visible_chat_text(text)
    assert "อวกาศรอบตัว" in visible_chat_text(text)
    assert visible_chat_text("กำลังคิด ```path\n{\"steps\"") == "กำลังคิด"


def test_learning_path_requires_auth(client: TestClient) -> None:
    assert client.get("/space/learning-path").status_code == 401


def test_learning_path_none_then_skip_then_delete(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    empty = client.get("/space/learning-path", headers=auth_headers)
    assert empty.status_code == 200
    assert empty.json()["status"] == "none"

    skipped = client.put(
        "/space/learning-path",
        headers=auth_headers,
        json={"status": "skipped"},
    )
    assert skipped.status_code == 200
    assert skipped.json()["status"] == "skipped"
    assert skipped.json()["steps"] == []

    again = client.get("/space/learning-path", headers=auth_headers)
    assert again.json()["status"] == "skipped"

    cleared = client.delete("/space/learning-path", headers=auth_headers)
    assert cleared.status_code == 204
    assert client.get("/space/learning-path", headers=auth_headers).json()["status"] == "none"


def test_learning_path_put_active_and_reject_invented_only(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    bad = client.put(
        "/space/learning-path",
        headers=auth_headers,
        json={
            "status": "active",
            "steps": [{"courseId": "totally-fake"}],
        },
    )
    assert bad.status_code == 400

    ok = client.put(
        "/space/learning-path",
        headers=auth_headers,
        json={
            "status": "active",
            "intentText": "อยากช่วยเกษตร",
            "intentTags": ["earth-app"],
            "steps": [
                {"courseId": "space-for-thailand", "note": "ใช้ในไทย"},
                {"courseId": "not-real"},
            ],
        },
    )
    assert ok.status_code == 200
    data = ok.json()
    assert data["status"] == "active"
    assert [s["courseId"] for s in data["steps"]] == ["space-for-thailand"]

    branched = client.put(
        "/space/learning-path",
        headers=auth_headers,
        json={
            "status": "active",
            "intentTags": ["earth-app"],
            "steps": [
                {"courseId": "space-in-plain-sight"},
                {"courseId": "space-for-thailand"},
                {"courseId": "cubesat-for-beginner"},
            ],
            "edges": [
                {"from": "space-in-plain-sight", "to": "space-for-thailand"},
                {"from": "space-in-plain-sight", "to": "cubesat-for-beginner"},
            ],
        },
    )
    assert branched.status_code == 200
    assert branched.json()["edges"] == [
        {"from": "space-in-plain-sight", "to": "space-for-thailand"},
        {"from": "space-in-plain-sight", "to": "cubesat-for-beginner"},
    ]


@patch("app.services.space_learning_path.get_llm")
def test_path_stream_emits_sanitized_plan_delta(
    mock_get_llm: MagicMock,
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    from app.core.config import get_settings

    get_settings.cache_clear()

    spoken = "ลองเส้นนี้ก่อนนะ "
    fence = (
        "```path\n"
        '{"intentTags":["earth-app"],"steps":['
        '{"courseId":"space-in-plain-sight"},'
        '{"courseId":"invented-xyz"},'
        '{"courseId":"space-for-thailand"}],'
        '"edges":[{"from":"space-in-plain-sight","to":"space-for-thailand"},'
        '{"from":"space-in-plain-sight","to":"invented-xyz"}],'
        '"final":true}\n'
        "```"
    )
    full = spoken + fence

    class FakeLlm:
        def stream(self, _messages):
            yield AIMessageChunk(content=full)

    mock_get_llm.return_value = FakeLlm()

    with client.stream(
        "POST",
        "/space/laika/path/stream",
        headers=auth_headers,
        json={"content": "อวกาศช่วยเกษตรไทยได้ไหม", "messages": []},
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    assert "event: token" in body
    assert spoken.strip() in body or "ลองเส้นนี้ก่อนนะ" in body
    assert "invented-xyz" not in body
    assert "event: plan" in body
    assert "space-in-plain-sight" in body
    assert "space-for-thailand" in body
    assert "cubesat-for-beginner" not in body or body.count("cubesat-for-beginner") == 0
    assert "event: done" in body

    saved = client.get("/space/learning-path", headers=auth_headers)
    assert saved.json()["status"] == "active"
    ids = [s["courseId"] for s in saved.json()["steps"]]
    assert ids == ["space-in-plain-sight", "space-for-thailand"]
    assert saved.json()["edges"] == [
        {"from": "space-in-plain-sight", "to": "space-for-thailand"},
    ]
