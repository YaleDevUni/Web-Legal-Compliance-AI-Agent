"""tests/agents/test_orchestrator.py — Orchestrator 에이전트 TDD

테스트 전략:
- mock으로 3개 서브 에이전트(privacy, security, service) 교체
- run(code_text) → list[ComplianceReport] 병합 반환
- 3개 에이전트 모두 호출되는지 확인
- 각 에이전트 결과가 병합됨 확인
- 빈 입력 → 빈 리스트 반환
"""
import pytest
from unittest.mock import MagicMock, patch


SAMPLE_CODE = "def login(): pass"


@pytest.fixture
def orchestrator(mock_llm, mocker):
    """3개 에이전트를 mock으로 교체 후 Orchestrator 초기화"""
    mocker.patch("agents._base_agent.ChatOpenAI", return_value=mock_llm)
    mocker.patch("agents.orchestrator.ChatOpenAI", return_value=mock_llm)
    from agents.orchestrator import Orchestrator
    return Orchestrator()


class TestOrchestrator:
    def test_run_returns_list(self, orchestrator, mocker):
        """run() → 리스트 반환"""
        mocker.patch.object(orchestrator.privacy_agent, "analyze", return_value=[])
        mocker.patch.object(orchestrator.security_agent, "analyze", return_value=[])
        mocker.patch.object(orchestrator.service_agent, "analyze", return_value=[])
        result = orchestrator.run(SAMPLE_CODE)
        assert isinstance(result, list)

    def test_all_agents_called(self, orchestrator, mocker):
        """3개 에이전트 analyze() 모두 호출됨 (search_query kwarg 포함)"""
        p = mocker.patch.object(orchestrator.privacy_agent, "analyze", return_value=[])
        s = mocker.patch.object(orchestrator.security_agent, "analyze", return_value=[])
        sv = mocker.patch.object(orchestrator.service_agent, "analyze", return_value=[])
        orchestrator.run(SAMPLE_CODE)
        # code_text는 첫 번째 인자로, search_query는 kwarg로 전달됨
        assert p.call_args[0][0] == SAMPLE_CODE
        assert s.call_args[0][0] == SAMPLE_CODE
        assert sv.call_args[0][0] == SAMPLE_CODE

    def test_results_merged(self, orchestrator, mocker):
        """각 에이전트 결과가 하나의 리스트로 병합됨"""
        from core.models import ComplianceReport, ComplianceStatus, Citation
        from datetime import datetime

        def _mock_report(status):
            citation = Citation(
                article_id="PA_3",
                law_name="개인정보 보호법",
                article_number="제3조",
                sha256="a" * 64,
                url="https://www.law.go.kr/",
                updated_at=datetime(2024, 1, 1),
            )
            return ComplianceReport(
                status=status,
                description="test",
                citations=[citation],
            )

        mocker.patch.object(
            orchestrator.privacy_agent, "analyze",
            return_value=[_mock_report(ComplianceStatus.COMPLIANT)],
        )
        mocker.patch.object(
            orchestrator.security_agent, "analyze",
            return_value=[_mock_report(ComplianceStatus.VIOLATION)],
        )
        mocker.patch.object(
            orchestrator.service_agent, "analyze",
            return_value=[_mock_report(ComplianceStatus.COMPLIANT)],
        )
        results = orchestrator.run(SAMPLE_CODE)
        assert len(results) == 3

    def test_empty_input_returns_empty(self, orchestrator, mocker):
        """빈 입력 → 빈 리스트 반환"""
        mocker.patch.object(orchestrator.privacy_agent, "analyze", return_value=[])
        mocker.patch.object(orchestrator.security_agent, "analyze", return_value=[])
        mocker.patch.object(orchestrator.service_agent, "analyze", return_value=[])
        result = orchestrator.run("")
        assert result == []
