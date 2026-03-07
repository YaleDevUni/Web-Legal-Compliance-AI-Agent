"""tests/agents/test_service_agent.py — 서비스 규정 에이전트 TDD

테스트 전략:
- mock_llm으로 실제 OpenAI 없이 ServiceAgent 검증
- analyze(code_text) → list[ComplianceReport] 반환
- 결제 코드 감지 → 전자상거래법 조항 참조한 위반 또는 준수 판정
- 사업자 정보 미표시 → violation 탐지
- 결과에 Citation 포함 확인
- 빈 입력 → 빈 리스트 반환
"""
import pytest
from unittest.mock import MagicMock


PAYMENT_CODE = """
def process_payment(user, amount):
    stripe.charge(user.card_token, amount)
    # 환불 정책 없음
"""

NO_BUSINESS_INFO = """
<html>
<body>
  <h1>쇼핑몰</h1>
  <!-- 사업자 등록번호 미표시 -->
</body>
</html>
"""


@pytest.fixture
def service_agent(mock_llm, mocker):
    """ChatOpenAI mock 패치 후 ServiceAgent 초기화"""
    mocker.patch("agents._base_agent.ChatOpenAI", return_value=mock_llm)
    from agents.service_agent import ServiceAgent
    return ServiceAgent()


class TestServiceAgent:
    def test_analyze_returns_list(self, service_agent, mock_llm):
        """analyze() → 리스트 반환"""
        mock_llm.invoke.return_value.content = "violation|환불 정책 미표시|전자상거래법|제17조|EC_17"
        result = service_agent.analyze(PAYMENT_CODE)
        assert isinstance(result, list)

    def test_payment_code_detected(self, service_agent, mock_llm):
        """결제 코드 감지 → 전자상거래법 관련 보고서 반환"""
        mock_llm.invoke.return_value.content = "violation|환불 정책 미표시|전자상거래법|제17조|EC_17"
        reports = service_agent.analyze(PAYMENT_CODE)
        assert len(reports) >= 1

    def test_business_info_missing_violation(self, service_agent, mock_llm):
        """사업자 정보 미표시 → violation 탐지"""
        from core.models import ComplianceStatus
        mock_llm.invoke.return_value.content = "violation|사업자 정보 미표시|전자상거래법|제10조|EC_10"
        reports = service_agent.analyze(NO_BUSINESS_INFO)
        assert any(r.status == ComplianceStatus.VIOLATION for r in reports)

    def test_report_has_citations(self, service_agent, mock_llm):
        """결과 보고서에 Citation 포함"""
        from core.models import Citation
        mock_llm.invoke.return_value.content = "violation|환불 미표시|전자상거래법|제17조|EC_17"
        reports = service_agent.analyze(PAYMENT_CODE)
        for report in reports:
            assert len(report.citations) >= 1
            assert isinstance(report.citations[0], Citation)

    def test_empty_input_returns_empty(self, service_agent):
        """빈 코드 입력 → 빈 리스트 반환"""
        result = service_agent.analyze("")
        assert result == []
