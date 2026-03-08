"""api/routers/analyze.py — Job Queue 기반 분석 엔드포인트.

흐름:
  POST /api/analyze          → job_id 즉시 반환 + Redis Stream에 job enqueue
  GET  /api/analyze/{id}/events → Redis Pub/Sub subscribe → SSE 스트리밍
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

    # 캐시 확인 — URL 입력이면 캐시된 job_id로 즉시 응답
    url_cache = get_url_cache()
    if url_cache and body.url:
        cached = url_cache.get(body.url)
        if cached is not None:
            job_id = f"cached:{uuid.uuid4().hex}"
            # 캐시 결과를 Pub/Sub에 즉시 publish (worker 없이)
            if rc:
                channel = f"result:{job_id}"
                for report in cached:
                    rc.publish(channel, json.dumps({
                        "_event": "report",
                        **report.model_dump(mode="json"),
                    }, ensure_ascii=False))
                rc.publish(channel, json.dumps({
                    "_event": "done", "total": len(cached), "cached": True
                }))
            return EnqueueResponse(job_id=job_id, cached=True)

    job_id = uuid.uuid4().hex
    if rc:
        rc.xadd(JOBS_STREAM, {
            "job_id": job_id,
            "code_text": body.code_text,
            "url": body.url or "",
        })
        logger.info(f"[{job_id[:8]}] job enqueued")
    else:
        raise HTTPException(status_code=503, detail="Redis 연결 불가")

    return EnqueueResponse(job_id=job_id)


# ── GET: SSE subscribe ─────────────────────────────────────────────────────────

@router.get("/analyze/{job_id}/events")
async def analyze_stream(job_id: str):
    """Redis Pub/Sub에서 결과를 subscribe해 SSE로 전달."""
    return StreamingResponse(
        _subscribe(job_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _subscribe(job_id: str):
    rc = get_redis_client()
    if not rc:
        yield _sse("error", {"message": "Redis 연결 불가"})
        return

    channel = f"result:{job_id}"
    pubsub = rc.pubsub()
    pubsub.subscribe(channel)

    try:
        timeout = 300  # 최대 5분 대기
        elapsed = 0.0
        while elapsed < timeout:
            msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
            if msg and msg["type"] == "message":
                try:
                    data = json.loads(msg["data"])
                except (json.JSONDecodeError, TypeError):
                    continue

                event = data.pop("_event", "report")
                yield _sse(event, data)

                if event == "done":
                    break
            else:
                await asyncio.sleep(0.05)
                elapsed += 0.05
        else:
            yield _sse("error", {"message": "분석 시간 초과"})
    except Exception as e:
        logger.exception(f"[{job_id[:8]}] SSE 오류:")
        yield _sse("error", {"message": str(e)})
    finally:
        pubsub.unsubscribe(channel)
        pubsub.close()
