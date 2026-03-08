"""tests/session/test_conversation.py — 대화 세션 TDD (mock)"""
import pytest
import json
from unittest.mock import MagicMock
from session.conversation import ConversationSession

@pytest.fixture
def mock_redis():
    return MagicMock()

class TestConversationSession:
    def test_add_message_calls_redis(self, mock_redis):
        """메시지 추가 시 Redis rpush 및 ltrim 호출 확인"""
        session = ConversationSession(mock_redis, "test_sid", context_window=5)
        session.add_message("user", "안녕하세요")
        
        # rpush 호출 확인 (JSON 인코딩됨)
        mock_redis.rpush.assert_called_once()
        args = mock_redis.rpush.call_args[0]
        assert args[0] == "session:test_sid"
        assert json.loads(args[1]) == {"role": "user", "content": "안녕하세요"}
        
        # ltrim (윈도우 유지) 호출 확인
        mock_redis.ltrim.assert_called_with("session:test_sid", -5, -1)

    def test_get_history_returns_list(self, mock_redis):
        """Redis 데이터를 파싱하여 리스트로 반환하는지 확인"""
        mock_redis.lrange.return_value = [
            json.dumps({"role": "user", "content": "Q"}),
            json.dumps({"role": "assistant", "content": "A"})
        ]
        
        session = ConversationSession(mock_redis, "test_sid")
        history = session.get_history()
        
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["content"] == "A"

    def test_clear_deletes_key(self, mock_redis):
        """세션 삭제 시 Redis delete 호출 확인"""
        session = ConversationSession(mock_redis, "test_sid")
        session.clear()
        mock_redis.delete.assert_called_with("session:test_sid")
