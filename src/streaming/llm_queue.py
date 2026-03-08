"""src/streaming/llm_queue.py — Redis Streams Consumer Group 기반 LLM 요청 큐

흐름:
  API 워커  → enqueue(job)          → stream:llm_jobs
  LLM 워커  ← dequeue(consumer)     ← stream:llm_jobs  (XREADGROUP, blocking)
  LLM 워커  → publish_chunk(job_id) → stream:response:{job_id}
  SSE 엔드포인트 ← consume_response(job_id) ← stream:response:{job_id}
"""
import json
import asyncio
from typing import Optional, AsyncIterator

import redis.asyncio as aioredis

_QUEUE_KEY = "stream:llm_jobs"
_RESPONSE_PREFIX = "stream:response:"
_CONSUMER_GROUP = "llm_workers"
_RESPONSE_TTL = 3600  # seconds


class LLMJobQueue:
    """Redis Streams Consumer Group 기반 LLM 요청 큐."""

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._redis: Optional[aioredis.Redis] = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(
                self._redis_url, decode_responses=True
            )
        return self._redis

    # ------------------------------------------------------------------
    # Consumer Group 초기화
    # ------------------------------------------------------------------

    async def setup(self) -> None:
        """Consumer Group 생성 (이미 존재하면 무시)."""
        r = await self._get_redis()
        try:
            await r.xgroup_create(_QUEUE_KEY, _CONSUMER_GROUP, id="0", mkstream=True)
        except Exception:
            pass  # BUSYGROUP: group already exists

    # ------------------------------------------------------------------
    # 요청 큐 (Producer / Consumer)
    # ------------------------------------------------------------------

    async def enqueue(self, job: dict) -> str:
        """Job을 큐에 추가하고 job_id 반환."""
        r = await self._get_redis()
        await r.xadd(_QUEUE_KEY, {"data": json.dumps(job, ensure_ascii=False)})
        return job["job_id"]

    async def dequeue(
        self, consumer: str, block_ms: int = 5000
    ) -> Optional[tuple[str, dict]]:
        """Consumer Group에서 다음 job 가져오기 (blocking read).

        Returns:
            (msg_id, job_dict) 또는 타임아웃 시 None
        """
        r = await self._get_redis()
        result = await r.xreadgroup(
            _CONSUMER_GROUP,
            consumer,
            {_QUEUE_KEY: ">"},
            count=1,
            block=block_ms,
        )
        if not result:
            return None
        _key, records = result[0]
        msg_id, fields = records[0]
        return msg_id, json.loads(fields["data"])

    async def ack(self, msg_id: str) -> None:
        """Worker가 job 처리 완료를 확인."""
        r = await self._get_redis()
        await r.xack(_QUEUE_KEY, _CONSUMER_GROUP, msg_id)

    # ------------------------------------------------------------------
    # 응답 스트림 (Worker → SSE)
    # ------------------------------------------------------------------

    async def publish_chunk(self, job_id: str, chunk: dict) -> None:
        """Worker가 처리 결과 청크를 응답 스트림에 발행."""
        r = await self._get_redis()
        key = f"{_RESPONSE_PREFIX}{job_id}"
        await r.xadd(key, {"data": json.dumps(chunk, ensure_ascii=False)})
        await r.expire(key, _RESPONSE_TTL)

    async def consume_response(
        self, job_id: str, timeout_s: int = 120
    ) -> AsyncIterator[dict]:
        """SSE 엔드포인트가 응답 청크를 읽어 yield하는 async generator.

        done 또는 error 청크 수신 시 종료.
        """
        r = await self._get_redis()
        key = f"{_RESPONSE_PREFIX}{job_id}"
        last_id = "0-0"
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout_s

        while loop.time() < deadline:
            results = await r.xread({key: last_id}, count=20, block=3000)
            if not results:
                continue
            _key, records = results[0]
            for msg_id, fields in records:
                last_id = msg_id
                chunk = json.loads(fields["data"])
                yield chunk
                if chunk.get("type") in ("done", "error"):
                    return
