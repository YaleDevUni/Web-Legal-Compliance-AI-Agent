"""tests/api/test_chat_integration.py — API 엔드포인트 통합 테스트 (TestClient)"""
import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from core.models import Citation
from datetime import datetime

# Import app AFTER patching or use app.dependency_overrides
from api.main import app
from api.dependencies import get_legal_agent, get_session_manager, get_law_retriever

client = TestClient(app)

@pytest.fixture
def mock_agent():
    agent = MagicMock()
    app.dependency_overrides[get_legal_agent] = lambda: agent
    yield agent
    app.dependency_overrides.pop(get_legal_agent)

@pytest.fixture
def mock_sm():
    sm = MagicMock()
    app.dependency_overrides[get_session_manager] = lambda: sm
    yield sm
    app.dependency_overrides.pop(get_session_manager)

class TestChatAPI:
    def test_chat_sse_stream(self, mock_agent, mock_sm):
        """POST /api/chat 호출 시 SSE 스트림이 정상적으로 반환되는지 확인"""
        # Mock Session
        session = MagicMock()
        session.get_history.return_value = []
        mock_sm.get_session.return_value = session

        mock_citation = Citation(
            article_id="L1", law_name="법", article_number="1",
            sha256="a"*64, url="http://t.com", updated_at=datetime.now()
        )

        # aask는 async generator — 라우터가 `async for chunk in agent.aask(...)` 로 호출
        async def fake_aask(*args, **kwargs):
            yield {"type": "content", "text": "AI 답변입니다."}
            yield {
                "type": "citations",
                "citations": [mock_citation],
                "related_articles": [],
                "full_answer": "AI 답변입니다.",
            }

        mock_agent.aask = fake_aask

        response = client.post("/api/chat", json={"question": "안녕", "session_id": "test_sid"})

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        # SSE 데이터 파싱 확인
        lines = response.text.strip().split("\n\n")

        # event: content
        assert "event: content" in lines[0]
        assert "AI 답변입니다." in lines[0]

        # event: citations
        assert "event: citations" in lines[1]
        assert "L1" in lines[1]

        # event: done
        assert "event: done" in lines[2]

    def test_get_history(self, mock_sm):
        """GET /api/sessions/{id}/history 호출 확인"""
        session = MagicMock()
        session.get_history.return_value = [{"role": "user", "content": "Q"}]
        mock_sm.get_session.return_value = session
        
        response = client.get("/api/sessions/test_sid/history")
        assert response.status_code == 200
        assert response.json() == [{"role": "user", "content": "Q"}]

class TestSearchAPI:
    def test_search_endpoint(self):
        """GET /api/search 호출 확인"""
        ret = MagicMock()
        ret.search.return_value = [{"id": "1", "text": "res", "score": 0.9, "metadata": {}}]
        
        app.dependency_overrides[get_law_retriever] = lambda: ret
        
        try:
            response = client.get("/api/search?q=테스트&type=law")
            assert response.status_code == 200
            assert len(response.json()) == 1
            assert response.json()[0]["text"] == "res"
        finally:
            app.dependency_overrides.pop(get_law_retriever)
