"""tests/api/test_analyze_queue.py — Job Queue / SSE 엔드포인트 TDD

테스트 전략:
- POST /api/analyze    → job_id 즉시 반환, Redis Stream에 enqueue 확인
- POST (빈 입력)       → 400 오류
- POST (URL 캐시 히트) → cached=True + result stream에 즉시 기록
- GET  /{id}/events   → result stream을 SSE로 변환 확인
- GET  (done 이벤트)   → SSE 종료 확인
- GET  (error 이벤트)  → error SSE 전달
- ResultStream        → XADD 호출 확인
- Worker _process_job → 분석 완료 시 result stream에 done 기록
"""
import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

from fastapi.testclient import TestClient

from core.models import Citation, ComplianceReport, ComplianceStatus


# ── 공통 픽스처 ────────────────────────────────────────────────────────────────

def _make_report(status=ComplianceStatus.VIOLATION, description="테스트 위반"):
    citation = Citation(
        article_id="SA_7",
        law_name="개인정보의 안전성 확보조치 기준",
        article_number="제7조",
        sha256="a" * 64,
        url="https://www.law.go.kr/",
        updated_at=datetime(2025, 1, 1),
    )
    return ComplianceReport(status=status, description=description, citations=[citation])


@pytest.fixture
def mock_redis():
    rc = MagicMock()
    rc.ping.return_value = True
    rc.xadd.return_value = "1772956387663-0"
    rc.xread.return_value = []
    return rc


@pytest.fixture
def app(mock_redis):
    """mock Redis가 주입된 FastAPI 앱."""
    with patch("api.routers.analyze.get_redis_client", return_value=mock_redis), \
         patch("api.routers.analyze.get_url_cache", return_value=None):
        from api.main import app as _app
        yield _app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=True)


# ── POST /api/analyze ─────────────────────────────────────────────────────────

class TestEnqueue:
    def test_returns_job_id(self, client, mock_redis):
        """정상 요청 시 job_id가 반환됨."""
        res = client.post("/api/analyze", json={"code_text": "def f(): pass"})
        assert res.status_code == 200
        data = res.json()
        assert "job_id" in data
        assert len(data["job_id"]) == 32  # uuid4 hex

    def test_job_enqueued_to_stream(self, client, mock_redis):
        """job이 Redis Stream(stream:jobs)에 XADD됨."""
        client.post("/api/analyze", json={"code_text": "def f(): pass"})
        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args
        assert call_args[0][0] == "stream:jobs"
        fields = call_args[0][1]
        assert "job_id" in fields
        assert "code_text" in fields

    def test_empty_input_returns_400(self, client):
        """빈 입력 시 400 오류 반환."""
        res = client.post("/api/analyze", json={"code_text": "   "})
        assert res.status_code == 400

    def test_cached_false_by_default(self, client, mock_redis):
        """캐시 없으면 cached=False."""
        res = client.post("/api/analyze", json={"code_text": "code"})
        assert res.json()["cached"] is False


class TestEnqueueWithCache:
    def test_cache_hit_returns_cached_true(self, client, mock_redis):
        """URL 캐시 히트 시 cached=True 반환."""
        report = _make_report()
        mock_cache = MagicMock()
        mock_cache.get.return_value = [report]

        with patch("api.routers.analyze.get_url_cache", return_value=mock_cache):
            res = client.post("/api/analyze", json={"code_text": "code", "url": "https://example.com"})

        assert res.status_code == 200
        assert res.json()["cached"] is True

    def test_cache_hit_writes_to_result_stream(self, client, mock_redis):
        """URL 캐시 히트 시 result stream에 report+done이 XADD됨."""
        reports = [_make_report(), _make_report(ComplianceStatus.COMPLIANT, "준수")]
        mock_cache = MagicMock()
        mock_cache.get.return_value = reports

        with patch("api.routers.analyze.get_url_cache", return_value=mock_cache):
            client.post("/api/analyze", json={"code_text": "code", "url": "https://example.com"})

        # report 2개 + done 1개 = 3회 XADD
        assert mock_redis.xadd.call_count == 3
        events = [call[0][1]["_event"] for call in mock_redis.xadd.call_args_list]
        assert events.count("report") == 2
        assert events.count("done") == 1

    def test_cache_hit_skips_jobs_stream(self, client, mock_redis):
        """URL 캐시 히트 시 stream:jobs에는 XADD하지 않음."""
        mock_cache = MagicMock()
        mock_cache.get.return_value = [_make_report()]

        with patch("api.routers.analyze.get_url_cache", return_value=mock_cache):
            client.post("/api/analyze", json={"code_text": "code", "url": "https://example.com"})

        xadd_keys = [call[0][0] for call in mock_redis.xadd.call_args_list]
        assert "stream:jobs" not in xadd_keys


# ── GET /api/analyze/{job_id}/events (SSE) ───────────────────────────────────

class TestSSEStream:
    def _make_xread_entries(self, job_id: str, events: list[dict]) -> list:
        """XREAD 반환 형식 시뮬레이션."""
        messages = [(f"177000000{i}-0", e) for i, e in enumerate(events)]
        return [(f"result:{job_id}", messages)]

    def test_report_event_forwarded(self, client, mock_redis):
        """result stream의 report 이벤트가 SSE로 전달됨."""
        job_id = "abc123"
        report = _make_report()
        report_data = json.dumps(report.model_dump(mode="json"), ensure_ascii=False)

        mock_redis.xread.return_value = self._make_xread_entries(job_id, [
            {"_event": "report", "data": report_data},
            {"_event": "done", "total": "1"},
        ])

        res = client.get(f"/api/analyze/{job_id}/events")

        assert res.status_code == 200
        assert "event: report" in res.text
        assert "event: done" in res.text

    def test_done_event_terminates_stream(self, client, mock_redis):
        """done 이벤트 수신 시 SSE 스트림이 종료됨."""
        job_id = "xyz789"
        mock_redis.xread.return_value = self._make_xread_entries(job_id, [
            {"_event": "done", "total": "0"},
        ])

        res = client.get(f"/api/analyze/{job_id}/events")

        assert "event: done" in res.text

    def test_error_event_forwarded(self, client, mock_redis):
        """error 이벤트가 SSE로 전달되고 스트림이 종료됨."""
        job_id = "err001"
        mock_redis.xread.return_value = self._make_xread_entries(job_id, [
            {"_event": "error", "message": "분석 실패"},
        ])

        res = client.get(f"/api/analyze/{job_id}/events")

        assert "event: error" in res.text
        assert "분석 실패" in res.text

    def test_no_redis_returns_error_sse(self):
        """Redis 없을 때 error SSE 반환."""
        with patch("api.routers.analyze.get_redis_client", return_value=None), \
             patch("api.routers.analyze.get_url_cache", return_value=None):
            from api.main import app as _app
            c = TestClient(_app, raise_server_exceptions=True)
            res = c.get("/api/analyze/nojob/events")

        assert "event: error" in res.text


# ── ResultStream (Worker 어댑터) ──────────────────────────────────────────────

class TestResultStream:
    def test_publish_xadds_to_result_key(self):
        """publish() 호출 시 result:{job_id} 스트림에 XADD됨."""
        from workers.agent_worker import ResultStream
        rc = MagicMock()
        stream = ResultStream(rc, "job123")
        report_dict = _make_report().model_dump(mode="json")

        stream.publish("보안", report_dict)

        rc.xadd.assert_called_once()
        key, payload = rc.xadd.call_args[0]
        assert key == "result:job123"
        assert payload["_event"] == "report"
        assert payload["_agent"] == "보안"
        assert json.loads(payload["data"]) == report_dict

    def test_publish_multiple_agents(self):
        """여러 에이전트 결과가 각각 XADD됨."""
        from workers.agent_worker import ResultStream
        rc = MagicMock()
        stream = ResultStream(rc, "multijob")

        stream.publish("개인정보", {"status": "violation"})
        stream.publish("보안", {"status": "compliant"})

        assert rc.xadd.call_count == 2


# ── Worker _process_job ───────────────────────────────────────────────────────

class TestWorkerProcessJob:
    def test_done_event_written_after_analysis(self, mocker):
        """분석 완료 후 result stream에 done 이벤트가 XADD됨."""
        rc = MagicMock()
        mock_cache = MagicMock()
        reports = [_make_report(), _make_report(ComplianceStatus.COMPLIANT, "준수")]

        mock_orch = MagicMock()
        mock_orch.run.return_value = reports
        mocker.patch("workers.agent_worker.Orchestrator", return_value=mock_orch)

        from workers.agent_worker import _process_job
        _process_job(rc, retriever=None, url_cache=mock_cache,
                     job_id="proc001", code_text="code", url="")

        xadd_calls = rc.xadd.call_args_list
        events = [c[0][1]["_event"] for c in xadd_calls]
        assert "done" in events
        done_call = next(c for c in xadd_calls if c[0][1]["_event"] == "done")
        assert done_call[0][1]["total"] == "2"

    def test_expire_set_after_done(self, mocker):
        """분석 완료 후 result stream에 TTL이 설정됨."""
        rc = MagicMock()
        mock_orch = MagicMock()
        mock_orch.run.return_value = [_make_report()]
        mocker.patch("workers.agent_worker.Orchestrator", return_value=mock_orch)

        from workers.agent_worker import _process_job, RESULT_TTL
        _process_job(rc, retriever=None, url_cache=MagicMock(),
                     job_id="expire001", code_text="code", url="")

        rc.expire.assert_called_once_with("result:expire001", RESULT_TTL)

    def test_error_written_on_exception(self, mocker):
        """분석 중 예외 발생 시 error 이벤트가 XADD됨."""
        rc = MagicMock()
        mock_orch = MagicMock()
        mock_orch.run.side_effect = RuntimeError("LLM 오류")
        mocker.patch("workers.agent_worker.Orchestrator", return_value=mock_orch)

        from workers.agent_worker import _process_job
        _process_job(rc, retriever=None, url_cache=MagicMock(),
                     job_id="err002", code_text="code", url="")

        xadd_calls = rc.xadd.call_args_list
        events = [c[0][1]["_event"] for c in xadd_calls]
        assert "error" in events
        error_call = next(c for c in xadd_calls if c[0][1]["_event"] == "error")
        assert "LLM 오류" in error_call[0][1]["message"]

    def test_url_cache_set_on_success(self, mocker):
        """분석 성공 + URL 있으면 URL 캐시에 저장됨."""
        rc = MagicMock()
        mock_cache = MagicMock()
        reports = [_make_report()]
        mock_orch = MagicMock()
        mock_orch.run.return_value = reports
        mocker.patch("workers.agent_worker.Orchestrator", return_value=mock_orch)

        from workers.agent_worker import _process_job
        _process_job(rc, retriever=None, url_cache=mock_cache,
                     job_id="cache001", code_text="code", url="https://example.com")

        mock_cache.set.assert_called_once_with("https://example.com", reports)

    def test_url_cache_not_set_when_empty_url(self, mocker):
        """URL이 빈 문자열이면 캐시에 저장하지 않음."""
        rc = MagicMock()
        mock_cache = MagicMock()
        mock_orch = MagicMock()
        mock_orch.run.return_value = [_make_report()]
        mocker.patch("workers.agent_worker.Orchestrator", return_value=mock_orch)

        from workers.agent_worker import _process_job
        _process_job(rc, retriever=None, url_cache=mock_cache,
                     job_id="nocache", code_text="code", url="")

        mock_cache.set.assert_not_called()
