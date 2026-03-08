"""api/dependencies.py — FastAPI 공유 싱글턴 의존성."""
from functools import lru_cache

from qdrant_client import QdrantClient
import redis as redis_lib

from core.config import Settings
from core.logger import logger
from retrieval.hybrid import HybridRetriever
from cache.url_cache import URLAnalysisCache
from streaming.redis_stream import RedisStream


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@lru_cache(maxsize=1)
def get_retriever() -> HybridRetriever | None:
    try:
        settings = get_settings()
        client = QdrantClient(url=str(settings.qdrant_url), timeout=30)
        return HybridRetriever(client, collection=settings.qdrant_collection)
    except Exception as e:
        logger.warning(f"HybridRetriever 초기화 실패: {e}")
        return None


@lru_cache(maxsize=1)
def get_redis_client():
    try:
        settings = get_settings()
        client = redis_lib.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        return client
    except Exception as e:
        logger.warning(f"Redis 연결 실패: {e}")
        return None


def get_url_cache() -> URLAnalysisCache | None:
    rc = get_redis_client()
    return URLAnalysisCache(redis_client=rc) if rc else None


def get_stream() -> RedisStream | None:
    rc = get_redis_client()
    return RedisStream(redis_client=rc) if rc else None
