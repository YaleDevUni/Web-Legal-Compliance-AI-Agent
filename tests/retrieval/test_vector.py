"""tests/retrieval/test_vector.py — Qdrant 벡터 검색 TDD

테스트 전략:
- mock_qdrant / mocker로 실제 Qdrant 없이 동작 검증
- VectorRetriever(qdrant_client, collection, embeddings)
- search(query, top_k) → [{"id", "text", "score", "metadata"}, ...] 형식 확인
- top_k=0 → 빈 리스트 반환 (query_points 호출 안 함)
- Qdrant 결과 없음 → 빈 리스트 반환
"""
import pytest
from unittest.mock import MagicMock


def _make_hit(article_id: str, text: str, score: float = 0.9) -> MagicMock:
    """query_points 결과 포인트 mock 생성 헬퍼."""
    hit = MagicMock()
    hit.id = article_id
    hit.score = score
    hit.payload = {
        "text": text,
        "article_id": article_id,
        "law_name": "개인정보 보호법",
        "article_number": "제3조",
        "sha256": "a" * 64,
        "url": "https://www.law.go.kr/",
        "updated_at": "2025-01-01T00:00:00",
    }
    return hit


def _mock_query_result(hits: list) -> MagicMock:
    """query_points 반환값 mock."""
    result = MagicMock()
    result.points = hits
    return result


@pytest.fixture
def vector_retriever(mock_qdrant, mocker):
    """embeddings mock 패치 후 VectorRetriever 초기화"""
    mocker.patch("retrieval.vector.OpenAIEmbeddings")
    from retrieval.vector import VectorRetriever
    return VectorRetriever(
        qdrant_client=mock_qdrant,
        collection="law_articles",
        embeddings=MagicMock(),
    )


class TestVectorRetriever:
    def test_search_returns_list(self, vector_retriever, mock_qdrant):
        """search() → 리스트 타입 반환"""
        mock_qdrant.query_points.return_value = _mock_query_result([])
        results = vector_retriever.search("개인정보 동의", top_k=3)
        assert isinstance(results, list)

    def test_search_result_format(self, vector_retriever, mock_qdrant):
        """각 결과에 id, text, score, metadata 키 포함"""
        hit = _make_hit("PA_3", "개인정보처리자는 처리 목적을 명확하게 하여야 한다.", 0.92)
        mock_qdrant.query_points.return_value = _mock_query_result([hit])

        results = vector_retriever.search("처리 목적", top_k=1)
        assert len(results) == 1
        assert results[0]["id"] == "PA_3"
        assert results[0]["text"] == "개인정보처리자는 처리 목적을 명확하게 하여야 한다."
        assert results[0]["score"] == pytest.approx(0.92)
        assert "metadata" in results[0]
        assert results[0]["metadata"]["article_id"] == "PA_3"

    def test_top_k_zero_returns_empty(self, vector_retriever, mock_qdrant):
        """top_k=0 → 빈 리스트, query_points 호출 안 함"""
        results = vector_retriever.search("쿼리", top_k=0)
        assert results == []
        mock_qdrant.query_points.assert_not_called()

    def test_no_results_returns_empty(self, vector_retriever, mock_qdrant):
        """Qdrant 결과 없음 → 빈 리스트"""
        mock_qdrant.query_points.return_value = _mock_query_result([])
        results = vector_retriever.search("존재하지 않는 조항", top_k=5)
        assert results == []

    def test_search_calls_qdrant_with_top_k(self, vector_retriever, mock_qdrant):
        """search() 호출 시 Qdrant client에 limit=top_k 전달됨"""
        mock_qdrant.query_points.return_value = _mock_query_result([])
        vector_retriever.search("쿼리", top_k=7)
        call_kwargs = mock_qdrant.query_points.call_args
        assert call_kwargs is not None
        assert call_kwargs.kwargs.get("limit") == 7

    def test_metadata_does_not_include_text(self, vector_retriever, mock_qdrant):
        """metadata에 text 필드가 중복 포함되지 않음"""
        hit = _make_hit("PA_3", "조문 내용")
        mock_qdrant.query_points.return_value = _mock_query_result([hit])
        results = vector_retriever.search("쿼리", top_k=1)
        assert "text" not in results[0]["metadata"]
