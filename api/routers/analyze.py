"""api/routers/analyze.py — SSE 스트리밍 분석 엔드포인트."""
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agents.orchestrator import Orchestrator
from api.dependencies import get_retriever, get_url_cache, get_stream
from core.logger import logger

router = APIRouter(prefix="/api", tags=["analyze"])

_executor = ThreadPoolExecutor(max_workers=8)


class AnalyzeRequest(BaseModel):
    code_text: str
    url: str | None = None  # URL 탭 입력이면 캐시 키로 사용


def _run_analysis(code_text: str) -> list:
    retriever = get_retriever()
    stream = get_stream()
    orch = Orchestrator(retriever=retriever, stream=stream)
    return orch.run(code_text)


async def _event_stream(body: AnalyzeRequest):
    # 1. 캐시 확인
    url_cache = get_url_cache()
    if url_cache and body.url:
        cached = url_cache.get(body.url)
        if cached is not None:
            yield _sse("cached", True)
            for report in cached:
                yield _sse("report", report.model_dump(mode="json"))
            yield _sse("done", {"total": len(cached)})
            return

    yield _sse("status", {"message": "분석 시작..."})

    # 2. 별도 스레드에서 분석 실행
    loop = asyncio.get_event_loop()
    try:
        reports = await loop.run_in_executor(
            _executor, _run_analysis, body.code_text
        )
    except Exception as e:
        logger.exception("분석 중 오류:")
        yield _sse("error", {"message": str(e)})
        return

    # 3. 결과 캐싱
    if url_cache and body.url and reports:
        url_cache.set(body.url, reports)

    # 4. 결과 스트리밍
    for report in reports:
        yield _sse("report", report.model_dump(mode="json"))

    yield _sse("done", {"total": len(reports)})


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/analyze")
async def analyze_endpoint(body: AnalyzeRequest):
    if not body.code_text.strip():
        return StreamingResponse(
            iter([_sse("done", {"total": 0})]),
            media_type="text/event-stream",
        )

    return StreamingResponse(
        _event_stream(body),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
