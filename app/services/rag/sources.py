from app.models.knowledge_chunk import KnowledgeChunk
from app.schemas.laika import LaikaSource
from app.services.rag.prompts import RetrievedChunk


def build_sources(chunks: list[RetrievedChunk]) -> list[LaikaSource]:
    seen: set[tuple[str, int | None]] = set()
    sources: list[LaikaSource] = []
    for chunk in chunks:
        key = (chunk.source_id, chunk.page)
        if key in seen:
            continue
        seen.add(key)
        snippet = chunk.content[:200]
        if len(chunk.content) > 200:
            snippet += "…"
        sources.append(
            LaikaSource(
                source_id=chunk.source_id,
                title=chunk.source_title,
                page=chunk.page,
                topic=chunk.topic,
                snippet=snippet,
            )
        )
    return sources


def chunk_to_retrieved(chunk: KnowledgeChunk, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        content=chunk.content,
        source_id=chunk.source_id,
        source_title=chunk.source_title,
        page=chunk.page,
        topic=chunk.topic,
        score=score,
    )
