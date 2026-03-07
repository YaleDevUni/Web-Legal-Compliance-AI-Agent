"""streaming/redis_stream.py — Redis Streams 기반 에이전트 결과 발행/구독"""
import json


class RedisStream:
    """Redis Streams를 사용한 에이전트별 채널 메시지 발행/구독."""

    _PREFIX = "stream:"

    def __init__(self, redis_client) -> None:
        self._redis = redis_client

    def publish(self, channel: str, message: dict) -> None:
        """message를 JSON 직렬화 후 stream:{channel}에 XADD."""
        key = f"{self._PREFIX}{channel}"
        self._redis.xadd(key, {"data": json.dumps(message)})

    def consume(self, channel: str, count: int = 10) -> list[dict]:
        """stream:{channel}에서 XREAD 후 JSON 역직렬화된 메시지 리스트 반환."""
        key = f"{self._PREFIX}{channel}"
        entries = self._redis.xread({key: "0-0"}, count=count)
        messages: list[dict] = []
        for _stream_key, records in (entries or []):
            for _msg_id, fields in records:
                data = fields.get(b"data") or fields.get("data")
                if data:
                    messages.append(json.loads(data))
        return messages
