def test_space_progress_requires_auth(client):
    response = client.get("/space/progress")
    assert response.status_code == 401


def test_space_progress_empty(client, auth_headers):
    response = client.get("/space/progress", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"completed": []}


def test_complete_module_requires_auth(client):
    response = client.put("/space/courses/cubesat-for-beginner/modules/physics/complete")
    assert response.status_code == 401


def test_complete_module_and_list(client, auth_headers):
    complete = client.put(
        "/space/courses/cubesat-for-beginner/modules/physics/complete",
        headers=auth_headers,
    )
    assert complete.status_code == 200
    data = complete.json()
    assert data["course_id"] == "cubesat-for-beginner"
    assert data["module_id"] == "physics"
    assert data["completed_at"]

    progress = client.get("/space/progress", headers=auth_headers)
    assert progress.status_code == 200
    completed = progress.json()["completed"]
    assert len(completed) == 1
    assert completed[0]["module_id"] == "physics"


def test_complete_module_is_idempotent(client, auth_headers):
    first = client.put(
        "/space/courses/cubesat-for-beginner/modules/overview/complete",
        headers=auth_headers,
    )
    second = client.put(
        "/space/courses/cubesat-for-beginner/modules/overview/complete",
        headers=auth_headers,
    )
    assert first.status_code == 200
    assert second.status_code == 200

    progress = client.get("/space/progress", headers=auth_headers)
    overview_rows = [
        row
        for row in progress.json()["completed"]
        if row["course_id"] == "cubesat-for-beginner" and row["module_id"] == "overview"
    ]
    assert len(overview_rows) == 1
