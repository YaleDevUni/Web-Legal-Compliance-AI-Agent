"""tests/worker/test_llm_worker.py — LLMWorker TDD

테스트 전략:
- agent.aask()를 async generator mock으로 대체
- _process() 정상 흐름: 청크 발행 → done 발행 → ack 호출
- _process() 오류 흐름: error 청크 발행 → ack 호출 (예외 전파 없음)
- Citation 객체 → dict 직렬화 확인 (citations 타입 청크)
- setup 호출 여부 확인
"""
import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, call


# ---------------------------------------------------------------------------
# helper: async generator
# ---------------------------------------------------------------------------

async def _agen(*items):
    for item in items:
        yield item


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_queue():
    q = MagicMock()
    q.setup = AsyncMock()
    q.dequeue = AsyncMock()
    q.ack = AsyncMock()
    q.publish_chunk = AsyncMock()
    return q


@pytest.fixture
def mock_agent():
    return MagicMock()


@pytest.fixture
def worker(mock_queue, mock_agent):
    from worker.llm_worker import LLMWorker
    return LLMWorker(queue=mock_queue, agent=mock_agent), mock_queue, mock_agent


# ---------------------------------------------------------------------------
# _process 정상 흐름
# ---------------------------------------------------------------------------

class TestProcessNormal:
    @pytest.mark.asyncio
    async def test_process_publishes_content_and_done(self, worker):
        """정상 흐름: content 청크 발행 후 done 청크 발행."""
        w, mock_queue, mock_agent = worker
        chunks = [
            {"type": "content", "text": "안녕"},
            {"type": "content", "text": "하세요"},
        ]
        mock_agent.aask = MagicMock(return_value=_agen(*chunks))

        await w._process("msg-1", {"job_id": "j1", "question": "질문", "session_id": "s1", "history": []})

        assert mock_queue.publish_chunk.call_count == 3  # 2 content + 1 done
        last_call = mock_queue.publish_chunk.call_args_list[-1]
        published = last_call[0][1]
        assert published["type"] == "done"

    @pytest.mark.asyncio
    async def test_process_acks_after_completion(self, worker):
        """처리 완료 후 반드시 XACK 호출."""
        w, mock_queue, mock_agent = worker
        mock_agent.aask = MagicMock(return_value=_agen({"type": "content", "text": "ok"}))

        await w._process("msg-1", {"job_id": "j1", "question": "q", "session_id": "s1", "history": []})

        mock_queue.ack.assert_called_once_with("msg-1")

    @pytest.mark.asyncio
    async def test_process_serializes_citations(self, worker):
        """citations 청크의 Citation 객체를 dict로 직렬화하여 발행."""
        w, mock_queue, mock_agent = worker

        from core.models import Citation
        citation = Citation(
            article_id="art-1",
            law_name="주택임대차보호법",
            article_number="제3조",
            sha256="a" * 64,
            url="https://www.law.go.kr/",
            updated_at=datetime(2024, 1, 1),
            article_content="임차인은...",
        )
        chunks = [
            {"type": "citations", "citations": [citation], "related_articles": [], "full_answer": ""},
        ]
        mock_agent.aask = MagicMock(return_value=_agen(*chunks))

        await w._process("msg-1", {"job_id": "j1", "question": "q", "session_id": "s1", "history": []})

        published = mock_queue.publish_chunk.call_args_list[0][0][1]
        assert published["type"] == "citations"
        # Citation 객체가 dict로 변환되어야 함
        assert isinstance(published["citations"][0], dict)
        assert published["citations"][0]["law_name"] == "주택임대차보호법"


# ---------------------------------------------------------------------------
# _process 오류 흐름
# ---------------------------------------------------------------------------

class TestProcessError:
    @pytest.mark.asyncio
    async def test_process_publishes_error_on_exception(self, worker):
        """agent.aask() 예외 시 error 청크 발행."""
        w, mock_queue, mock_agent = worker

        async def failing_gen(*args, **kwargs):
            raise RuntimeError("LLM 호출 실패")
            yield  # make it a generator

        mock_agent.aask = MagicMock(return_value=failing_gen())

        await w._process("msg-1", {"job_id": "j1", "question": "q", "session_id": "s1", "history": []})

        calls = [c[0][1] for c in mock_queue.publish_chunk.call_args_list]
        error_chunks = [c for c in calls if c.get("type") == "error"]
        assert len(error_chunks) == 1

    @pytest.mark.asyncio
    async def test_process_acks_even_on_error(self, worker):
        """오류 발생해도 반드시 XACK 호출 (finally 보장)."""
        w, mock_queue, mock_agent = worker

        async def failing_gen(*args, **kwargs):
            raise RuntimeError("fail")
            yield

        mock_agent.aask = MagicMock(return_value=failing_gen())

        await w._process("msg-1", {"job_id": "j1", "question": "q", "session_id": "s1", "history": []})

        mock_queue.ack.assert_called_once_with("msg-1")
