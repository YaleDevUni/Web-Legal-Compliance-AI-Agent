"""src/cache/url_cache.py — URL 분석 결과 Redis 캐시

동일 URL 재분석 시 토큰 낭비 방지.
키: "url_analysis:{url}"  (exact-match)
값: ComplianceReport 리스트 JSON 직렬화
TTL: 기본 3600초 (1시간)
"""
import json

from core.models import ComplianceReport

_KEY_PREFIX = "url_analysis:"


class URLAnalysisCache:
    def __init__(self, redis_client, ttl: int = 3600) -> None:
        self._redis = redis_client
        self._default_ttl = ttl

    def _key(self, url: str) -> str:
        return f"{_KEY_PREFIX}{url}"

    def get(self, url: str) -> list[ComplianceReport] | None:
        """캐시된 분석 결과 반환. 없으면 None."""
        raw = self._redis.get(self._key(url))
        if raw is None:
            return None
        data = json.loads(raw)
        return [ComplianceReport.model_validate(item) for item in data]

    def set(self, url: str, reports: list[ComplianceReport], ttl: int | None = None) -> None:
        """분석 결과를 JSON으로 직렬화해 Redis에 저장."""
        payload = json.dumps([r.model_dump(mode="json") for r in reports])
        self._redis.set(self._key(url), payload, ex=ttl or self._default_ttl)
