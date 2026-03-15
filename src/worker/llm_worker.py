"""src/worker/llm_worker.py — LLM 요청 큐 백그라운드 워커

동작:
  1. Redis Stream 큐(LLMJobQueue)에서 job을 XREADGROUP blocking read
  2. LegalReasoningAgent.aask()로 LLM 추론 실행
  3. citations 청크의 Citation 객체를 JSON-직렬화 가능한 dict로 변환
  4. 결과 청크를 stream:response:{job_id}에 발행
  5. 완료/오류 시 done/error 청크 발행 + XACK
"""
import asyncio
import os
from core.logger import logger
from streaming.llm_queue import LLMJobQueue


class LLMWorker:
    """Redis Stream 기반 LLM 요청 처리 워커."""

    def __init__(self, queue: LLMJobQueue, agent) -> None:
        self._queue = queue
        self._agent = agent
        self._running = False
        self._name = f"worker-{os.getpid()}"

    async def start(self) -> None:
        """Consumer Group 초기화 후 무한 루프로 job 처리."""
        self._running = True
        await self._queue.setup()
        logger.info(f"LLM Worker [{self._name}] 시작됨")
        while self._running:
            try:
                result = await self._queue.dequeue(self._name)
                if result is None:
                    continue
                msg_id, job = result
                asyncio.create_task(self._process(msg_id, job))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker 루프 오류: {e}")
                await asyncio.sleep(1)
        logger.info(f"LLM Worker [{self._name}] 종료됨")

    def stop(self) -> None:
        self._running = False

    async def _process(self, msg_id: str, job: dict) -> None:
        """단일 job 처리: 추론 → 청크 발행 → ACK."""
        job_id = job["job_id"]
        question = job["question"]
        session_id = job.get("session_id", "default")
        history = job.get("history", [])
        citation_offset = job.get("citation_offset", 0)

        try:
            async for chunk in self._agent.aask(question, session_id, history, citation_offset):
                chunk = self._serialize_chunk(chunk)
                await self._queue.publish_chunk(job_id, chunk)
            await self._queue.publish_chunk(
                job_id, {"type": "done", "session_id": session_id}
            )
        except Exception as e:
            logger.error(f"Worker 처리 오류 job={job_id}: {e}")
            await self._queue.publish_chunk(
                job_id, {"type": "error", "message": str(e)}
            )
        finally:
            await self._queue.ack(msg_id)

    @staticmethod
    def _serialize_citations(items: list) -> list:
        return [c.model_dump(mode="json") if hasattr(c, "model_dump") else c for c in items]

    @classmethod
    def _serialize_chunk(cls, chunk: dict) -> dict:
        """citations 청크의 Citation 객체를 JSON 직렬화 가능한 dict로 변환."""
        if chunk.get("type") != "citations":
            return chunk
        result = {**chunk}
        result["citations"] = cls._serialize_citations(chunk.get("citations", []))
        if "related_citations" in chunk:
            result["related_citations"] = cls._serialize_citations(chunk.get("related_citations", []))
        return result
