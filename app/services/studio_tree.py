"""Conversation tree helpers — mirrors frontend/src/lib/studio-tree.ts."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

ROOT_PARENT_KEY = "__root__"

Role = Literal["user", "assistant"]


def _nodes(tree: dict[str, Any]) -> dict[str, Any]:
    raw = tree.get("nodes")
    return raw if isinstance(raw, dict) else {}


def _selected(tree: dict[str, Any]) -> dict[str, str]:
    raw = tree.get("selectedChildByParent")
    return dict(raw) if isinstance(raw, dict) else {}


def _root_ids(tree: dict[str, Any]) -> list[str]:
    raw = tree.get("rootIds")
    return list(raw) if isinstance(raw, list) else []


def get_node(tree: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    node = _nodes(tree).get(node_id)
    return node if isinstance(node, dict) else None


def parent_key(parent_id: str | None) -> str:
    return parent_id if parent_id else ROOT_PARENT_KEY


def get_children(tree: dict[str, Any], parent_id: str) -> list[dict[str, Any]]:
    children = [
        n for n in _nodes(tree).values() if isinstance(n, dict) and n.get("parentId") == parent_id
    ]
    children.sort(key=lambda n: str(n.get("createdAt", "")))
    return children


def get_user_siblings(tree: dict[str, Any], node_id: str) -> list[dict[str, Any]]:
    node = get_node(tree, node_id)
    if not node or node.get("role") != "user":
        return []
    if node.get("parentId") is None:
        roots = [
            get_node(tree, rid)
            for rid in _root_ids(tree)
            if get_node(tree, rid) and get_node(tree, rid).get("role") == "user"
        ]
        roots = [n for n in roots if n]
        roots.sort(key=lambda n: str(n.get("createdAt", "")))
        return roots
    return [n for n in get_children(tree, node["parentId"]) if n.get("role") == "user"]


def can_create_branch_from_user_node(tree: dict[str, Any], node_id: str) -> bool:
    node = get_node(tree, node_id)
    if not node or node.get("role") != "user":
        return False
    return node.get("parentId") is not None


def prune_invalid_selections(tree: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(tree)
    selected = _selected(result)
    for parent_id, child_id in list(selected.items()):
        child = get_node(result, child_id)
        valid_parent = None if parent_id == ROOT_PARENT_KEY else parent_id
        if not child or child.get("parentId") != valid_parent:
            del selected[parent_id]
    result["selectedChildByParent"] = selected
    return result


def build_active_path(tree: dict[str, Any]) -> list[dict[str, Any]]:
    path: list[dict[str, Any]] = []
    selected = _selected(tree)
    root_ids = _root_ids(tree)
    root_id = (
        selected.get(ROOT_PARENT_KEY)
        or next(
            (rid for rid in root_ids if get_node(tree, rid) and get_node(tree, rid).get("role") == "user"),
            None,
        )
        or (root_ids[0] if root_ids else None)
    )
    if not root_id:
        return path

    current = get_node(tree, root_id)
    while current:
        path.append(current)
        next_id = selected.get(current["id"])
        if next_id:
            current = get_node(tree, next_id)
            continue
        children = get_children(tree, current["id"])
        current = children[0] if children else None
    return path


def get_active_user_path(tree: dict[str, Any]) -> list[dict[str, Any]]:
    return [n for n in build_active_path(tree) if n.get("role") == "user"]


def select_path_to_node(tree: dict[str, Any], target_node_id: str) -> dict[str, Any]:
    target = get_node(tree, target_node_id)
    if not target or target.get("role") != "user":
        return tree

    chain: list[dict[str, Any]] = []
    current: dict[str, Any] | None = target
    while current:
        chain.insert(0, current)
        parent_id = current.get("parentId")
        current = get_node(tree, parent_id) if parent_id else None
        if current and current.get("role") == "assistant" and current.get("parentId"):
            current = get_node(tree, current["parentId"])
        elif current and current.get("role") == "assistant":
            break

    selected = {**_selected(tree)}
    for i in range(len(chain) - 1):
        user_node = chain[i]
        next_user = chain[i + 1]
        assistants = [n for n in get_children(tree, user_node["id"]) if n.get("role") == "assistant"]
        for assistant in assistants:
            user_child = next(
                (n for n in get_children(tree, assistant["id"]) if n.get("id") == next_user["id"]),
                None,
            )
            if user_child:
                selected[user_node["id"]] = assistant["id"]
                selected[assistant["id"]] = next_user["id"]
                break

    root_user = chain[0] if chain else None
    if root_user:
        selected[ROOT_PARENT_KEY] = root_user["id"]

    return prune_invalid_selections({**tree, "selectedChildByParent": selected})


def build_user_branch_graph(tree: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    user_nodes = sorted(
        [n for n in _nodes(tree).values() if isinstance(n, dict) and n.get("role") == "user"],
        key=lambda n: str(n.get("createdAt", "")),
    )
    edges: list[dict[str, str]] = []
    for user in user_nodes:
        assistants = [n for n in get_children(tree, user["id"]) if n.get("role") == "assistant"]
        for assistant in assistants:
            for next_user in get_children(tree, assistant["id"]):
                if next_user.get("role") == "user":
                    edges.append({"from": user["id"], "to": next_user["id"]})
    return user_nodes, edges


def _preview_label(content: str, max_len: int = 60) -> str:
    line = content.split("\n", 1)[0].strip()
    if len(line) <= max_len:
        return line or "…"
    return f"{line[: max_len - 1]}…"


def node_to_message(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": node["id"],
        "role": node.get("role"),
        "content": node.get("content", ""),
        "created_at": node.get("createdAt", ""),
        "updated_at": node.get("updatedAt", ""),
        "parent_id": node.get("parentId"),
        "laika_intent": node.get("laikaIntent"),
    }


def build_conversation_payload(
    tree: dict[str, Any],
    *,
    at_user_node_id: str | None = None,
) -> dict[str, Any]:
    working = tree
    if at_user_node_id:
        working = select_path_to_node(tree, at_user_node_id)

    path = build_active_path(working)
    user_path = [n for n in path if n.get("role") == "user"]
    at_id = user_path[-1]["id"] if user_path else (path[0]["id"] if path else "")

    user_spots = []
    for node in user_path:
        siblings = get_user_siblings(working, node["id"])
        sibling_ids = [s["id"] for s in siblings]
        idx = sibling_ids.index(node["id"]) if node["id"] in sibling_ids else 0
        user_spots.append(
            {
                "user_node_id": node["id"],
                "sibling_index": idx,
                "sibling_count": len(siblings),
                "sibling_ids": sibling_ids,
                "can_create_branch": can_create_branch_from_user_node(working, node["id"]),
            }
        )

    has_laika = any(
        n.get("role") == "assistant" and str(n.get("content", "")).strip()
        for n in _nodes(working).values()
        if isinstance(n, dict)
    )

    return {
        "at_user_node_id": at_id,
        "messages": [node_to_message(n) for n in path],
        "user_spots": user_spots,
        "has_laika": has_laika,
        "active_user_node_ids": [n["id"] for n in user_path],
    }


def build_branch_map_payload(tree: dict[str, Any]) -> dict[str, Any]:
    user_nodes, edges = build_user_branch_graph(tree)
    active_ids = [n["id"] for n in get_active_user_path(tree)]
    active_edge_keys = set()
    for i in range(len(active_ids) - 1):
        active_edge_keys.add(f"{active_ids[i]}->{active_ids[i + 1]}")

    return {
        "user_nodes": [
            {
                "id": n["id"],
                "label": _preview_label(str(n.get("content", ""))),
                "created_at": n.get("createdAt", ""),
                "updated_at": n.get("updatedAt", ""),
            }
            for n in user_nodes
        ],
        "edges": edges,
        "active_user_node_ids": active_ids,
        "active_edge_keys": sorted(active_edge_keys),
    }


# ── Helpers for node manipulation ──────────────────────────────────────────

def _new_id() -> str:
    import uuid
    return str(uuid.uuid4())


def _now_iso() -> str:
    from datetime import UTC, datetime
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def create_node(
    role: Role,
    content: str,
    *,
    parent_id: str | None = None,
    laika_intent: str | None = None,
    node_id: str | None = None,
) -> dict[str, Any]:
    now = _now_iso()
    return {
        "id": node_id or _new_id(),
        "role": role,
        "content": content,
        "createdAt": now,
        "updatedAt": now,
        "parentId": parent_id,
        "laikaIntent": laika_intent,
    }


def add_node(tree: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    nodes = {**tree.get("nodes", {}), node["id"]: node}
    root_ids = list(tree.get("rootIds", []))
    if not node.get("parentId") and node.get("role") == "user" and node["id"] not in root_ids:
        root_ids.append(node["id"])
    selected = dict(tree.get("selectedChildByParent", {}))
    parent_id = node.get("parentId")
    if parent_id:
        selected[parent_id] = node["id"]
    elif node.get("role") == "user":
        selected[ROOT_PARENT_KEY] = node["id"]
    return {**tree, "nodes": nodes, "rootIds": root_ids, "selectedChildByParent": selected}


def update_node(tree: dict[str, Any], node_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    existing = get_node(tree, node_id)
    if not existing:
        return tree
    merged = {**existing, **patch, "updatedAt": _now_iso()}
    nodes = {**tree.get("nodes", {}), node_id: merged}
    return {**tree, "nodes": nodes}


def select_sibling(tree: dict[str, Any], parent_id: str | None, sibling_id: str) -> dict[str, Any]:
    siblings = get_children(tree, parent_id) if parent_id else get_user_siblings(tree, sibling_id)
    if not any(s.get("id") == sibling_id for s in siblings):
        return tree
    key = parent_key(parent_id)
    selected = {**tree.get("selectedChildByParent", {})}
    selected[key] = sibling_id
    result = {**tree, "selectedChildByParent": selected}
    if not parent_id:
        root_ids = list(tree.get("rootIds", []))
        result["rootIds"] = [sibling_id] + [rid for rid in root_ids if rid != sibling_id]
    return prune_invalid_selections(result)


def find_assistant_child(tree: dict[str, Any], parent_id: str) -> dict[str, Any] | None:
    return next(
        (n for n in get_children(tree, parent_id) if n.get("role") == "assistant"),
        None,
    )


def get_active_leaf(tree: dict[str, Any]) -> dict[str, Any] | None:
    """Return the last node in the active path."""
    path = build_active_path(tree)
    return path[-1] if path else None


def messages_from_tree(tree: dict[str, Any]) -> list[dict[str, Any]]:
    """Build ChatMessage-like history from the active path (excluding leaf if it's empty user)."""
    path = build_active_path(tree)
    result = []
    for node in path:
        content = str(node.get("content", "")).strip()
        if not content:
            continue
        result.append({
            "role": node["role"],
            "content": content,
            "created_at": node.get("createdAt"),
        })
    return result


def prepare_tree_for_stream(
    tree: dict[str, Any],
    mode: str,
    content: str,
    intent: str,
    *,
    node_id: str | None = None,
    parent_node_id: str | None = None,
) -> tuple[dict[str, Any], str, str]:
    """
    Modify tree according to mode, returning (new_tree, user_node_id, assistant_node_id).

    Modes:
    - new / follow_up: create user + assistant node pair
    - edit: update existing user node + clear its assistant child
    - retry: clear existing assistant node
    - branch: create sibling user + assistant under same parent
    """
    if mode in ("new", "follow_up"):
        user = create_node(role="user", content=content, parent_id=parent_node_id)
        tree = add_node(tree, user)
        assistant = create_node(role="assistant", content="", parent_id=user["id"], laika_intent=intent)
        tree = add_node(tree, assistant)
        return tree, user["id"], assistant["id"]

    if mode == "edit":
        if not node_id:
            raise ValueError("edit mode requires node_id")
        tree = update_node(tree, node_id, {"content": content})
        existing = find_assistant_child(tree, node_id)
        if existing:
            tree = update_node(tree, existing["id"], {"content": ""})
            return tree, node_id, existing["id"]
        # no assistant child yet — create one
        assistant = create_node(role="assistant", content="", parent_id=node_id, laika_intent=intent)
        tree = add_node(tree, assistant)
        return tree, node_id, assistant["id"]

    if mode == "retry":
        if not node_id:
            raise ValueError("retry mode requires node_id")
        tree = update_node(tree, node_id, {"content": ""})
        parent = get_node(tree, tree.get("nodes", {}).get(node_id, {}).get("parentId", ""))
        parent_id = parent["id"] if parent else ""
        return tree, parent_id, node_id

    if mode == "branch":
        if not node_id or not parent_node_id:
            raise ValueError("branch mode requires node_id and parent_node_id")
        sibling = create_node(role="user", content=content, parent_id=parent_node_id)
        tree = add_node(tree, sibling)
        tree = select_sibling(tree, parent_node_id, sibling["id"])
        assistant = create_node(role="assistant", content="", parent_id=sibling["id"], laika_intent=intent)
        tree = add_node(tree, assistant)
        return tree, sibling["id"], assistant["id"]

    raise ValueError(f"Unknown mode: {mode}")
