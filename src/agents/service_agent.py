"""agents/service_agent.py — 전자상거래·청소년보호·신용정보 준수 분석 에이전트"""
from langchain_openai import ChatOpenAI

from agents._base_agent import BaseAgent

_SERVICE_PROMPT = (
    "당신은 전자상거래법, 청소년보호법, 신용정보법 전문 컴플라이언스 에이전트입니다. "
    "주어진 코드나 HTML을 분석해 결제 처리, 사업자 정보 표시, 환불 정책, 청소년 연령 인증, 신용정보 처리를 점검하세요. "
    "반드시 다음 형식으로만 응답하세요: "
    "status|description|law_name|article_number|article_id "
    "(status: compliant 또는 violation)"
)


class ServiceAgent(BaseAgent):
    """전자상거래·청소년보호·신용정보 관련 코드 분석 에이전트."""

    _SYSTEM_PROMPT = _SERVICE_PROMPT
