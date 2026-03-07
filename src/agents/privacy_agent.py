"""agents/privacy_agent.py — 개인정보 보호법 준수 분석 에이전트"""
from agents._base_agent import BaseAgent

_PRIVACY_PROMPT = (
    "당신은 한국 개인정보 보호법 전문 컴플라이언스 에이전트입니다. "
    "주어진 코드를 분석해 개인정보 수집 동의, 민감정보 처리, 보유기간, 마케팅 동의 분리 등을 점검하세요. "
    "판단 기준: 코드에 실제 개인정보 수집 필드(input, form 등)가 있고 동의 절차가 명확히 없을 때만 violation. "
    "단순 UI 안내 문구, 링크, 설명 텍스트만 있는 경우는 compliant로 판단하세요."
)


class PrivacyAgent(BaseAgent):
    """개인정보 보호법 관련 코드 분석 에이전트."""

    _SYSTEM_PROMPT = _PRIVACY_PROMPT
    _RELEVANT_PREFIXES = ["PA_", "IC_", "LI_"]
    _SEARCH_DOMAIN_HINT = "개인정보 수집 이용 동의 민감정보 처리 제한 정보주체 권리 보유기간"
