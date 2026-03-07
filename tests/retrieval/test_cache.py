"""tests/retrieval/test_cache.py — Redis Semantic Cache TDD

테스트 전략:
- mock_redis 픽스처로 실제 Redis 없이 동작 검증
- 쿼리 임베딩 cosine 유사도로 캐시 히트/미스 판별 (임계값 0.95)
- 캐시 저장 시 TTL=3600초(1시간) 설정 확인
- 직렬화: JSON 문자열로 저장/역직렬화
"""
import json
import pytest
from unittest.mock import MagicMock


@pytest.fixture
def cache(mock_redis, mocker):
    mocker.patch("retrieval.cache.OpenAIEmbeddings")
    from retrieval.cache import SemanticCache
    return SemanticCache(redis_client=mock_redis)


class TestSemanticCache:
    def test_cache_miss_returns_none(self, cache, mock_redis):
        """Redis에 키 없음 → None 반환 (캐시 미스)"""
        mock_redis.keys.return_value = []
        result = cache.get("개인정보 동의 코드 확인")
        assert result is None

    def test_cache_hit_returns_result(self, cache, mock_redis, mocker):
        """cosine ≥ 0.95 → 저장된 결과 반환 (캐시 히트)"""
        stored = [{"status": "compliant", "description": "동의 코드 존재"}]
        mock_redis.keys.return_value = [b"semantic_cache:abc123"]
        mock_redis.get.return_value = json.dumps({
            "embedding": [1.0] * 1536,
            "result": stored,
        }).encode()
        mocker.patch.object(cache, "_embed", return_value=[1.0] * 1536)  # cosine=1.0

        result = cache.get("개인정보 동의 코드 확인")
        assert result == stored

    def test_cache_miss_low_cosine(self, cache, mock_redis, mocker):
        """cosine < 0.95 → None 반환 (캐시 미스)"""
        stored = [{"status": "compliant"}]
        # 완전히 다른 벡터로 cosine ≈ 0
        vec_a = [1.0] + [0.0] * 1535
        vec_b = [0.0] + [1.0] * 1535
        mock_redis.keys.return_value = [b"semantic_cache:abc123"]
        mock_redis.get.return_value = json.dumps({
            "embedding": vec_a,
            "result": stored,
        }).encode()
        mocker.patch.object(cache, "_embed", return_value=vec_b)

        result = cache.get("완전히 다른 질문")
        assert result is None

    def test_set_stores_with_ttl(self, cache, mock_redis, mocker):
        """set() 호출 시 TTL=3600초로 Redis에 저장"""
        mocker.patch.object(cache, "_embed", return_value=[0.5] * 1536)
        result = [{"status": "violation"}]
        cache.set("질문", result)
        mock_redis.set.assert_called_once()
        args, kwargs = mock_redis.set.call_args
        assert kwargs.get("ex") == 3600

    def test_set_serializes_as_json(self, cache, mock_redis, mocker):
        """set() 호출 시 결과가 JSON 직렬화되어 저장됨"""
        mocker.patch.object(cache, "_embed", return_value=[0.1] * 1536)
        result = [{"status": "compliant", "description": "OK"}]
        cache.set("질문", result)
        args, kwargs = mock_redis.set.call_args
        payload = json.loads(args[1])
        assert payload["result"] == result
        assert "embedding" in payload
