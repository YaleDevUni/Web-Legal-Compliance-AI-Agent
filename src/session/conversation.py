"""src/session/conversation.py — Redis 기반 대화 세션 관리"""
import json
from typing import List, Dict, Optional
from redis import Redis
from core.logger import logger

class ConversationSession:
    """Redis를 사용하여 대화 내역을 저장하고 관리한다."""

    def __init__(
        self,
        redis_client: Redis,
        session_id: str,
        context_window: int = 10,
        ttl: int = 3600
    ) -> None:
        self._redis = redis_client
        self._session_id = session_id
        self._key = f"session:{session_id}"
        self._context_window = context_window
        self._ttl = ttl

    def add_message(self, role: str, content: str) -> None:
        """대화 내역에 메시지를 추가한다."""
        msg = {"role": role, "content": content}
        self._redis.rpush(self._key, json.dumps(msg))
        
        # 윈도우 크기 유지 (LTRIM)
        self._redis.ltrim(self._key, -self._context_window, -1)
        
        # 만료 시간 갱신
        self._redis.expire(self._key, self._ttl)

    def get_history(self) -> List[Dict[str, str]]:
        """전체 대화 내역을 가져온다."""
        items = self._redis.lrange(self._key, 0, -1)
        return [json.loads(i) for i in items]

    def clear(self) -> None:
        """세션 내역을 삭제한다."""
        self._redis.delete(self._key)

class SessionManager:
    """세션 생성 및 접근을 관리하는 팩토리 클래스"""
    def __init__(self, redis_url: str) -> None:
        self._redis = Redis.from_url(redis_url, decode_responses=True)

    def get_session(self, session_id: str) -> ConversationSession:
        return ConversationSession(self._redis, session_id)
