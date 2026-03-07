"""tests/retrieval/test_query_rewriter.py — LLM 기반 쿼리 재작성 TDD

테스트 전략:
- mock_llm으로 실제 OpenAI 없이 QueryRewriter 검증
- rewrite(query) → str 반환, 원본 쿼리가 아닌 재작성된 문자열
- rewrite_multiple(query, n) → list[str], 길이 n
- 빈 쿼리 → ValueError 발생
- LLM 응답이 빈 문자열이면 원본 쿼리 fallback
"""
import pytest


@pytest.fixture
def rewriter(mock_llm, mocker):
    """ChatOpenAI mock 패치 후 QueryRewriter 초기화"""
    mocker.patch("retrieval.query_rewriter.ChatOpenAI", return_value=mock_llm)
    from retrieval.query_rewriter import QueryRewriter
    return QueryRewriter()


class TestQueryRewriter:
    def test_rewrite_returns_string(self, rewriter, mock_llm):
        """rewrite() → str 타입 반환"""
        mock_llm.invoke.return_value.content = "개인정보 제3자 제공 조항"
        result = rewriter.rewrite("개인정보 줘도 돼?")
        assert isinstance(result, str)

    def test_rewrite_uses_llm(self, rewriter, mock_llm):
        """rewrite() 호출 시 LLM invoke 호출됨"""
        mock_llm.invoke.return_value.content = "재작성된 쿼리"
        rewriter.rewrite("입력 쿼리")
        mock_llm.invoke.assert_called_once()

    def test_empty_query_raises(self, rewriter):
        """빈 쿼리 → ValueError"""
        with pytest.raises(ValueError, match="쿼리"):
            rewriter.rewrite("")

    def test_llm_empty_response_fallback(self, rewriter, mock_llm):
        """LLM이 빈 문자열 반환 시 원본 쿼리로 fallback"""
        mock_llm.invoke.return_value.content = ""
        result = rewriter.rewrite("원본 쿼리")
        assert result == "원본 쿼리"

    def test_rewrite_multiple_returns_list(self, rewriter, mock_llm):
        """rewrite_multiple(query, n=3) → 길이 3인 리스트"""
        mock_llm.invoke.return_value.content = "재작성 쿼리"
        results = rewriter.rewrite_multiple("개인정보 동의", n=3)
        assert isinstance(results, list)
        assert len(results) == 3
