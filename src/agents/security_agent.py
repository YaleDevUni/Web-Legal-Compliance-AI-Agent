"""agents/security_agent.py — 보안 기술 조치 준수 분석 에이전트"""
from agents._base_agent import BaseAgent

_SECURITY_PROMPT = (
    "당신은 한국 정보통신망법 및 개인정보 안전성 확보조치 기준 전문 보안 컴플라이언스 에이전트입니다. "
    "주어진 코드를 분석해 평문 비밀번호 저장, HTTPS 미적용, SQL Injection, 접근 로그 누락, 암호화 미적용 등을 점검하세요. "
    "판단 기준: 실제 보안 취약점이 코드에 명확히 존재할 때만 violation. "
    "비밀번호·암호화·접근통제 위반은 안전성확보조치(SA_) 조항을 우선 인용하세요. "
    "단순 입력 필드 존재만으로는 violation이 아닙니다 — 실제 저장/처리 로직이 확인될 때만 위반으로 판단하세요."
)


class SecurityAgent(BaseAgent):
    """보안 기술 조치 관련 코드 분석 에이전트."""

    _SYSTEM_PROMPT = _SECURITY_PROMPT
    _RELEVANT_PREFIXES = ["SA_", "IC_"]
    _SEARCH_DOMAIN_HINT = "보안 암호화 접근통제 취약점 안전성 확보조치 비밀번호 로그"
