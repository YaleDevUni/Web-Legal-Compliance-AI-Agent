"""tests/retrieval/test_bm25.py — BM25 희소 검색 TDD

테스트 전략:
- rank-bm25 라이브러리 기반 BM25Retriever 검증
- 코퍼스: [{"id": str, "text": str}] 형식의 조항 청크 목록
- 조항 번호("제17조") 정확 매칭이 상위에 랭크되는지 확인
- 빈 코퍼스로 초기화 시 ValueError 발생 확인
"""
import pytest


@pytest.fixture
def corpus():
    return [
        {"id": "PA_3",  "text": "개인정보처리자는 처리 목적을 명확하게 하여야 한다."},
        {"id": "PA_17", "text": "제17조 개인정보처리자는 제3자에게 개인정보를 제공할 수 있다."},
        {"id": "PA_29", "text": "개인정보처리자는 보안 조치를 취하여야 한다."},
    ]


class TestBM25Retriever:
    def test_article_number_match_top_ranked(self, corpus):
        """'제17조' 쿼리 → id='PA_17' 조항이 최상위 결과에 포함됨"""
        from retrieval.bm25 import BM25Retriever
        retriever = BM25Retriever(corpus)
        results = retriever.search("제17조", top_k=2)
        ids = [r["id"] for r in results]
        assert "PA_17" in ids

    def test_keyword_match(self, corpus):
        """'보안 조치' 쿼리 → 관련 조항이 결과에 포함됨"""
        from retrieval.bm25 import BM25Retriever
        retriever = BM25Retriever(corpus)
        results = retriever.search("보안 조치", top_k=2)
        ids = [r["id"] for r in results]
        assert "PA_29" in ids

    def test_returns_correct_format(self, corpus):
        """결과 각 항목에 id, text, score 키 포함"""
        from retrieval.bm25 import BM25Retriever
        retriever = BM25Retriever(corpus)
        results = retriever.search("개인정보", top_k=1)
        assert len(results) == 1
        assert "id" in results[0]
        assert "text" in results[0]
        assert "score" in results[0]

    def test_top_k_limits_results(self, corpus):
        """top_k=2 → 최대 2개 결과 반환"""
        from retrieval.bm25 import BM25Retriever
        retriever = BM25Retriever(corpus)
        results = retriever.search("개인정보", top_k=2)
        assert len(results) <= 2

    def test_empty_corpus_raises(self):
        """빈 코퍼스로 초기화 시 ValueError 발생"""
        from retrieval.bm25 import BM25Retriever
        with pytest.raises(ValueError, match="코퍼스"):
            BM25Retriever([])
