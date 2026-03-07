"""retrieval/vector.py — Qdrant 벡터 검색 모듈"""
from langchain_openai import OpenAIEmbeddings


class VectorRetriever:
    """Qdrant 기반 밀집 벡터 검색기."""

    def __init__(self, qdrant_client, collection: str, embeddings=None) -> None:
        self._client = qdrant_client
        self._collection = collection
        self._embeddings = embeddings or OpenAIEmbeddings(model="text-embedding-3-small")

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """쿼리를 임베딩 후 Qdrant에서 유사 벡터 검색.

        반환: [{"id": str, "text": str, "score": float}, ...]
        """
        if top_k == 0:
            return []
        vector = self._embeddings.embed_query(query)
        result = self._client.query_points(
            collection_name=self._collection,
            query=vector,
            limit=top_k,
            with_payload=True,
        )
        return [
            {
                "id": str(hit.id),
                "text": hit.payload.get("text", ""),
                "score": float(hit.score),
                "metadata": {k: v for k, v in hit.payload.items() if k != "text"},
            }
            for hit in result.points
        ]
