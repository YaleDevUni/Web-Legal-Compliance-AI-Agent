"""api/routers/chat.py — 실시간 법률 상담 엔드포인트 (SSE)

요청 처리 흐름:
  1. [캐시 확인] SemanticCache.get() → 히트 시 즉시 스트리밍 후 종료
  2. [큐 enqueue] LLMJobQueue.enqueue(job)
  3. [응답 스트리밍] LLMJobQueue.consume_response() → SSE 청크 전달
  4. [세션 저장] 완료 후 Redis에 assistant 메시지 저장
  5. [캐시 저장] SemanticCache.set() 로 다음 유사 질문에 재활용
"""
import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.dependencies import (
    get_llm_queue,
    get_semantic_cache,
    get_session_manager,
)
from cache.semantic_cache import SemanticCache
from core.logger import logger
from streaming.llm_queue import LLMJobQueue

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    citation_offset: int = 0


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat")
async def chat(
    body: ChatRequest,
    sm=Depends(get_session_manager),
    queue: LLMJobQueue = Depends(get_llm_queue),
    cache: Optional[SemanticCache] = Depends(get_semantic_cache),
):
    """질문에 대해 SSE 스트리밍으로 답변하고 최종 인용 정보를 전달한다."""
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="질문을 입력하세요.")

    session_id = body.session_id or uuid.uuid4().hex
    session = sm.get_session(session_id)
    history = session.get_history()

    async def event_generator():
        try:
            session.add_message("user", body.question)

            # ── 1. 시맨틱 캐시 확인 ──────────────────────────────────────
            if cache:
                cached = await cache.get(body.question)
                if cached:
                    logger.info(f"캐시 히트: {body.question[:30]}...")
                    citations_data = cached.get("citations", [])
                    full_answer = cached.get("answer", "")
                    related = cached.get("related_articles", [])

                    yield _sse("citations", {
                        "citations": citations_data,
                        "related_articles": related,
                        "session_id": session_id,
                    })
                    yield _sse("content", {"text": full_answer})
                    yield _sse("citations", {
                        "citations": citations_data,
                        "related_articles": related,
                        "session_id": session_id,
                        "full_answer": full_answer,
                    })
                    session.add_message("assistant", full_answer, citations=citations_data)
                    yield _sse("done", {"session_id": session_id, "cached": True})
                    return

            # ── 2. LLM 큐에 job enqueue ───────────────────────────────────
            job_id = uuid.uuid4().hex
            await queue.enqueue({
                "job_id": job_id,
                "question": body.question,
                "session_id": session_id,
                "history": history,
                "citation_offset": body.citation_offset,
            })

            # ── 3. 응답 스트림 소비 + SSE 전달 ───────────────────────────
            full_answer = ""
            current_citations = []
            current_related = []

            async for chunk in queue.consume_response(job_id):
                chunk_type = chunk.get("type")

                if chunk_type == "content":
                    full_answer += chunk.get("text", "")
                    yield _sse("content", {"text": chunk["text"]})

                elif chunk_type == "citations":
                    current_citations = chunk.get("citations", [])
                    current_related = chunk.get("related_articles", [])
                    payload = {
                        "citations": current_citations,
                        "related_articles": current_related,
                        "session_id": session_id,
                    }
                    if chunk.get("full_answer"):
                        full_answer = chunk["full_answer"]
                        payload["full_answer"] = full_answer
                    yield _sse("citations", payload)

                elif chunk_type == "done":
                    break

                elif chunk_type == "error":
                    yield _sse("error", {"message": chunk.get("message", "오류가 발생했습니다.")})
                    return

            # ── 4. 세션 저장 ──────────────────────────────────────────────
            if full_answer:
                session.add_message("assistant", full_answer, citations=current_citations)

                # ── 5. 캐시 저장 ─────────────────────────────────────────
                if cache:
                    await cache.set(body.question, {
                        "answer": full_answer,
                        "citations": current_citations,
                        "related_articles": current_related,
                    })

            yield _sse("done", {"session_id": session_id})

        except Exception as e:
            logger.exception("Chat SSE Error:")
            yield _sse("error", {"message": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/sessions/{session_id}/history")
async def get_history(session_id: str, sm=Depends(get_session_manager)):
    """특정 세션의 대화 내역을 가져온다."""
    session = sm.get_session(session_id)
    return session.get_history()


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, sm=Depends(get_session_manager)):
    """세션을 삭제한다."""
    session = sm.get_session(session_id)
    session.clear()
    return {"status": "deleted"}
