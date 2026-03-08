"""tests/cache/test_semantic_cache.py — SemanticCache TDD

테스트 전략:
- OpenAI 임베딩 호출과 Qdrant를 모두 mock 처리
- 캐시 miss → None 반환
- set 후 유사 질문 get → 저장된 응답 반환 (threshold 이상)
- Qdrant/OpenAI 오류 시 None 반환 (graceful degradation)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_qdrant():
    client = MagicMock()
    client.get_collections.return_value = MagicMock(collections=[])
    return client


@pytest.fixture
def cache(mock_qdrant):
    from cache.semantic_cache import SemanticCache

    with patch("cache.semantic_cache.AsyncOpenAI"):
        c = SemanticCache(
            openai_api_key="test-key",
            qdrant_client=mock_qdrant,
            threshold=0.92,
        )
    return c, mock_qdrant


class TestSemanticCacheGet:
    @pytest.mark.asyncio
    async def test_miss_returns_none(self, cache):
        """Qdrant 검색 결과 없으면 None 반환."""
        c, mock_qdrant = cache
        mock_qdrant.query_points.return_value = MagicMock(points=[])

        c._embed = AsyncMock(return_value=[0.1] * 1536)
        result = await c.get("전세 계약 해지 방법")

        assert result is None

    @pytest.mark.asyncio
    async def test_hit_returns_cached_response(self, cache):
        """Qdrant 검색 결과 있으면 payload['response'] 반환."""
        c, mock_qdrant = cache
        expected = {"answer": "전세계약은 ...", "citations": [], "related_articles": []}
        hit = MagicMock()
        hit.payload = {"response": expected}
        mock_qdrant.query_points.return_value = MagicMock(points=[hit])

        c._embed = AsyncMock(return_value=[0.1] * 1536)
        result = await c.get("전세 계약 해지")

        assert result == expected

    @pytest.mark.asyncio
    async def test_qdrant_error_returns_none(self, cache):
        """Qdrant 오류 시 예외 대신 None 반환 (graceful degradation)."""
        c, mock_qdrant = cache
        mock_qdrant.query_points.side_effect = Exception("qdrant unavailable")

        c._embed = AsyncMock(return_value=[0.1] * 1536)
        result = await c.get("임대차 보호법")

        assert result is None


class TestSemanticCacheSet:
    @pytest.mark.asyncio
    async def test_set_calls_qdrant_upsert(self, cache):
        """set() 호출 시 Qdrant upsert가 실행되어야 한다."""
        c, mock_qdrant = cache
        c._embed = AsyncMock(return_value=[0.2] * 1536)

        await c.set(
            "전세 보증금 반환",
            {"answer": "보증금은...", "citations": [], "related_articles": []},
        )

        mock_qdrant.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_error_does_not_raise(self, cache):
        """set() 중 Qdrant 오류 발생해도 예외 전파 안 됨."""
        c, mock_qdrant = cache
        mock_qdrant.upsert.side_effect = Exception("upsert failed")
        c._embed = AsyncMock(return_value=[0.2] * 1536)

        await c.set("질문", {"answer": "답변", "citations": [], "related_articles": []})


class TestSemanticCacheInit:
    def test_creates_collection_if_not_exists(self):
        """query_cache 컬렉션 없으면 create_collection 호출."""
        mock_qdrant = MagicMock()
        mock_qdrant.get_collections.return_value = MagicMock(collections=[])

        with patch("cache.semantic_cache.AsyncOpenAI"):
            from cache.semantic_cache import SemanticCache

            SemanticCache("key", mock_qdrant)

        mock_qdrant.create_collection.assert_called_once()

    def test_skips_collection_creation_if_exists(self):
        """query_cache 컬렉션 이미 있으면 create_collection 호출 안 함."""
        mock_qdrant = MagicMock()
        existing = MagicMock()
        existing.name = "query_cache"
        mock_qdrant.get_collections.return_value = MagicMock(collections=[existing])

        with patch("cache.semantic_cache.AsyncOpenAI"):
            from cache.semantic_cache import SemanticCache

            SemanticCache("key", mock_qdrant)

        mock_qdrant.create_collection.assert_not_called()
