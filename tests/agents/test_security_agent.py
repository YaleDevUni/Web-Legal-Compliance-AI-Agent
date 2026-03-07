"""tests/agents/test_security_agent.py — 보안 에이전트 TDD

테스트 전략:
- mock_llm으로 실제 OpenAI 없이 SecurityAgent 검증
- analyze(code_text) → list[ComplianceReport] 반환
- 평문 비밀번호 저장 패턴 → violation 탐지
- HTTPS 리다이렉트 미적용 → violation 탐지
- 결과에 Citation 포함 확인
- 빈 입력 → 빈 리스트 반환
"""
import pytest
from unittest.mock import MagicMock


PLAIN_PASSWORD_CODE = """
def save_user(user, password):
    db.execute("INSERT INTO users (name, password) VALUES (?, ?)", (user, password))
"""

HTTPS_MISSING_CODE = """
app = Flask(__name__)
# no SSL/HTTPS redirect configured
"""


@pytest.fixture
def security_agent(mock_llm, mocker):
    """ChatOpenAI mock 패치 후 SecurityAgent 초기화"""
    mocker.patch("agents._base_agent.ChatOpenAI", return_value=mock_llm)
    from agents.security_agent import SecurityAgent
    return SecurityAgent()


class TestSecurityAgent:
    def test_analyze_returns_list(self, security_agent, mock_llm):
        """analyze() → 리스트 반환"""
        mock_llm.invoke.return_value.content = "violation|평문 비밀번호 저장|안전성확보조치기준|제7조|SA_7"
        result = security_agent.analyze(PLAIN_PASSWORD_CODE)
        assert isinstance(result, list)

    def test_plain_password_violation(self, security_agent, mock_llm):
        """평문 비밀번호 패턴 → violation 탐지"""
        from core.models import ComplianceStatus
        mock_llm.invoke.return_value.content = "violation|평문 비밀번호 저장|안전성확보조치기준|제7조|SA_7"
        reports = security_agent.analyze(PLAIN_PASSWORD_CODE)
        assert any(r.status == ComplianceStatus.VIOLATION for r in reports)

    def test_https_missing_violation(self, security_agent, mock_llm):
        """HTTPS 미적용 → violation 탐지"""
        from core.models import ComplianceStatus
        mock_llm.invoke.return_value.content = "violation|HTTPS 미적용|정보통신망법|제28조|IC_28"
        reports = security_agent.analyze(HTTPS_MISSING_CODE)
        assert any(r.status == ComplianceStatus.VIOLATION for r in reports)

    def test_report_has_citations(self, security_agent, mock_llm):
        """결과 보고서에 Citation 포함"""
        from core.models import Citation
        mock_llm.invoke.return_value.content = "violation|SQL 인젝션|안전성확보조치기준|제7조|SA_7"
        reports = security_agent.analyze(PLAIN_PASSWORD_CODE)
        for report in reports:
            assert len(report.citations) >= 1
            assert isinstance(report.citations[0], Citation)

    def test_empty_input_returns_empty(self, security_agent):
        """빈 코드 입력 → 빈 리스트 반환"""
        result = security_agent.analyze("")
        assert result == []
