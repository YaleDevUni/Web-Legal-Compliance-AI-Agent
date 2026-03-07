"""src/embedder/indexer.py — Qdrant 벡터 색인 (증분 upsert)"""
import uuid

from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from core.models import LawArticle
from embedder.chunker import chunk_article

_VECTOR_SIZE = 1536  # text-embedding-3-small


class ArticleIndexer:
    def __init__(self, qdrant_client: QdrantClient, collection: str) -> None:
        self._client = qdrant_client
        self._collection = collection
        self._embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    def _ensure_collection(self) -> None:
        if not self._client.collection_exists(self._collection):
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE),
            )

    def _embed(self, texts: list[str]) -> list[list[float]]:
        return self._embeddings.embed_documents(texts)

    def upsert(self, articles: list[LawArticle], changed_ids: set[str] | None = None) -> None:
        """changed_ids가 주어지면 해당 조항만, 없으면 전체를 색인한다."""
        self._ensure_collection()

        targets = (
            [a for a in articles if a.article_id in changed_ids]
            if changed_ids is not None
            else articles
        )
        if not targets:
            return

        all_chunks: list[dict] = []
        for article in targets:
            all_chunks.extend(chunk_article(article))

        texts = [c["text"] for c in all_chunks]
        vectors = self._embed(texts)

        points = [
            PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, c["text"])),
                vector=v,
                payload=c["metadata"],
            )
            for c, v in zip(all_chunks, vectors)
        ]
        self._client.upsert(collection_name=self._collection, points=points)
