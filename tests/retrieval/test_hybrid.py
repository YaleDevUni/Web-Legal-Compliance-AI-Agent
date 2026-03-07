"""tests/retrieval/test_hybrid.py — HybridRetriever (BM25 + Vector + RRF) TDD

테스트 전략:
- Qdrant scroll로 코퍼스 로드 → BM25 인덱스 빌드
- search() → BM25 + Vector 결과를 RRF로 병합
- 반환 형식: [{"id", "text", "score", "metadata"}, ...]
- top_k 적용, BM25 단독 히트도 결과에 포함됨
"""
import pytest
from unittest.mock import MagicMock


def _make_scroll_point(article_id: str, text: str) -> MagicMock:
    point = MagicMock()
    point.id = article_id
    point.payload = {
        "text": text,
        "article_id": article_id,
        "law_name": "개인정보 보호법",
        "article_number": "제23조",
        "sha256": "a" * 64,
        "url": "https://www.law.go.kr/",
        "updated_at": "2025-01-01T00:00:00",
    }
    return point


def _make_vector_result(article_id: str, text: str, score: float = 0.8) -> dict:
    return {
        "id": article_id,
        "text": text,
        "score": score,
        "metadata": {
            "article_id": article_id,
            "law_name": "개인정보 보호법",
            "article_number": "제23조",
            "sha256": "a" * 64,
            "url": "https://www.law.go.kr/",
            "updated_at": "2025-01-01T00:00:00",
        },
    }


@pytest.fixture
def hybrid_retriever(mock_qdrant, mocker):
    """Qdrant scroll + OpenAIEmbeddings mock 후 HybridRetriever 초기화"""
    mocker.patch("retrieval.vector.OpenAIEmbeddings")

    # scroll 응답: (points_list, next_offset=None)
    points = [
        _make_scroll_point("PA_23", "민감정보 처리 제한 건강정보 동의"),
        _make_scroll_point("PA_15", "개인정보 수집 이용 동의"),
        _make_scroll_point("PA_29", "개인정보의 안전성 확보 조치 암호화"),
    ]
    mock_qdrant.scroll.return_value = (points, None)

    from retrieval.hybrid import HybridRetriever
    return HybridRetriever(
        qdrant_client=mock_qdrant,
        collection="law_articles",
        embeddings=MagicMock(),
    )


class TestHybridRetriever:
    def test_search_returns_list(self, hybrid_retriever, mock_qdrant):
        """search() → 리스트 반환"""
        query_result = MagicMock()
        query_result.points = []
        mock_qdrant.query_points.return_value = query_result

        results = hybrid_retriever.search("민감정보 수집 동의", top_k=3)
        assert isinstance(results, list)

    def test_result_has_required_keys(self, hybrid_retriever, mock_qdrant):
        """각 결과에 id, text, score, metadata 키 포함"""
        hit = MagicMock()
        hit.id = "PA_23"
        hit.score = 0.9
        hit.payload = {
            "text": "민감정보 처리 제한 건강정보 동의",
            "article_id": "PA_23",
            "law_name": "개인정보 보호법",
            "article_number": "제23조",
            "sha256": "a" * 64,
            "url": "https://www.law.go.kr/",
            "updated_at": "2025-01-01T00:00:00",
        }
        query_result = MagicMock()
        query_result.points = [hit]
        mock_qdrant.query_points.return_value = query_result

        results = hybrid_retriever.search("민감정보 동의", top_k=3)
        assert len(results) >= 1
        assert all(k in results[0] for k in ("id", "text", "score", "metadata"))

    def test_bm25_only_hit_included(self, hybrid_retriever, mock_qdrant):
        """벡터 검색에 없어도 BM25 히트면 결과에 포함됨"""
        # 벡터 검색 결과 없음
        query_result = MagicMock()
        query_result.points = []
        mock_qdrant.query_points.return_value = query_result

        # BM25는 코퍼스에서 "민감정보" 키워드로 PA_23 매칭
        results = hybrid_retriever.search("민감정보", top_k=5)
        ids = [r["id"] for r in results]
        assert "PA_23" in ids

    def test_rrf_boosts_shared_hits(self, hybrid_retriever, mock_qdrant):
        """BM25 + Vector 모두 히트한 문서는 RRF 점수가 더 높음"""
        hit = MagicMock()
        hit.id = "PA_23"
        hit.score = 0.9
        hit.payload = {
            "text": "민감정보 처리 제한 건강정보 동의",
            "article_id": "PA_23",
            "law_name": "개인정보 보호법",
            "article_number": "제23조",
            "sha256": "a" * 64,
            "url": "https://www.law.go.kr/",
            "updated_at": "2025-01-01T00:00:00",
        }
        query_result = MagicMock()
        query_result.points = [hit]
        mock_qdrant.query_points.return_value = query_result

        results = hybrid_retriever.search("민감정보 처리 제한", top_k=5)
        # PA_23은 BM25 + Vector 모두 히트 → 상위권
        assert results[0]["id"] == "PA_23"

    def test_top_k_limits_results(self, hybrid_retriever, mock_qdrant):
        """top_k 만큼만 반환"""
        query_result = MagicMock()
        query_result.points = []
        mock_qdrant.query_points.return_value = query_result

        results = hybrid_retriever.search("개인정보", top_k=1)
        assert len(results) <= 1

    def test_metadata_attached_from_corpus(self, hybrid_retriever, mock_qdrant):
        """결과의 metadata가 Qdrant payload에서 올바르게 복원됨"""
        hit = MagicMock()
        hit.id = "PA_15"
        hit.score = 0.85
        hit.payload = {
            "text": "개인정보 수집 이용 동의",
            "article_id": "PA_15",
            "law_name": "개인정보 보호법",
            "article_number": "제15조",
            "sha256": "b" * 64,
            "url": "https://www.law.go.kr/",
            "updated_at": "2025-01-01T00:00:00",
        }
        query_result = MagicMock()
        query_result.points = [hit]
        mock_qdrant.query_points.return_value = query_result

        results = hybrid_retriever.search("개인정보 수집 동의", top_k=5)
        pa15 = next((r for r in results if r["id"] == "PA_15"), None)
        assert pa15 is not None
        assert pa15["metadata"]["article_id"] == "PA_15"
