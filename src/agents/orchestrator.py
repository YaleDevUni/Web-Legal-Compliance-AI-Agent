"""agents/orchestrator.py — 멀티 에이전트 오케스트레이터"""
from core.models import ComplianceReport
from agents.privacy_agent import PrivacyAgent
from agents.security_agent import SecurityAgent
from agents.service_agent import ServiceAgent


class Orchestrator:
    """3개 에이전트를 순차 호출해 결과를 병합하는 오케스트레이터."""

    def __init__(self) -> None:
        self.privacy_agent = PrivacyAgent()
        self.security_agent = SecurityAgent()
        self.service_agent = ServiceAgent()

    def run(self, code_text: str) -> list[ComplianceReport]:
        """3개 에이전트를 호출해 ComplianceReport 리스트로 병합 반환."""
        if not code_text.strip():
            return []
        results: list[ComplianceReport] = []
        results.extend(self.privacy_agent.analyze(code_text))
        results.extend(self.security_agent.analyze(code_text))
        results.extend(self.service_agent.analyze(code_text))
        return results
