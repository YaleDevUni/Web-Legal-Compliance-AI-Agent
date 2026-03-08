"""tests/cache/test_url_cache.py — URL 분석 결과 Redis 캐시 TDD

테스트 전략:
- mock_redis 픽스처로 실제 Redis 없이 동작 검증
- URL 키를 exact-match로 사용 (시맨틱 유사도 불필요)
- ComplianceReport 리스트를 JSON으로 직렬화/역직렬화
- 캐시 저장 시 TTL=3600초(1시간) 기본값 확인
- 캐시 미스 → None 반환
- 캐시 히트 → ComplianceReport 리스트 반환
- 빈 리스트도 캐시 저장 가능 (분석 완료된 결과)
- TTL 커스터마이징 가능
"""
import json
from datetime import datetime

import pytest
from unittest.mock import MagicMock

from core.models import Citation, ComplianceReport, ComplianceStatus


# ── 테스트용 샘플 데이터 ────────────────────────────────────────────────────────

@pytest.fixture
def sample_reports():
    """ComplianceReport 리스트 샘플."""
    citation = Citation(
        article_id="PA_15",
        law_name="개인정보 보호법",
        article_number="제15조",
        sha256="a" * 64,
        url="https://www.law.go.kr/",
        updated_at=datetime(2024, 1, 1),
        article_content="개인정보 수집·이용 조항",
    )
    return [
        ComplianceReport(
            status=ComplianceStatus.VIOLATION,
            description="동의 절차 없이 개인정보 수집",
            citations=[citation],
            recommendation="<form> 내 동의 체크박스 추가 필요",
        ),
        ComplianceReport(
            status=ComplianceStatus.COMPLIANT,
            description="개인정보처리방침 링크 존재",
            citations=[citation],
        ),
        ComplianceReport(
            status=ComplianceStatus.UNVERIFIABLE,
            description="서버 암호화 방식 확인 불가",
            citations=[],
        ),
    ]


@pytest.fixture
def cache(mock_redis):
    from cache.url_cache import URLAnalysisCache
    return URLAnalysisCache(redis_client=mock_redis)


# ── 캐시 미스 ─────────────────────────────────────────────────────────────────

class TestCacheMiss:
    def test_miss_when_key_not_in_redis(self, cache, mock_redis):
        """Redis에 키 없음 → None 반환."""
        mock_redis.get.return_value = None
        result = cache.get("https://example.com")
        assert result is None

    def test_get_uses_url_as_key(self, cache, mock_redis):
        """get() 호출 시 URL이 Redis 키로 사용됨."""
        mock_redis.get.return_value = None
        cache.get("https://example.com")
        mock_redis.get.assert_called_once()
        key_used = mock_redis.get.call_args[0][0]
        assert "https://example.com" in key_used


# ── 캐시 히트 ─────────────────────────────────────────────────────────────────

class TestCacheHit:
    def test_hit_returns_compliance_reports(self, cache, mock_redis, sample_reports):
        """캐시 히트 시 ComplianceReport 리스트 반환."""
        serialized = json.dumps([r.model_dump(mode="json") for r in sample_reports])
        mock_redis.get.return_value = serialized.encode()

        result = cache.get("https://example.com")

        assert result is not None
        assert len(result) == 3
        assert all(isinstance(r, ComplianceReport) for r in result)

    def test_hit_preserves_status(self, cache, mock_redis, sample_reports):
        """캐시 히트 시 각 보고서의 status가 유지됨."""
        serialized = json.dumps([r.model_dump(mode="json") for r in sample_reports])
        mock_redis.get.return_value = serialized.encode()

        result = cache.get("https://example.com")

        assert result[0].status == ComplianceStatus.VIOLATION
        assert result[1].status == ComplianceStatus.COMPLIANT
        assert result[2].status == ComplianceStatus.UNVERIFIABLE

    def test_hit_preserves_citations(self, cache, mock_redis, sample_reports):
        """캐시 히트 시 citations 정보가 유지됨."""
        serialized = json.dumps([r.model_dump(mode="json") for r in sample_reports])
        mock_redis.get.return_value = serialized.encode()

        result = cache.get("https://example.com")

        assert result[0].citations[0].article_id == "PA_15"
        assert result[2].citations == []

    def test_empty_list_is_cached(self, cache, mock_redis):
        """빈 리스트도 유효한 캐시 값으로 처리됨 (분석 완료, 결과 없음)."""
        serialized = json.dumps([])
        mock_redis.get.return_value = serialized.encode()

        result = cache.get("https://example.com")

        assert result == []


# ── 캐시 저장 ─────────────────────────────────────────────────────────────────

class TestCacheSet:
    def test_set_stores_with_default_ttl(self, cache, mock_redis, sample_reports):
        """set() 호출 시 기본 TTL=3600초로 저장."""
        cache.set("https://example.com", sample_reports)

        mock_redis.set.assert_called_once()
        _, kwargs = mock_redis.set.call_args[0], mock_redis.set.call_args[1]
        assert kwargs.get("ex") == 3600

    def test_set_stores_with_custom_ttl(self, cache, mock_redis, sample_reports):
        """set() 호출 시 커스텀 TTL 적용."""
        cache.set("https://example.com", sample_reports, ttl=7200)

        _, kwargs = mock_redis.set.call_args[0], mock_redis.set.call_args[1]
        assert kwargs.get("ex") == 7200

    def test_set_serializes_as_json(self, cache, mock_redis, sample_reports):
        """set() 호출 시 JSON 문자열로 직렬화."""
        cache.set("https://example.com", sample_reports)

        args, _ = mock_redis.set.call_args[0], mock_redis.set.call_args[1]
        payload = json.loads(args[1])
        assert isinstance(payload, list)
        assert len(payload) == 3
        assert payload[0]["status"] == "violation"

    def test_set_uses_url_as_key(self, cache, mock_redis, sample_reports):
        """set() 호출 시 URL이 Redis 키로 사용됨."""
        cache.set("https://example.com/path", sample_reports)

        args, _ = mock_redis.set.call_args[0], mock_redis.set.call_args[1]
        assert "https://example.com/path" in args[0]

    def test_set_empty_list(self, cache, mock_redis):
        """빈 리스트도 정상 저장."""
        cache.set("https://example.com", [])

        mock_redis.set.assert_called_once()
        args, _ = mock_redis.set.call_args[0], mock_redis.set.call_args[1]
        assert json.loads(args[1]) == []
