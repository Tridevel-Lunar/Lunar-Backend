def test_list_collections_empty(client, auth_headers):
    response = client.get("/studio/collections", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_list_collections_requires_auth(client):
    response = client.get("/studio/collections")
    assert response.status_code == 401


def test_create_and_get_collection(client, auth_headers):
    create = client.post(
        "/studio/collections",
        headers=auth_headers,
        json={"type": "note", "content": "ทดสอบ power budget"},
    )
    assert create.status_code == 201
    data = create.json()
    assert data["type"] == "note"
    assert data["title"] == "ทดสอบ power budget"
    assert data["content"] == "ทดสอบ power budget"
    assert data["tree"]["rootIds"]
    assert len(data["tree"]["nodes"]) == 1

    collection_id = data["id"]
    get_resp = client.get(f"/studio/collections/{collection_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == collection_id


def test_patch_collection_tree(client, auth_headers):
    create = client.post(
        "/studio/collections",
        headers=auth_headers,
        json={"type": "idea", "content": "ไอเดียดาวเทียม"},
    )
    entry = create.json()
    tree = entry["tree"]
    assistant_id = "assistant-1"
    root_id = tree["rootIds"][0]
    tree["nodes"][assistant_id] = {
        "id": assistant_id,
        "role": "assistant",
        "content": "คำตอบจาก LAIKA",
        "createdAt": entry["created_at"],
        "parentId": root_id,
    }
    tree["selectedChildByParent"] = {root_id: assistant_id}

    patch = client.patch(
        f"/studio/collections/{entry['id']}",
        headers=auth_headers,
        json={
            "title": entry["title"],
            "content": entry["content"],
            "tree": tree,
            "laika_intent": "analyze",
        },
    )
    assert patch.status_code == 200
    patched = patch.json()
    assert patched["laika_intent"] == "analyze"
    assert patched["tree"]["nodes"][assistant_id]["content"] == "คำตอบจาก LAIKA"

    listed = client.get("/studio/collections", headers=auth_headers).json()["items"]
    assert len(listed) == 1
    assert listed[0]["has_laika"] is True


def test_get_conversation_and_select_branch(client, auth_headers):
    create = client.post(
        "/studio/collections",
        headers=auth_headers,
        json={"type": "note", "content": "root question"},
    )
    entry = create.json()
    collection_id = entry["id"]
    root_id = entry["tree"]["rootIds"][0]

    conv = client.get(f"/studio/collections/{collection_id}/conversation", headers=auth_headers)
    assert conv.status_code == 200
    body = conv.json()
    assert body["collection_id"] == collection_id
    assert len(body["messages"]) == 1
    assert body["messages"][0]["role"] == "user"
    assert body["at_user_node_id"] == root_id

    branch_map = client.get(
        f"/studio/collections/{collection_id}/branch-map",
        headers=auth_headers,
    )
    assert branch_map.status_code == 200
    assert len(branch_map.json()["user_nodes"]) == 1

    select_resp = client.post(
        f"/studio/collections/{collection_id}/select-branch",
        headers=auth_headers,
        json={"user_node_id": root_id},
    )
    assert select_resp.status_code == 200
    assert select_resp.json()["at_user_node_id"] == root_id


def test_collection_isolation_between_users(client):
    user_a = client.post(
        "/auth/register",
        json={"email": "studio-a@lunar.dev", "password": "testpass123"},
    )
    user_b = client.post(
        "/auth/register",
        json={"email": "studio-b@lunar.dev", "password": "testpass123"},
    )
    headers_a = {"Authorization": f"Bearer {user_a.json()['access_token']}"}
    headers_b = {"Authorization": f"Bearer {user_b.json()['access_token']}"}

    created = client.post(
        "/studio/collections",
        headers=headers_a,
        json={"type": "note", "content": "ของ user A"},
    )
    collection_id = created.json()["id"]

    assert client.get(f"/studio/collections/{collection_id}", headers=headers_b).status_code == 404
    assert client.patch(
        f"/studio/collections/{collection_id}",
        headers=headers_b,
        json={
            "title": "hack",
            "content": "hack",
            "tree": created.json()["tree"],
        },
    ).status_code == 404


def test_delete_collection(client, auth_headers):
    created = client.post(
        "/studio/collections",
        headers=auth_headers,
        json={"type": "note", "content": "ลบทิ้ง"},
    )
    collection_id = created.json()["id"]

    delete = client.delete(f"/studio/collections/{collection_id}", headers=auth_headers)
    assert delete.status_code == 204
    assert client.get(f"/studio/collections/{collection_id}", headers=auth_headers).status_code == 404
