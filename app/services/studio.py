import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.studio_collection import StudioCollection
from app.models.user import User
from app.schemas.studio import (
    BranchMapResponse,
    CollectionEntry,
    CollectionSummary,
    ConversationResponse,
    CreateCollectionRequest,
    SelectBranchRequest,
    UpdateCollectionRequest,
)
from app.services import studio_tree


def derive_title(content: str) -> str:
    line = content.split("\n")[0].strip()
    if not line:
        return "ไม่มีชื่อ"
    if len(line) > 60:
        return f"{line[:57]}…"
    return line


def empty_tree(content: str, created_at: datetime) -> dict[str, Any]:
    # tree ว่าง — ไม่มี root user node แล้ว
    # content ไม่จำเป็น เก็บเฉพาะ metadata ของ collection
    return {
        "nodes": {},
        "rootIds": [],
        "selectedChildByParent": {},
    }


def tree_has_laika(tree: dict[str, Any]) -> bool:
    nodes = tree.get("nodes")
    if not isinstance(nodes, dict):
        return False
    for node in nodes.values():
        if not isinstance(node, dict):
            continue
        if node.get("role") == "assistant" and str(node.get("content", "")).strip():
            return True
    return False


def _to_summary(row: StudioCollection) -> CollectionSummary:
    return CollectionSummary(
        id=row.id,
        type=row.type,  # type: ignore[arg-type]
        title=row.title,
        content=row.content,
        created_at=row.created_at,
        updated_at=row.updated_at,
        has_laika=tree_has_laika(row.tree),
    )


def _to_entry(row: StudioCollection) -> CollectionEntry:
    return CollectionEntry(
        id=row.id,
        type=row.type,  # type: ignore[arg-type]
        title=row.title,
        content=row.content,
        created_at=row.created_at,
        updated_at=row.updated_at,
        tree=row.tree,
        laika_intent=row.laika_intent,
    )


def list_collections(db: Session, user: User) -> list[CollectionSummary]:
    rows = db.scalars(
        select(StudioCollection)
        .where(StudioCollection.user_id == user.id)
        .order_by(StudioCollection.updated_at.desc())
    ).all()
    return [_to_summary(row) for row in rows]


def get_collection(db: Session, user: User, collection_id: uuid.UUID) -> StudioCollection | None:
    return db.scalar(
        select(StudioCollection).where(
            StudioCollection.id == collection_id,
            StudioCollection.user_id == user.id,
        )
    )


def get_collection_entry(
    db: Session, user: User, collection_id: uuid.UUID
) -> CollectionEntry | None:
    row = get_collection(db, user, collection_id)
    if not row:
        return None
    return _to_entry(row)


def create_collection(
    db: Session, user: User, payload: CreateCollectionRequest
) -> CollectionEntry:
    now = datetime.now(UTC)
    row = StudioCollection(
        user_id=user.id,
        type=payload.type,
        title=derive_title(payload.content),
        content=payload.content,
        tree=empty_tree(payload.content, now),
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_entry(row)


def update_collection(
    db: Session,
    user: User,
    collection_id: uuid.UUID,
    payload: UpdateCollectionRequest,
) -> CollectionEntry | None:
    row = get_collection(db, user, collection_id)
    if not row:
        return None

    row.title = payload.title
    row.content = payload.content
    row.tree = payload.tree
    row.laika_intent = payload.laika_intent
    row.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    return _to_entry(row)


def delete_collection(db: Session, user: User, collection_id: uuid.UUID) -> bool:
    row = get_collection(db, user, collection_id)
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def _conversation_from_row(
    row: StudioCollection,
    *,
    at_user_node_id: str | None = None,
) -> ConversationResponse:
    payload = studio_tree.build_conversation_payload(row.tree, at_user_node_id=at_user_node_id)
    return ConversationResponse(
        collection_id=row.id,
        type=row.type,  # type: ignore[arg-type]
        title=row.title,
        content=row.content,
        laika_intent=row.laika_intent,
        created_at=row.created_at,
        updated_at=row.updated_at,
        at_user_node_id=payload["at_user_node_id"],
        messages=payload["messages"],  # type: ignore[arg-type]
        user_spots=payload["user_spots"],  # type: ignore[arg-type]
        has_laika=payload["has_laika"],
    )


def get_conversation(
    db: Session,
    user: User,
    collection_id: uuid.UUID,
    at_user_node_id: str | None = None,
) -> ConversationResponse | None:
    row = get_collection(db, user, collection_id)
    if not row:
        return None
    if at_user_node_id:
        target = studio_tree.get_node(row.tree, at_user_node_id)
        if not target or target.get("role") != "user":
            return None
    return _conversation_from_row(row, at_user_node_id=at_user_node_id)


def select_branch(
    db: Session,
    user: User,
    collection_id: uuid.UUID,
    payload: SelectBranchRequest,
) -> ConversationResponse | None:
    row = get_collection(db, user, collection_id)
    if not row:
        return None
    target = studio_tree.get_node(row.tree, payload.user_node_id)
    if not target or target.get("role") != "user":
        return None

    row.tree = studio_tree.select_path_to_node(row.tree, payload.user_node_id)
    row.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    return _conversation_from_row(row)


def get_branch_map(
    db: Session,
    user: User,
    collection_id: uuid.UUID,
) -> BranchMapResponse | None:
    row = get_collection(db, user, collection_id)
    if not row:
        return None
    payload = studio_tree.build_branch_map_payload(row.tree)
    return BranchMapResponse(
        collection_id=row.id,
        user_nodes=payload["user_nodes"],  # type: ignore[arg-type]
        edges=[{"from_id": e["from"], "to_id": e["to"]} for e in payload["edges"]],
        active_user_node_ids=payload["active_user_node_ids"],
        active_edge_keys=payload["active_edge_keys"],
    )
