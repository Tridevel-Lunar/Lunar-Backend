from app.services import space_catalog as catalog_service


def test_catalog_loads_and_validates():
    catalog_service.clear_catalog_cache()
    tree = catalog_service.get_catalog_tree()
    assert tree.domainId == "space-technology"
    assert tree.nodes
    assert tree.nodes[0].kind == "folder"


def test_pilot_course_published_with_outline():
    courses = list(catalog_service.iter_courses())
    published = [c for c in courses if c.status == "published"]
    assert len(published) == 1
    pilot = published[0]
    assert pilot.id == "cubesat-for-beginner"
    assert pilot.outline is not None
    assert [m.id for m in pilot.outline] == [
        "overview",
        "anatomy",
        "physics",
        "programming",
    ]


def test_no_course_has_children_shape():
    """Courses are leaves — only folders nest."""
    tree = catalog_service.get_catalog_tree()

    def walk(nodes):
        for node in nodes:
            if node.kind == "course":
                assert not hasattr(node, "children") or getattr(node, "children", None) is None
            else:
                assert node.children
                walk(node.children)

    walk(tree.nodes)


def test_digest_includes_intent_hints_for_published_and_coming_soon():
    digest = catalog_service.get_catalog_digest()
    ids = {c.id for c in digest.courses}
    assert "cubesat-for-beginner" in ids
    assert "space-for-thailand" in ids
    assert "rockets" not in ids  # later excluded by default
    thai = next(c for c in digest.courses if c.id == "space-for-thailand")
    assert thai.intentHints
    assert "earth-app" in thai.recommendWhen or "thailand" in thai.recommendWhen
    md = digest.markdown
    assert "Recommend ONLY by course id" in md
    assert "`cubesat-for-beginner`" in md
    assert "space-for-thailand" in md
    assert "intentHints:" in md


def test_format_catalog_digest_max_chars():
    short = catalog_service.format_catalog_digest(max_chars=400)
    assert "truncated" in short.lower() or len(short) <= 500


def test_get_catalog_requires_auth(client):
    assert client.get("/space/catalog").status_code == 401


def test_get_catalog_ok(client, auth_headers):
    response = client.get("/space/catalog", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["domainId"] == "space-technology"
    assert isinstance(data["nodes"], list)
    assert data["nodes"][0]["kind"] == "folder"


def test_get_catalog_digest_ok(client, auth_headers):
    response = client.get("/space/catalog/digest", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["domainId"] == "space-technology"
    assert data["markdown"]
    assert any(c["id"] == "cubesat-for-beginner" for c in data["courses"])


def test_get_catalog_digest_include_later(client, auth_headers):
    response = client.get(
        "/space/catalog/digest",
        headers=auth_headers,
        params={"include_later": True},
    )
    assert response.status_code == 200
    ids = {c["id"] for c in response.json()["courses"]}
    assert "rockets" in ids


def test_intent_system_prompt_includes_catalog_digest():
    from app.services.rag.prompts import get_intent_system_prompt

    prompt = get_intent_system_prompt("ask-anything")
    assert "Space Technology catalog" in prompt
    assert "cubesat-for-beginner" in prompt
    assert "space-for-thailand" in prompt
