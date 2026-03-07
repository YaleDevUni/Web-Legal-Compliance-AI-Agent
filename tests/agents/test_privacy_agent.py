"""tests/agents/test_privacy_agent.py — 개인정보 보호 에이전트 TDD

테스트 전략:
- mock_llm으로 실제 OpenAI 없이 PrivacyAgent 검증
- analyze(code_text) → list[ComplianceReport] 반환
- 동의 코드 존재 시 준수(compliant) 판정
- 민감정보 처리 코드 감지 시 위반(violation) 판정
- 결과에 Citation 포함 확인
- 빈 입력 → 빈 리스트 반환
"""
import pytest
from unittest.mock import MagicMock


CONSENT_CODE = """
def get_user_consent():
    if user.agrees_to_privacy_policy:
        collect_personal_info(user)
"""

SENSITIVE_CODE = """
def process_health_data(user):
    db.save(user.health_records)  # 민감정보 처리
"""


@pytest.fixture
def privacy_agent(mock_llm, mocker):
    """ChatOpenAI mock 패치 후 PrivacyAgent 초기화"""
    mocker.patch("agents._base_agent.ChatOpenAI", return_value=mock_llm)
    from agents.privacy_agent import PrivacyAgent
    return PrivacyAgent()


class TestPrivacyAgent:
    def test_analyze_returns_list(self, privacy_agent, mock_llm):
        """analyze() → 리스트 반환"""
        mock_llm.invoke.return_value.content = "compliant|동의 코드 확인됨|개인정보 보호법|제15조|PA_15"
        result = privacy_agent.analyze(CONSENT_CODE)
        assert isinstance(result, list)

    def test_compliant_detection(self, privacy_agent, mock_llm):
        """동의 코드 존재 → compliant 상태 반환"""
        from core.models import ComplianceStatus
        mock_llm.invoke.return_value.content = "compliant|동의 코드 확인됨|개인정보 보호법|제15조|PA_15"
        reports = privacy_agent.analyze(CONSENT_CODE)
        assert len(reports) >= 1
        assert any(r.status == ComplianceStatus.COMPLIANT for r in reports)

    def test_violation_detection(self, privacy_agent, mock_llm):
        """민감정보 처리 코드 → violation 상태 반환"""
        from core.models import ComplianceStatus
        mock_llm.invoke.return_value.content = "violation|민감정보 무단 처리|개인정보 보호법|제23조|PA_23"
        reports = privacy_agent.analyze(SENSITIVE_CODE)
        assert any(r.status == ComplianceStatus.VIOLATION for r in reports)

    def test_report_has_citations(self, privacy_agent, mock_llm):
        """결과 보고서에 Citation 포함"""
        from core.models import Citation
        mock_llm.invoke.return_value.content = "compliant|동의 확인|개인정보 보호법|제15조|PA_15"
        reports = privacy_agent.analyze(CONSENT_CODE)
        for report in reports:
            assert len(report.citations) >= 1
            assert isinstance(report.citations[0], Citation)

    def test_empty_input_returns_empty(self, privacy_agent):
        """빈 코드 입력 → 빈 리스트 반환"""
        result = privacy_agent.analyze("")
        assert result == []
