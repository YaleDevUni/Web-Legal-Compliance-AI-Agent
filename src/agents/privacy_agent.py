"""agents/privacy_agent.py — 개인정보 보호법 준수 분석 에이전트"""
from langchain_openai import ChatOpenAI

from agents._base_agent import BaseAgent

_PRIVACY_PROMPT = (
    "당신은 한국 개인정보 보호법 전문 컴플라이언스 에이전트입니다. "
    "주어진 코드를 분석해 개인정보 수집 동의, 민감정보 처리, 보유기간, 마케팅 동의 분리 등을 점검하세요. "
    "반드시 다음 형식으로만 응답하세요: "
    "status|description|law_name|article_number|article_id|code_snippet "
    "(status: compliant 또는 violation, "
    "code_snippet: violation 시 문제가 된 코드 원문 1~3줄, compliant 시 빈 문자열)"
)


class PrivacyAgent(BaseAgent):
    """개인정보 보호법 관련 코드 분석 에이전트."""

    _SYSTEM_PROMPT = _PRIVACY_PROMPT
