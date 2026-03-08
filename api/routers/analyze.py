"""api/routers/analyze.py — Job Queue 기반 분석 엔드포인트.

흐름:
  POST /api/analyze               → job_id 즉시 반환 + stream:jobs에 enqueue
  GET  /api/analyze/{id}/events   → result:{job_id} 스트림 XREAD → SSE 스트리밍

Race-condition 방지:
  Worker가 result:{job_id}에 XADD하면 메시지가 보존됨.
  SSE가 늦게 연결해도 id=0 부터 읽으므로 유실 없음.
"""
import asyncio
import json
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.dependencies import get_redis_client, get_url_cache
from core.logger import logger

router = APIRouter(prefix="/api", tags=["analyze"])

JOBS_STREAM = "stream:jobs"
RESULT_TTL = 600        # 결과 스트림 보존 시간 (초)
POLL_INTERVAL = 0.1     # XREAD 폴링 간격 (초)
JOB_TIMEOUT = 300       # 최대 대기 시간 (초)


class AnalyzeRequest(BaseModel):
    code_text: str
    url: str | None = None


class EnqueueResponse(BaseModel):
    job_id: str
    cached: bool = False


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ── POST: job enqueue ──────────────────────────────────────────────────────────

@router.post("/analyze", response_model=EnqueueResponse)
async def analyze_enqueue(body: AnalyzeRequest):
    """작업을 Redis Stream에 등록하고 job_id를 즉시 반환."""
    if not body.code_text.strip():
        raise HTTPException(status_code=400, detail="분석할 내용을 입력하세요.")

    rc = get_redis_client()
    if not rc:
        raise HTTPException(status_code=503, detail="Redis 연결 불가")

    # 캐시 확인 — URL 입력이면 result stream에 즉시 기록 후 반환
    url_cache = get_url_cache()
    if url_cache and body.url:
        cached_reports = url_cache.get(body.url)
        if cached_reports is not None:
            job_id = f"cache:{uuid.uuid4().hex}"
            result_key = f"result:{job_id}"
            for report in cached_reports:
                rc.xadd(result_key, {
                    "_event": "report",
                    "data": json.dumps(report.model_dump(mode="json"), ensure_ascii=False),
                })
            rc.xadd(result_key, {"_event": "done", "total": str(len(cached_reports)), "cached": "1"})
            rc.expire(result_key, RESULT_TTL)
            return EnqueueResponse(job_id=job_id, cached=True)

    job_id = uuid.uuid4().hex
    rc.xadd(JOBS_STREAM, {
        "job_id": job_id,
        "code_text": body.code_text,
        "url": body.url or "",
    })
    logger.info(f"[{job_id[:8]}] job enqueued")
    return EnqueueResponse(job_id=job_id)


# ── GET: SSE stream ────────────────────────────────────────────────────────────

@router.get("/analyze/{job_id}/events")
async def analyze_events(job_id: str):
    """result:{job_id} 스트림을 XREAD로 읽어 SSE로 전달."""
    return StreamingResponse(
        _read_result_stream(job_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _read_result_stream(job_id: str):
    rc = get_redis_client()
    if not rc:
        yield _sse("error", {"message": "Redis 연결 불가"})
        return

    result_key = f"result:{job_id}"
    last_id = "0"           # 처음부터 읽음 — 늦게 연결해도 유실 없음
    elapsed = 0.0
    loop = asyncio.get_running_loop()

    try:
        while elapsed < JOB_TIMEOUT:
            # 블로킹 XREAD를 스레드 풀에서 실행 (이벤트 루프 블로킹 방지)
            entries = await loop.run_in_executor(
                None,
                lambda: rc.xread({result_key: last_id}, count=50, block=500),
            )

            if not entries:
                elapsed += 0.5
                continue

            for _key, messages in entries:
                for msg_id, fields in messages:
                    last_id = msg_id
                    event = fields.get("_event", "report")

                    if event == "report":
                        try:
                            data = json.loads(fields["data"])
                        except (KeyError, json.JSONDecodeError):
                            continue
                        yield _sse("report", data)

                    elif event == "done":
                        total = int(fields.get("total", 0))
                        cached = fields.get("cached", "0") == "1"
                        yield _sse("done", {"total": total, "cached": cached})
                        return

                    elif event == "error":
                        yield _sse("error", {"message": fields.get("message", "알 수 없는 오류")})
                        return

            elapsed += 0.0  # XREAD block=500 이 대기시간 역할

        yield _sse("error", {"message": "분석 시간 초과"})

    except Exception as e:
        logger.exception(f"[{job_id[:8]}] SSE 오류:")
        yield _sse("error", {"message": str(e)})
