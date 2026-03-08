"""tests/agents/test_legal_agent.py — LegalReasoningAgent TDD (mock)"""
import pytest
from unittest.mock import MagicMock
from agents.legal_agent import LegalReasoningAgent

@pytest.fixture
def mock_retrievers():
    law = MagicMock()
    law.search.return_value = [
        {
            "id": "doc1",
            "text": "주택법 제1조 본문",
            "metadata": {
                "article_id": "L1", "law_name": "주택법", "article_number": "제1조",
                "full_content": "주택법 제1조 전체 내용", "doc_type": "law", "updated_at": "2024-01-01T00:00:00"
            }
        }
    ]

    case = MagicMock()
    case.search.return_value = [
        {
            "id": "case1",
            "text": "판례 2024다123 요지",
            "metadata": {
                "case_id": "C1", "case_number": "2024다123", "case_name": "임대차",
                "doc_type": "case", "decision_date": "2024-05-01T00:00:00"
            }
        }
    ]
    return law, case

@pytest.fixture
def mock_expander():
    exp = MagicMock()
    exp.expand.return_value = [
        {
            "id": "doc2",
            "text": "연관 조문 내용",
            "metadata": {
                "article_id": "L2", "law_name": "주택법", "article_number": "제2조",
                "full_content": "주택법 제2조 전체 내용", "doc_type": "law", "updated_at": "2024-01-01T00:00:00"
            }
        }
    ]
    return exp

class TestLegalReasoningAgent:
    @pytest.mark.asyncio
    async def test_ask_returns_legal_answer(self, mock_retrievers, mock_expander):
        """aask()가 content → citations 순으로 청크를 스트리밍하는지 확인"""
        # ChatOpenAI는 Pydantic 모델이라 patch.object 불가 → _llm 자체를 대체
        async def fake_astream(*args, **kwargs):
            chunk = MagicMock()
            chunk.content = "답변입니다. 주택법 제1조에 따르면..."
            yield chunk

        mock_llm = MagicMock()
        mock_llm.astream = fake_astream

        law_ret, case_ret = mock_retrievers
        agent = LegalReasoningAgent(
            law_retriever=law_ret,
            case_retriever=case_ret,
            graph_expander=mock_expander,
        )
        agent._llm = mock_llm

        chunks = []
        async for chunk in agent.aask("전세금 반환은 언제까지인가요?", session_id="test_session"):
            chunks.append(chunk)

        content_chunks = [c for c in chunks if c["type"] == "content"]
        citations_chunk = next(c for c in chunks if c["type"] == "citations")

        assert content_chunks, "content 청크가 없음"
        assert "답변입니다" in citations_chunk["full_answer"]
        assert len(citations_chunk["citations"]) >= 2  # 법령 L1 + 확장 L2 + 판례 CASE_C1
        assert "L1" in [c.article_id for c in citations_chunk["citations"]]
        assert "CASE_C1" in [c.article_id for c in citations_chunk["citations"]]
        assert "L2" in citations_chunk["related_articles"]

    def test_build_context_deduplication(self, mock_retrievers):
        """중복된 조문 ID가 컨텍스트에서 하나로 합쳐지는지 확인"""
        agent = LegalReasoningAgent()
        law_ret, _ = mock_retrievers
        
        # 중복 데이터 시뮬레이션
        duplicate_laws = law_ret.search("") * 2
        context, citation_map = agent._build_context(duplicate_laws, [])
        
        assert "[법령] 주택법 제1조" in context
        assert context.count("[법령]") == 1
        assert "L1" in citation_map
