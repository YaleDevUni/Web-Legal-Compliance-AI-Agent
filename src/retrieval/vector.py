"""retrieval/vector.py — Qdrant 벡터 검색 모듈"""
from langchain_openai import OpenAIEmbeddings


class VectorRetriever:
    """Qdrant 기반 밀집 벡터 검색기."""

    def __init__(self, qdrant_client, collection: str, embeddings=None) -> None:
        self._client = qdrant_client
        self._collection = collection
        self._embeddings = embeddings or OpenAIEmbeddings()

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """쿼리를 임베딩 후 Qdrant에서 유사 벡터 검색.

        반환: [{"id": str, "text": str, "score": float}, ...]
        """
        if top_k == 0:
            return []
        vector = self._embeddings.embed_query(query)
        hits = self._client.search(
            collection_name=self._collection,
            query_vector=vector,
            limit=top_k,
        )
        return [
            {
                "id": hit.id,
                "text": hit.payload.get("text", ""),
                "score": float(hit.score),
            }
            for hit in hits
        ]
