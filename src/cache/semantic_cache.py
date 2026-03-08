"""src/cache/semantic_cache.py — OpenAI 임베딩 기반 시맨틱 응답 캐시

동작:
  1. 질문을 text-embedding-3-small로 임베딩
  2. Qdrant 'query_cache' 컬렉션에서 코사인 유사도 검색
  3. threshold 이상 → 캐시 히트(저장된 응답 반환), 미만 → None
  4. 새 응답은 set()으로 컬렉션에 저장
"""
import hashlib
from typing import Optional

from openai import AsyncOpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

_COLLECTION = "query_cache"
_VECTOR_SIZE = 1536  # text-embedding-3-small


class SemanticCache:
    """동일/유사 질문에 대해 OpenAI 호출 없이 캐시된 답변을 반환한다."""

    def __init__(
        self,
        openai_api_key: str,
        qdrant_client: QdrantClient,
        threshold: float = 0.92,
    ) -> None:
        self._openai = AsyncOpenAI(api_key=openai_api_key)
        self._qdrant = qdrant_client
        self._threshold = threshold
        self._ensure_collection()

    # ------------------------------------------------------------------
    # 내부 유틸
    # ------------------------------------------------------------------

    def _ensure_collection(self) -> None:
        names = {c.name for c in self._qdrant.get_collections().collections}
        if _COLLECTION not in names:
            self._qdrant.create_collection(
                collection_name=_COLLECTION,
                vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE),
            )

    async def _embed(self, text: str) -> list[float]:
        resp = await self._openai.embeddings.create(
            model="text-embedding-3-small", input=text
        )
        return resp.data[0].embedding

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------

    async def get(self, question: str) -> Optional[dict]:
        """유사 질문 캐시 히트 시 저장된 응답(answer + citations) 반환."""
        try:
            vector = await self._embed(question)
            response = self._qdrant.query_points(
                collection_name=_COLLECTION,
                query=vector,
                limit=1,
                with_payload=True,
                score_threshold=self._threshold,
            )
            points = response.points
            if points:
                return points[0].payload.get("response")
        except Exception:
            pass
        return None

    async def set(self, question: str, response: dict) -> None:
        """질문-응답 쌍을 캐시에 저장한다."""
        try:
            vector = await self._embed(question)
            point_id = int(hashlib.md5(question.encode()).hexdigest()[:8], 16)
            self._qdrant.upsert(
                collection_name=_COLLECTION,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=vector,
                        payload={"question": question, "response": response},
                    )
                ],
            )
        except Exception:
            pass
