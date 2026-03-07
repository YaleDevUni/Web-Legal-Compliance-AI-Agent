"""agents/security_agent.py — 보안 기술 조치 준수 분석 에이전트"""
from langchain_openai import ChatOpenAI

from agents._base_agent import BaseAgent

_SECURITY_PROMPT = (
    "당신은 한국 안전성확보조치기준 및 정보통신망법 전문 보안 컴플라이언스 에이전트입니다. "
    "주어진 코드를 분석해 평문 비밀번호 저장, HTTPS 미적용, SQL Injection, 접근 로그, 암호화를 점검하세요. "
    "반드시 다음 형식으로만 응답하세요: "
    "status|description|law_name|article_number|article_id "
    "(status: compliant 또는 violation)"
)


class SecurityAgent(BaseAgent):
    """보안 기술 조치 관련 코드 분석 에이전트."""

    _SYSTEM_PROMPT = _SECURITY_PROMPT
