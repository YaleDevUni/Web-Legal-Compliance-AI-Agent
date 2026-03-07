"""src/retrieval/cache.py — Redis Semantic Cache"""
import hashlib
import json
import math

from langchain_openai import OpenAIEmbeddings
from redis import Redis

_TTL = 3600  # 1시간
_THRESHOLD = 0.95
_PREFIX = "semantic_cache:"


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class SemanticCache:
    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client
        self._embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    def _embed(self, text: str) -> list[float]:
        return self._embeddings.embed_query(text)

    def _key(self, text: str) -> str:
        digest = hashlib.md5(text.encode()).hexdigest()
        return f"{_PREFIX}{digest}"

    def get(self, query: str) -> list | None:
        """유사 쿼리 캐시 히트 시 저장된 결과 반환, 미스 시 None"""
        query_vec = self._embed(query)
        for raw_key in self._redis.keys(f"{_PREFIX}*"):
            raw = self._redis.get(raw_key)
            if raw is None:
                continue
            payload = json.loads(raw)
            stored_vec = payload["embedding"]
            if _cosine(query_vec, stored_vec) >= _THRESHOLD:
                return payload["result"]
        return None

    def set(self, query: str, result: list) -> None:
        """쿼리 결과를 임베딩과 함께 TTL=1h로 캐싱"""
        vec = self._embed(query)
        payload = json.dumps({"embedding": vec, "result": result})
        self._redis.set(self._key(query), payload, ex=_TTL)
