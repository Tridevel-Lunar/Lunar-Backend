from __future__ import annotations

import mimetypes
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_source import KnowledgeSource
from app.services.knowledge.manifest import load_manifest, resolve_manifest_path
from app.services.rag.providers import get_embeddings

ALLOWED_EXTENSIONS = {".md", ".markdown", ".txt", ".pdf"}


@dataclass(frozen=True)
class IngestSourceResult:
    source_id: str
    chunks_ingested: int


@dataclass(frozen=True)
class IngestRunResult:
    total_chunks: int
    results: list[IngestSourceResult]


@dataclass(frozen=True)
class KnowledgeSourceOverview:
    id: str
    manifest_id: str | None
    title: str
    filename: str
    type: str
    module: str | None
    stage: str | None
    source_origin: str
    language: str
    topic: str | None
    license: str | None
    chunk_count: int
    last_ingested_at: datetime | None
    created_at: datetime


@dataclass(frozen=True)
class KnowledgeOverview:
    total_chunks: int
    embedding_provider: str
    embedding_enabled: bool
    sources: list[KnowledgeSourceOverview]


@dataclass(frozen=True)
class KnowledgeCatalogItem:
    manifest_id: str
    title: str
    module: str
    stage: str | None
    order: int | None
    path: str
    type: str
    language: str
    topic: str | None
    synced: bool
    id: str | None
    filename: str | None
    chunk_count: int
    last_ingested_at: datetime | None
    created_at: datetime | None


@dataclass(frozen=True)
class KnowledgeModuleGroup:
    module: str
    sources: list[KnowledgeCatalogItem]


@dataclass(frozen=True)
class KnowledgeCatalog:
    total_chunks: int
    embedding_provider: str
    embedding_enabled: bool
    modules: list[KnowledgeModuleGroup]
    uploads: list[KnowledgeSourceOverview]


@dataclass(frozen=True)
class KnowledgeSourceDetail:
    id: str
    manifest_id: str | None
    title: str
    filename: str
    type: str
    module: str | None
    stage: str | None
    source_origin: str
    language: str
    topic: str | None
    license: str | None
    content: str | None
    content_editable: bool
    chunk_count: int
    last_ingested_at: datetime | None


@dataclass(frozen=True)
class UpdateKnowledgeSourceResult:
    id: str
    title: str
    chunks_ingested: int


@dataclass(frozen=True)
class UploadKnowledgeResult:
    source_id: str
    title: str
    filename: str
    source_type: str
    chunks_ingested: int


def detect_source_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".md", ".markdown"}:
        return "markdown"
    if suffix == ".txt":
        return "text"
    raise ValueError(f"Unsupported file type: {suffix or '(none)'}")


def guess_mime_type(filename: str, source_type: str) -> str:
    guessed, _ = mimetypes.guess_type(filename)
    if guessed:
        return guessed
    if source_type == "pdf":
        return "application/pdf"
    return "text/plain"


def load_documents_from_source(source: KnowledgeSource) -> list[Document]:
    if source.source_type == "pdf":
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
            tmp.write(source.file_data)
            tmp.flush()
            loader = PyPDFLoader(tmp.name)
            docs = loader.load()
            for i, doc in enumerate(docs):
                doc.metadata["page"] = doc.metadata.get("page", i)
            return docs

    text = source.file_data.decode("utf-8")
    return [Document(page_content=text)]


def chunk_documents(docs: list[Document], source: KnowledgeSource) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    chunks = splitter.split_documents(docs)
    for chunk in chunks:
        chunk.metadata.setdefault("source_id", str(source.id))
        chunk.metadata.setdefault("source_title", source.title)
        chunk.metadata.setdefault("topic", source.topic)
        chunk.metadata.setdefault("language", source.language)
    return chunks


def embed_batch(embeddings, texts: list[str], batch_size: int = 32) -> list[list[float]]:
    vectors: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        vectors.extend(embeddings.embed_documents(batch))
    return vectors


def ingest_source_record(
    db: Session,
    source: KnowledgeSource,
    embeddings,
    provider_label: str,
) -> int:
    docs = load_documents_from_source(source)
    chunks = chunk_documents(docs, source)
    if not chunks:
        return 0

    texts = [c.page_content for c in chunks]
    vectors = embed_batch(embeddings, texts)
    source_id = str(source.id)

    db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.source_id == source_id))
    now = datetime.now(timezone.utc)
    for chunk_doc, vector in zip(chunks, vectors):
        page = chunk_doc.metadata.get("page")
        if page is not None and not isinstance(page, int):
            try:
                page = int(page)
            except (TypeError, ValueError):
                page = None
        db.add(
            KnowledgeChunk(
                id=uuid.uuid4(),
                content=chunk_doc.page_content,
                embedding=vector,
                embedding_provider=provider_label,
                source_id=source_id,
                source_title=source.title,
                page=page,
                topic=chunk_doc.metadata.get("topic"),
                language=str(chunk_doc.metadata.get("language", source.language)),
                created_at=now,
            )
        )
    db.commit()
    return len(chunks)


def create_knowledge_source(
    db: Session,
    *,
    filename: str,
    file_data: bytes,
    title: str | None,
    topic: str | None,
    language: str,
    license_value: str | None,
    uploaded_by: uuid.UUID | None,
) -> KnowledgeSource:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise ValueError(f"Unsupported file type. Allowed: {allowed}")

    source_type = detect_source_type(filename)
    record = KnowledgeSource(
        id=uuid.uuid4(),
        title=(title or Path(filename).stem).strip() or filename,
        filename=filename,
        source_type=source_type,
        language=language or "th",
        topic=topic,
        license=license_value,
        mime_type=guess_mime_type(filename, source_type),
        file_data=file_data,
        source_origin="upload",
        uploaded_by=uploaded_by,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def upload_and_ingest(
    db: Session,
    settings: Settings,
    *,
    filename: str,
    file_data: bytes,
    title: str | None,
    topic: str | None,
    language: str,
    license_value: str | None,
    uploaded_by: uuid.UUID | None,
    auto_ingest: bool = True,
) -> UploadKnowledgeResult:
    if len(file_data) > settings.knowledge_max_upload_bytes:
        max_mb = settings.knowledge_max_upload_bytes // (1024 * 1024)
        raise ValueError(f"File too large — maximum size is {max_mb} MB")

    source = create_knowledge_source(
        db,
        filename=filename,
        file_data=file_data,
        title=title,
        topic=topic,
        language=language,
        license_value=license_value,
        uploaded_by=uploaded_by,
    )

    chunks_ingested = 0
    if auto_ingest:
        if not settings.laika_embedding_enabled:
            raise ValueError(
                "Embedding provider not configured — set GEMINI_API_KEY or OLLAMA_BASE_URL"
            )
        embeddings = get_embeddings(settings)
        provider_label = settings.active_embedding_provider_label
        chunks_ingested = ingest_source_record(db, source, embeddings, provider_label)

    return UploadKnowledgeResult(
        source_id=str(source.id),
        title=source.title,
        filename=source.filename,
        source_type=source.source_type,
        chunks_ingested=chunks_ingested,
    )


def delete_knowledge_source(db: Session, source_id: str) -> None:
    source = _get_source_by_id_or_manifest(db, source_id)
    if source is None:
        raise ValueError(f"Unknown source id: {source_id}")

    db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.source_id == str(source.id)))
    db.delete(source)
    db.commit()


def _chunk_stats(db: Session) -> dict[str, tuple[int, datetime | None]]:
    rows = db.execute(
        select(
            KnowledgeChunk.source_id,
            func.count(KnowledgeChunk.id),
            func.max(KnowledgeChunk.created_at),
        ).group_by(KnowledgeChunk.source_id)
    ).all()
    return {source_id: (count, last_ingested_at) for source_id, count, last_ingested_at in rows}


def get_knowledge_overview(db: Session, settings: Settings) -> KnowledgeOverview:
    stats = _chunk_stats(db)
    total_chunks = sum(count for count, _ in stats.values())

    db_sources = db.scalars(
        select(KnowledgeSource).order_by(KnowledgeSource.created_at.desc())
    ).all()

    sources: list[KnowledgeSourceOverview] = []
    for source in db_sources:
        source_id = str(source.id)
        chunk_count, last_ingested_at = stats.get(source_id, (0, None))
        sources.append(
            KnowledgeSourceOverview(
                id=source_id,
                manifest_id=source.manifest_id,
                title=source.title,
                filename=source.filename,
                type=source.source_type,
                module=source.module,
                stage=source.stage,
                source_origin=source.source_origin,
                language=source.language,
                topic=source.topic,
                license=source.license,
                chunk_count=chunk_count,
                last_ingested_at=last_ingested_at,
                created_at=source.created_at,
            )
        )

    return KnowledgeOverview(
        total_chunks=total_chunks,
        embedding_provider=settings.active_embedding_provider_label,
        embedding_enabled=settings.laika_embedding_enabled,
        sources=sources,
    )


def ingest_knowledge(db: Session, settings: Settings, source_id: str = "all") -> IngestRunResult:
    if not settings.laika_embedding_enabled:
        raise ValueError(
            "Embedding provider not configured — set GEMINI_API_KEY or OLLAMA_BASE_URL"
        )

    embeddings = get_embeddings(settings)
    provider_label = settings.active_embedding_provider_label

    if source_id == "all":
        sources = db.scalars(select(KnowledgeSource)).all()
    else:
        source = _get_source_by_id_or_manifest(db, source_id)
        if source is None:
            raise ValueError(f"Unknown source id: {source_id}")
        sources = [source]

    results: list[IngestSourceResult] = []
    total = 0
    for source in sources:
        count = ingest_source_record(db, source, embeddings, provider_label)
        results.append(
            IngestSourceResult(
                source_id=source.manifest_id or str(source.id),
                chunks_ingested=count,
            )
        )
        total += count

    return IngestRunResult(total_chunks=total, results=results)


def _get_source_by_id_or_manifest(db: Session, source_id: str) -> KnowledgeSource | None:
    try:
        parsed = uuid.UUID(source_id)
    except ValueError:
        parsed = None
    if parsed is not None:
        source = db.get(KnowledgeSource, parsed)
        if source is not None:
            return source
    return db.scalar(select(KnowledgeSource).where(KnowledgeSource.manifest_id == source_id))


def _upsert_manifest_source(db: Session, entry: dict) -> KnowledgeSource:
    file_path = resolve_manifest_path(entry["path"])
    file_data = file_path.read_bytes()
    filename = file_path.name
    source_type = entry.get("type", detect_source_type(filename))
    now = datetime.now(timezone.utc)

    existing = db.scalar(
        select(KnowledgeSource).where(KnowledgeSource.manifest_id == entry["id"])
    )
    if existing:
        existing.title = entry["title"]
        existing.filename = filename
        existing.source_type = source_type
        existing.language = entry.get("language", "th")
        existing.topic = entry.get("topic")
        existing.license = entry.get("license")
        existing.mime_type = guess_mime_type(filename, source_type)
        existing.file_data = file_data
        existing.module = entry.get("module")
        existing.stage = entry.get("stage")
        existing.source_origin = "manifest"
        existing.updated_at = now
        db.commit()
        db.refresh(existing)
        return existing

    record = KnowledgeSource(
        id=uuid.uuid4(),
        manifest_id=entry["id"],
        title=entry["title"],
        filename=filename,
        source_type=source_type,
        language=entry.get("language", "th"),
        topic=entry.get("topic"),
        license=entry.get("license"),
        mime_type=guess_mime_type(filename, source_type),
        file_data=file_data,
        module=entry.get("module"),
        stage=entry.get("stage"),
        source_origin="manifest",
        uploaded_by=None,
        created_at=now,
        updated_at=now,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def sync_manifest_sources(
    db: Session,
    settings: Settings,
    source_id: str = "all",
    auto_ingest: bool = True,
) -> IngestRunResult:
    entries = load_manifest()
    if source_id != "all":
        entries = [e for e in entries if e["id"] == source_id]
        if not entries:
            raise ValueError(f"Unknown manifest source id: {source_id}")

    if auto_ingest and not settings.laika_embedding_enabled:
        raise ValueError(
            "Embedding provider not configured — set GEMINI_API_KEY or OLLAMA_BASE_URL"
        )

    embeddings = get_embeddings(settings) if auto_ingest else None
    provider_label = settings.active_embedding_provider_label

    results: list[IngestSourceResult] = []
    total = 0
    for entry in entries:
        record = _upsert_manifest_source(db, entry)
        chunks_ingested = 0
        if auto_ingest and embeddings is not None:
            chunks_ingested = ingest_source_record(db, record, embeddings, provider_label)
        results.append(
            IngestSourceResult(source_id=entry["id"], chunks_ingested=chunks_ingested)
        )
        total += chunks_ingested

    return IngestRunResult(total_chunks=total, results=results)


MODULE_ORDER = ("space", "arena", "studio")


def get_knowledge_catalog(db: Session, settings: Settings) -> KnowledgeCatalog:
    stats = _chunk_stats(db)
    total_chunks = sum(count for count, _ in stats.values())

    db_sources = db.scalars(select(KnowledgeSource)).all()
    by_manifest: dict[str, KnowledgeSource] = {
        s.manifest_id: s for s in db_sources if s.manifest_id
    }
    uploads: list[KnowledgeSourceOverview] = []
    for source in db_sources:
        if source.source_origin != "manifest":
            source_id = str(source.id)
            chunk_count, last_ingested_at = stats.get(source_id, (0, None))
            uploads.append(
                KnowledgeSourceOverview(
                    id=source_id,
                    manifest_id=source.manifest_id,
                    title=source.title,
                    filename=source.filename,
                    type=source.source_type,
                    module=source.module,
                    stage=source.stage,
                    source_origin=source.source_origin,
                    language=source.language,
                    topic=source.topic,
                    license=source.license,
                    chunk_count=chunk_count,
                    last_ingested_at=last_ingested_at,
                    created_at=source.created_at,
                )
            )

    uploads.sort(key=lambda s: s.created_at, reverse=True)

    grouped: dict[str, list[KnowledgeCatalogItem]] = {m: [] for m in MODULE_ORDER}
    for entry in load_manifest():
        module = entry["module"]
        existing = by_manifest.get(entry["id"])
        if existing:
            source_id = str(existing.id)
            chunk_count, last_ingested_at = stats.get(source_id, (0, None))
            item = KnowledgeCatalogItem(
                manifest_id=entry["id"],
                title=existing.title,
                module=module,
                stage=entry.get("stage"),
                order=entry.get("order"),
                path=entry["path"],
                type=entry.get("type", existing.source_type),
                language=existing.language,
                topic=existing.topic,
                synced=True,
                id=source_id,
                filename=existing.filename,
                chunk_count=chunk_count,
                last_ingested_at=last_ingested_at,
                created_at=existing.created_at,
            )
        else:
            item = KnowledgeCatalogItem(
                manifest_id=entry["id"],
                title=entry["title"],
                module=module,
                stage=entry.get("stage"),
                order=entry.get("order"),
                path=entry["path"],
                type=entry.get("type", "markdown"),
                language=entry.get("language", "th"),
                topic=entry.get("topic"),
                synced=False,
                id=None,
                filename=Path(entry["path"]).name,
                chunk_count=0,
                last_ingested_at=None,
                created_at=None,
            )
        grouped.setdefault(module, []).append(item)

    modules: list[KnowledgeModuleGroup] = []
    for module in MODULE_ORDER:
        sources = grouped.get(module, [])
        sources.sort(key=lambda s: (s.stage or "", s.order if s.order is not None else 999, s.title))
        modules.append(KnowledgeModuleGroup(module=module, sources=sources))

    return KnowledgeCatalog(
        total_chunks=total_chunks,
        embedding_provider=settings.active_embedding_provider_label,
        embedding_enabled=settings.laika_embedding_enabled,
        modules=modules,
        uploads=uploads,
    )


def get_knowledge_source_detail(db: Session, source_id: str) -> KnowledgeSourceDetail:
    source = _get_source_by_id_or_manifest(db, source_id)
    if source is None:
        raise ValueError(f"Unknown source id: {source_id}")

    stats = _chunk_stats(db)
    source_id_str = str(source.id)
    chunk_count, last_ingested_at = stats.get(source_id_str, (0, None))

    content_editable = source.source_type in {"markdown", "text"}
    content: str | None = None
    if content_editable:
        content = source.file_data.decode("utf-8")

    return KnowledgeSourceDetail(
        id=source_id_str,
        manifest_id=source.manifest_id,
        title=source.title,
        filename=source.filename,
        type=source.source_type,
        module=source.module,
        stage=source.stage,
        source_origin=source.source_origin,
        language=source.language,
        topic=source.topic,
        license=source.license,
        content=content,
        content_editable=content_editable,
        chunk_count=chunk_count,
        last_ingested_at=last_ingested_at,
    )


def update_knowledge_source(
    db: Session,
    settings: Settings,
    source_id: str,
    *,
    title: str | None = None,
    topic: str | None = None,
    language: str | None = None,
    license_value: str | None = None,
    content: str | None = None,
    auto_reingest: bool = True,
) -> UpdateKnowledgeSourceResult:
    source = _get_source_by_id_or_manifest(db, source_id)
    if source is None:
        raise ValueError(f"Unknown source id: {source_id}")

    if content is not None and source.source_type not in {"markdown", "text"}:
        raise ValueError("Content can only be edited for markdown or text sources")

    if title is not None:
        source.title = title.strip() or source.title
    if topic is not None:
        source.topic = topic.strip() or None
    if language is not None:
        source.language = language.strip() or source.language
    if license_value is not None:
        source.license = license_value.strip() or None
    if content is not None:
        source.file_data = content.encode("utf-8")

    source.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(source)

    chunks_ingested = 0
    if auto_reingest:
        if not settings.laika_embedding_enabled:
            raise ValueError(
                "Embedding provider not configured — set GEMINI_API_KEY or OLLAMA_BASE_URL"
            )
        embeddings = get_embeddings(settings)
        provider_label = settings.active_embedding_provider_label
        chunks_ingested = ingest_source_record(db, source, embeddings, provider_label)

    return UpdateKnowledgeSourceResult(
        id=str(source.id),
        title=source.title,
        chunks_ingested=chunks_ingested,
    )
