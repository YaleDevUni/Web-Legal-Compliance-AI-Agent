"""agents/service_agent.py — 전자상거래·청소년보호·신용정보 준수 분석 에이전트"""
from agents._base_agent import BaseAgent

_SERVICE_PROMPT = (
    "당신은 전자상거래법·청소년보호법 전문 컴플라이언스 에이전트입니다. "
    "주어진 코드/HTML에서 사업자 정보 미표시, 청약철회 미고지, 결제 처리, 청소년 연령 인증 누락만 점검하세요. "
    "개인정보 수집·민감정보 처리는 다른 에이전트 담당입니다. 여기서는 전자상거래·청소년보호 서비스 규정만 확인하세요."
)


class ServiceAgent(BaseAgent):
    """전자상거래·청소년보호·신용정보 관련 코드 분석 에이전트."""

    _SYSTEM_PROMPT = _SERVICE_PROMPT
    _RELEVANT_PREFIXES = ["EC_", "YP_"]
    _SEARCH_DOMAIN_HINT = "전자상거래 사업자정보 청약철회 환불 청소년 연령인증 결제"
