"""tests/agents/test_orchestrator.py — Orchestrator TDD

테스트 전략:
- _determine_website_purpose / _extract_search_query를 mock으로 제어
- _AGENT_MAP의 에이전트 클래스를 mock으로 교체해 analyze() 반환값 지정
- 병렬 실행: 모든 에이전트가 호출되고 결과가 병합됨을 확인
- Redis Stream publish: stream.publish()가 에이전트 수만큼 호출됨을 확인
- stream=None 시 오류 없이 동작 확인
- 빈 입력 → 빈 리스트 반환
- 관련 법규 없을 때 → 빈 리스트 반환
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from core.models import Citation, ComplianceReport, ComplianceStatus


SAMPLE_CODE = "def login(password): db.save(password)"


def _make_report(status=ComplianceStatus.COMPLIANT, description="test"):
    citation = Citation(
        article_id="PA_15",
        law_name="개인정보 보호법",
        article_number="제15조",
        sha256="a" * 64,
        url="https://www.law.go.kr/",
        updated_at=datetime(2024, 1, 1),
    )
    return ComplianceReport(status=status, description=description, citations=[citation])


@pytest.fixture
def mock_agents(mocker):
    """Orchestrator._AGENT_MAP을 mock 팩토리로 교체 (클래스 참조 직접 패치)."""
    privacy_mock = MagicMock()
    security_mock = MagicMock()
    service_mock = MagicMock()
    privacy_mock.analyze.return_value = [_make_report(ComplianceStatus.VIOLATION, "개인정보 위반")]
    security_mock.analyze.return_value = [_make_report(ComplianceStatus.COMPLIANT, "보안 준수")]
    service_mock.analyze.return_value = [_make_report(ComplianceStatus.UNVERIFIABLE, "서비스 확인불가")]

    # _AGENT_MAP의 클래스(팩토리)를 mock으로 교체 — 인스턴스화 시 mock 반환
    from agents.orchestrator import Orchestrator
    mocker.patch.dict(Orchestrator._AGENT_MAP, {
        "개인정보": MagicMock(return_value=privacy_mock),
        "보안": MagicMock(return_value=security_mock),
        "서비스": MagicMock(return_value=service_mock),
    })
    return {"개인정보": privacy_mock, "보안": security_mock, "서비스": service_mock}


@pytest.fixture
def orchestrator(mock_llm, mocker):
    mocker.patch("agents.orchestrator.ChatOpenAI", return_value=mock_llm)
    from agents.orchestrator import Orchestrator
    orch = Orchestrator()
    mocker.patch.object(orch, "_determine_website_purpose",
                        return_value=("로그인 서비스", ["개인정보", "보안", "서비스"]))
    mocker.patch.object(orch, "_extract_search_query", return_value="개인정보 수집 보안")
    return orch


# ── 기본 동작 ─────────────────────────────────────────────────────────────────

class TestOrchestratorBasic:
    def test_run_returns_list(self, orchestrator, mock_agents):
        """run() → 리스트 반환."""
        result = orchestrator.run(SAMPLE_CODE)
        assert isinstance(result, list)

    def test_empty_input_returns_empty(self, orchestrator, mock_agents):
        """빈 입력 → 빈 리스트 반환."""
        result = orchestrator.run("")
        assert result == []

    def test_no_required_laws_returns_empty(self, orchestrator, mock_agents, mocker):
        """관련 법규 없음 → 빈 리스트 반환."""
        mocker.patch.object(orchestrator, "_determine_website_purpose",
                            return_value=("기업 홍보", []))
        result = orchestrator.run(SAMPLE_CODE)
        assert result == []


# ── 병렬 실행 ─────────────────────────────────────────────────────────────────

class TestParallelExecution:
    def test_all_agents_called(self, orchestrator, mock_agents):
        """선택된 모든 에이전트의 analyze()가 호출됨."""
        orchestrator.run(SAMPLE_CODE)
        mock_agents["개인정보"].analyze.assert_called_once()
        mock_agents["보안"].analyze.assert_called_once()
        mock_agents["서비스"].analyze.assert_called_once()

    def test_each_agent_receives_code_text(self, orchestrator, mock_agents):
        """각 에이전트에 code_text가 첫 번째 인자로 전달됨."""
        orchestrator.run(SAMPLE_CODE)
        for agent_mock in mock_agents.values():
            call_args = agent_mock.analyze.call_args
            assert call_args[0][0] == SAMPLE_CODE

    def test_results_merged_from_all_agents(self, orchestrator, mock_agents):
        """3개 에이전트 결과가 모두 병합됨."""
        results = orchestrator.run(SAMPLE_CODE)
        # 각 에이전트가 1개씩 반환 → 총 3개
        assert len(results) == 3

    def test_partial_agents_selected(self, orchestrator, mock_agents, mocker):
        """개인정보+보안만 선택 시 2개 에이전트만 실행됨."""
        mocker.patch.object(orchestrator, "_determine_website_purpose",
                            return_value=("정보 블로그", ["개인정보", "보안"]))
        orchestrator.run(SAMPLE_CODE)
        mock_agents["개인정보"].analyze.assert_called_once()
        mock_agents["보안"].analyze.assert_called_once()
        mock_agents["서비스"].analyze.assert_not_called()


# ── Redis Stream ───────────────────────────────────────────────────────────────

class TestRedisStreamPublish:
    def test_stream_publish_called_per_report(self, mock_llm, mock_agents, mocker):
        """에이전트 결과마다 stream.publish()가 호출됨."""
        mocker.patch("agents.orchestrator.ChatOpenAI", return_value=mock_llm)
        from agents.orchestrator import Orchestrator
        mock_stream = MagicMock()
        orch = Orchestrator(stream=mock_stream)
        mocker.patch.object(orch, "_determine_website_purpose",
                            return_value=("로그인", ["개인정보", "보안", "서비스"]))
        mocker.patch.object(orch, "_extract_search_query", return_value="쿼리")

        orch.run(SAMPLE_CODE)

        # 각 에이전트가 1개 report 반환 → publish 3회
        assert mock_stream.publish.call_count == 3

    def test_stream_publish_uses_law_name_as_channel(self, mock_llm, mock_agents, mocker):
        """stream.publish() 채널이 법규 분야명으로 호출됨."""
        mocker.patch("agents.orchestrator.ChatOpenAI", return_value=mock_llm)
        from agents.orchestrator import Orchestrator
        mock_stream = MagicMock()
        orch = Orchestrator(stream=mock_stream)
        mocker.patch.object(orch, "_determine_website_purpose",
                            return_value=("로그인", ["개인정보"]))
        mocker.patch.object(orch, "_extract_search_query", return_value="쿼리")

        orch.run(SAMPLE_CODE)

        channel_used = mock_stream.publish.call_args[0][0]
        assert channel_used == "개인정보"

    def test_no_stream_no_error(self, orchestrator, mock_agents):
        """stream=None 이어도 오류 없이 동작."""
        assert orchestrator._stream is None
        result = orchestrator.run(SAMPLE_CODE)
        assert isinstance(result, list)
