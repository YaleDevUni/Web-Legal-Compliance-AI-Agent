"""src/workers/agent_worker.py — Redis Stream 컨슈머 워커

흐름:
  Redis Stream 'stream:jobs' consume
    → Orchestrator 실행
      → 에이전트 완료 시마다 Redis Pub/Sub 'result:{job_id}'에 publish
    → done 이벤트 publish
    → XACK

실행:
  uv run python -m workers.agent_worker
  (또는 Docker worker 서비스)
"""
import json
import os
import sys
import signal
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))

import redis as redis_lib

from agents.orchestrator import Orchestrator
from cache.url_cache import URLAnalysisCache
from core.config import Settings
from core.logger import logger
from retrieval.hybrid import HybridRetriever
from qdrant_client import QdrantClient

JOBS_STREAM = "stream:jobs"
CONSUMER_GROUP = "agent-workers"
CONSUMER_NAME = f"worker-{os.getpid()}"
BLOCK_MS = 5_000  # 5초 블로킹 read


class PubSubStream:
    """에이전트 결과를 Redis Pub/Sub으로 실시간 publish하는 stream 어댑터."""

    def __init__(self, redis_client, job_id: str) -> None:
        self._redis = redis_client
        self._channel = f"result:{job_id}"

    def publish(self, agent_name: str, message: dict) -> None:
        payload = {"_event": "report", "_agent": agent_name, **message}
        self._redis.publish(self._channel, json.dumps(payload, ensure_ascii=False))


def _init_resources():
    settings = Settings()
    rc = redis_lib.from_url(settings.redis_url, decode_responses=True)
    rc.ping()

    try:
        qdrant = QdrantClient(url=str(settings.qdrant_url), timeout=30)
        retriever = HybridRetriever(qdrant, collection=settings.qdrant_collection)
    except Exception as e:
        logger.warning(f"HybridRetriever 초기화 실패: {e} — retriever 없이 실행")
        retriever = None

    url_cache = URLAnalysisCache(redis_client=rc)
    return rc, retriever, url_cache


def _ensure_consumer_group(rc):
    try:
        rc.xgroup_create(JOBS_STREAM, CONSUMER_GROUP, id="0", mkstream=True)
        logger.info(f"컨슈머 그룹 '{CONSUMER_GROUP}' 생성됨")
    except redis_lib.exceptions.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise


def _process_job(rc, retriever, url_cache, job_id: str, code_text: str, url: str):
    channel = f"result:{job_id}"
    logger.info(f"[{job_id[:8]}] 분석 시작 (url={url or '-'})")

    try:
        stream = PubSubStream(rc, job_id)
        orch = Orchestrator(retriever=retriever, stream=stream)
        reports = orch.run(code_text)

        # URL 캐싱
        if url and reports:
            url_cache.set(url, reports)

        rc.publish(channel, json.dumps({
            "_event": "done",
            "total": len(reports),
        }))
        logger.info(f"[{job_id[:8]}] 완료: {len(reports)}개 보고서")

    except Exception as e:
        logger.exception(f"[{job_id[:8]}] 분석 오류:")
        rc.publish(channel, json.dumps({
            "_event": "error",
            "message": str(e),
        }))


def run():
    logger.info(f"Worker 시작: {CONSUMER_NAME}")
    rc, retriever, url_cache = _init_resources()
    _ensure_consumer_group(rc)

    # 재시작 시 미처리된 pending 메시지 먼저 처리
    _recover_pending(rc, retriever, url_cache)

    running = True

    def _shutdown(sig, frame):
        nonlocal running
        logger.info("Worker 종료 신호 수신")
        running = False

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    logger.info(f"'{JOBS_STREAM}' 스트림 대기 중...")

    while running:
        try:
            entries = rc.xreadgroup(
                CONSUMER_GROUP, CONSUMER_NAME,
                {JOBS_STREAM: ">"},
                count=1,
                block=BLOCK_MS,
            )
        except redis_lib.exceptions.ConnectionError:
            logger.warning("Redis 연결 끊김, 재연결 대기...")
            time.sleep(3)
            continue

        if not entries:
            continue

        for _stream_key, messages in entries:
            for msg_id, fields in messages:
                job_id = fields.get("job_id", "")
                code_text = fields.get("code_text", "")
                url = fields.get("url", "")

                _process_job(rc, retriever, url_cache, job_id, code_text, url)
                rc.xack(JOBS_STREAM, CONSUMER_GROUP, msg_id)

    logger.info("Worker 종료됨")


def _recover_pending(rc, retriever, url_cache):
    """재시작 후 미ACK 메시지 재처리."""
    pending = rc.xpending_range(JOBS_STREAM, CONSUMER_GROUP, "-", "+", 100)
    if pending:
        logger.info(f"Pending 메시지 {len(pending)}개 재처리 중...")
    for entry in pending:
        msg_id = entry["message_id"]
        msgs = rc.xrange(JOBS_STREAM, msg_id, msg_id)
        for _, fields in msgs:
            job_id = fields.get("job_id", "")
            code_text = fields.get("code_text", "")
            url = fields.get("url", "")
            _process_job(rc, retriever, url_cache, job_id, code_text, url)
            rc.xack(JOBS_STREAM, CONSUMER_GROUP, msg_id)


if __name__ == "__main__":
    run()
