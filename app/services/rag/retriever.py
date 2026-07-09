from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.knowledge_chunk import KnowledgeChunk
from app.services.rag.prompts import RetrievedChunk
from app.services.rag.providers import get_embeddings
from app.services.rag.sources import chunk_to_retrieved


class PgVectorRetriever:
    def __init__(self, db: Session, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._embeddings = get_embeddings(settings)

    def embed_query(self, query: str) -> list[float]:
        return self._embeddings.embed_query(query)

    def search(self, query_vector: list[float]) -> list[RetrievedChunk]:
        vector_literal = "[" + ",".join(str(v) for v in query_vector) + "]"

        rows = self._db.execute(
            text(
                """
                SELECT id, content, source_id, source_title, page, topic,
                       1 - (embedding <=> CAST(:query_vec AS vector)) AS score
                FROM knowledge_chunks
                ORDER BY embedding <=> CAST(:query_vec AS vector)
                LIMIT :top_k
                """
            ),
            {
                "query_vec": vector_literal,
                "top_k": self._settings.laika_top_k,
            },
        ).mappings().all()

        results: list[RetrievedChunk] = []
        for row in rows:
            chunk = self._db.get(KnowledgeChunk, row["id"])
            if chunk is None:
                continue
            results.append(chunk_to_retrieved(chunk, float(row["score"])))
        return results

    def retrieve(self, query: str) -> list[RetrievedChunk]:
        return self.search(self.embed_query(query))
