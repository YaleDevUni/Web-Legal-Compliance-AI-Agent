"""src/api/routers/chat.py — 실시간 법률 상담 엔드포인트 (SSE)"""
import asyncio
import json
import uuid
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.dependencies import get_legal_agent, get_session_manager
from core.logger import logger
from core.models import LegalAnswer

router = APIRouter(prefix="/api", tags=["chat"])

class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None

def _sse(event: str, data: any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

@router.post("/chat")
async def chat(
    body: ChatRequest,
    agent = Depends(get_legal_agent),
    sm = Depends(get_session_manager)
):
    """질문에 대해 SSE 스트리밍으로 답변하고 최종 인용 정보를 전달한다."""
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="질문을 입력하세요.")

    session_id = body.session_id or uuid.uuid4().hex
    session = sm.get_session(session_id)
    history = session.get_history()

    async def event_generator():
        try:
            # 1. 사용자 메시지 저장
            session.add_message("user", body.question)
            
            full_answer = ""
            # 2. 에이전트 비동기 스트림 실행
            async for chunk in agent.aask(body.question, session_id, history):
                if chunk["type"] == "content":
                    # 토큰 단위 전송
                    yield _sse("content", {"text": chunk["text"]})
                elif chunk["type"] == "citations":
                    # 최종 인용 정보 전송
                    citations_data = [c.model_dump(mode="json") for c in chunk["citations"]]
                    yield _sse("citations", {
                        "citations": citations_data,
                        "related_articles": chunk["related_articles"],
                        "session_id": session_id
                    })
                    full_answer = chunk["full_answer"]
            
            # 3. AI 답변 저장 (최종 합본)
            if full_answer:
                session.add_message("assistant", full_answer)
            
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
async def get_history(session_id: str, sm = Depends(get_session_manager)):
    """특정 세션의 대화 내역을 가져온다."""
    session = sm.get_session(session_id)
    return session.get_history()

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, sm = Depends(get_session_manager)):
    """세션을 삭제한다."""
    session = sm.get_session(session_id)
    session.clear()
    return {"status": "deleted"}
