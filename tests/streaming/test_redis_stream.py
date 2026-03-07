"""tests/streaming/test_redis_stream.py — Redis Stream 메시지 발행/구독 TDD

테스트 전략:
- mock_redis로 실제 Redis 없이 RedisStream 검증
- publish(channel, message) → Redis XADD 호출 확인
- consume(channel) → Redis XREAD 결과 반환 확인
- 메시지 형식: {"agent": str, "content": str} JSON
- 에이전트별 채널 분리: stream:{channel} 키 사용
- XREAD 결과 없음 → 빈 리스트 반환
"""
import json
import pytest


@pytest.fixture
def stream(mock_redis):
    """RedisStream 초기화"""
    from streaming.redis_stream import RedisStream
    return RedisStream(redis_client=mock_redis)


class TestRedisStream:
    def test_publish_calls_xadd(self, stream, mock_redis):
        """publish() 호출 시 Redis XADD 호출됨"""
        stream.publish("privacy", {"agent": "privacy", "content": "분석 완료"})
        mock_redis.xadd.assert_called_once()

    def test_publish_uses_correct_stream_key(self, stream, mock_redis):
        """publish() 시 'stream:privacy' 키로 XADD 호출됨"""
        stream.publish("privacy", {"agent": "privacy", "content": "ok"})
        args, kwargs = mock_redis.xadd.call_args
        assert args[0] == "stream:privacy"

    def test_publish_serializes_as_json(self, stream, mock_redis):
        """publish() 메시지가 JSON 직렬화되어 저장됨"""
        msg = {"agent": "security", "content": "위반 감지"}
        stream.publish("security", msg)
        args, kwargs = mock_redis.xadd.call_args
        payload = args[1]
        assert "data" in payload
        parsed = json.loads(payload["data"])
        assert parsed == msg

    def test_consume_calls_xread(self, stream, mock_redis):
        """consume() 호출 시 Redis XREAD 호출됨"""
        mock_redis.xread.return_value = []
        stream.consume("privacy")
        mock_redis.xread.assert_called_once()

    def test_consume_empty_returns_empty(self, stream, mock_redis):
        """XREAD 결과 없음 → 빈 리스트 반환"""
        mock_redis.xread.return_value = []
        result = stream.consume("privacy")
        assert result == []

    def test_consume_returns_deserialized_messages(self, stream, mock_redis):
        """XREAD 결과 → JSON 역직렬화된 메시지 리스트 반환"""
        msg = {"agent": "privacy", "content": "분석 결과"}
        mock_redis.xread.return_value = [
            (b"stream:privacy", [(b"1-0", {b"data": json.dumps(msg).encode()})])
        ]
        result = stream.consume("privacy")
        assert len(result) == 1
        assert result[0] == msg
