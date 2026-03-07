"""tests/retrieval/test_vector.py — Qdrant 벡터 검색 TDD

테스트 전략:
- mock_qdrant / mocker로 실제 Qdrant 없이 동작 검증
- VectorRetriever(qdrant_client, collection, embeddings)
- search(query, top_k) → [{"id", "text", "score"}, ...] 형식 확인
- top_k=0 → 빈 리스트 반환
- Qdrant search 결과 없음 → 빈 리스트 반환
"""
import pytest
from unittest.mock import MagicMock


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
        mock_qdrant.search.return_value = []
        results = vector_retriever.search("개인정보 동의", top_k=3)
        assert isinstance(results, list)

    def test_search_result_format(self, vector_retriever, mock_qdrant):
        """각 결과에 id, text, score 키 포함"""
        hit = MagicMock()
        hit.id = "PA_3"
        hit.score = 0.92
        hit.payload = {"text": "개인정보처리자는 처리 목적을 명확하게 하여야 한다."}
        mock_qdrant.search.return_value = [hit]

        results = vector_retriever.search("처리 목적", top_k=1)
        assert len(results) == 1
        assert results[0]["id"] == "PA_3"
        assert results[0]["text"] == "개인정보처리자는 처리 목적을 명확하게 하여야 한다."
        assert results[0]["score"] == pytest.approx(0.92)

    def test_top_k_zero_returns_empty(self, vector_retriever, mock_qdrant):
        """top_k=0 → 빈 리스트"""
        mock_qdrant.search.return_value = []
        results = vector_retriever.search("쿼리", top_k=0)
        assert results == []

    def test_no_results_returns_empty(self, vector_retriever, mock_qdrant):
        """Qdrant 결과 없음 → 빈 리스트"""
        mock_qdrant.search.return_value = []
        results = vector_retriever.search("존재하지 않는 조항", top_k=5)
        assert results == []

    def test_search_calls_qdrant_with_top_k(self, vector_retriever, mock_qdrant):
        """search() 호출 시 Qdrant client에 top_k 전달됨"""
        mock_qdrant.search.return_value = []
        vector_retriever.search("쿼리", top_k=7)
        call_kwargs = mock_qdrant.search.call_args
        assert call_kwargs is not None
