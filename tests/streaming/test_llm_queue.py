"""tests/streaming/test_llm_queue.py — LLMJobQueue TDD

테스트 전략:
- redis.asyncio를 fakeredis.aioredis(또는 mock)로 대체하여 실제 Redis 불필요
- enqueue → job_id 반환 및 XADD 호출 확인
- dequeue → XREADGROUP 호출 및 job dict 반환 확인
- ack → XACK 호출 확인
- publish_chunk → response stream에 XADD 호출 확인
- consume_response → 청크 yield 및 done/error 시 종료 확인
- setup → BUSYGROUP 예외 무시 확인
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# fixture: LLMJobQueue with mocked aioredis
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_redis():
    r = AsyncMock()
    return r


@pytest.fixture
def queue(mock_redis):
    from streaming.llm_queue import LLMJobQueue

    q = LLMJobQueue("redis://localhost:6379")
    q._redis = mock_redis
    return q, mock_redis


# ---------------------------------------------------------------------------
# enqueue / dequeue / ack
# ---------------------------------------------------------------------------

class TestEnqueueDequeue:
    @pytest.mark.asyncio
    async def test_enqueue_returns_job_id(self, queue):
        """enqueue() 후 job_id 반환."""
        q, mock_redis = queue
        job = {"job_id": "abc123", "question": "전세 계약 해지"}
        result = await q.enqueue(job)
        assert result == "abc123"

    @pytest.mark.asyncio
    async def test_enqueue_calls_xadd(self, queue):
        """enqueue() 시 XADD 호출 확인."""
        q, mock_redis = queue
        job = {"job_id": "abc123", "question": "질문"}
        await q.enqueue(job)
        mock_redis.xadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_dequeue_returns_none_when_empty(self, queue):
        """큐가 비어 있으면 None 반환."""
        q, mock_redis = queue
        mock_redis.xreadgroup.return_value = None
        result = await q.dequeue("worker-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_dequeue_returns_msg_id_and_job(self, queue):
        """큐에 job이 있으면 (msg_id, job_dict) 반환."""
        q, mock_redis = queue
        job = {"job_id": "xyz", "question": "임대차"}
        mock_redis.xreadgroup.return_value = [
            ("stream:llm_jobs", [("1-0", {"data": json.dumps(job)})])
        ]
        result = await q.dequeue("worker-1")
        assert result is not None
        msg_id, data = result
        assert msg_id == "1-0"
        assert data["job_id"] == "xyz"

    @pytest.mark.asyncio
    async def test_ack_calls_xack(self, queue):
        """ack() 시 XACK 호출 확인."""
        q, mock_redis = queue
        await q.ack("1-0")
        mock_redis.xack.assert_called_once()


# ---------------------------------------------------------------------------
# publish_chunk / consume_response
# ---------------------------------------------------------------------------

class TestChunkStreaming:
    @pytest.mark.asyncio
    async def test_publish_chunk_calls_xadd(self, queue):
        """publish_chunk() 시 response stream에 XADD 호출."""
        q, mock_redis = queue
        await q.publish_chunk("job1", {"type": "content", "text": "안녕"})
        mock_redis.xadd.assert_called_once()
        key_arg = mock_redis.xadd.call_args[0][0]
        assert "job1" in key_arg

    @pytest.mark.asyncio
    async def test_consume_response_yields_chunks_until_done(self, queue):
        """consume_response()는 done 청크를 받으면 종료된다."""
        q, mock_redis = queue
        chunks = [
            {"type": "content", "text": "안녕"},
            {"type": "content", "text": "하세요"},
            {"type": "done", "session_id": "s1"},
        ]
        mock_redis.xread.side_effect = [
            [("stream:response:job1", [
                ("1-0", {"data": json.dumps(chunks[0])}),
                ("1-1", {"data": json.dumps(chunks[1])}),
                ("1-2", {"data": json.dumps(chunks[2])}),
            ])]
        ]

        received = []
        async for chunk in q.consume_response("job1"):
            received.append(chunk)

        assert len(received) == 3
        assert received[-1]["type"] == "done"

    @pytest.mark.asyncio
    async def test_consume_response_stops_on_error(self, queue):
        """consume_response()는 error 청크를 받으면 종료된다."""
        q, mock_redis = queue
        mock_redis.xread.return_value = [
            ("stream:response:job1", [
                ("1-0", {"data": json.dumps({"type": "error", "message": "fail"})}),
            ])
        ]

        received = []
        async for chunk in q.consume_response("job1"):
            received.append(chunk)

        assert received[0]["type"] == "error"
        assert len(received) == 1


# ---------------------------------------------------------------------------
# setup (Consumer Group)
# ---------------------------------------------------------------------------

class TestSetup:
    @pytest.mark.asyncio
    async def test_setup_calls_xgroup_create(self, queue):
        """setup() 시 XGROUP CREATE 호출."""
        q, mock_redis = queue
        await q.setup()
        mock_redis.xgroup_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_setup_ignores_busygroup_error(self, queue):
        """Consumer Group 이미 존재할 때 예외 없이 통과."""
        q, mock_redis = queue
        mock_redis.xgroup_create.side_effect = Exception("BUSYGROUP")
        # 예외 전파 없어야 함
        await q.setup()
