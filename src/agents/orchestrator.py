"""agents/orchestrator.py — 멀티 에이전트 오케스트레이터"""
import re
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from core.logger import logger
from core.models import ComplianceReport, ComplianceStatus
from agents.privacy_agent import PrivacyAgent
from agents.security_agent import SecurityAgent
from agents.service_agent import ServiceAgent

_INTENT_PROMPT = (
    "아래 코드/HTML에서 개인정보·보안·서비스 법규와 관련된 행위를 "
    "한국 법령 조문 검색에 최적화된 자연어 키워드 문장으로 요약하세요. "
    "법령 조문 텍스트와 벡터 유사도가 높도록 법령 용어를 사용하세요. "
    "예: '동의 없는 개인정보 수집, 민감정보(건강정보·주민등록번호) 처리, 평문 비밀번호 저장'\n\n"
    "코드:\n"
)

_PURPOSE_PROMPT = (
    "다음 코드/텍스트를 분석하여 웹사이트의 주요 목적을 1~2단어로 요약하고, 해당 목적을 위해 반드시 준수해야 할 핵심 법규 분야를 '개인정보', '보안', '서비스' 중에서 모두 선택하세요. "
    "\n\n"
    "각 법규 분야 선택 기준 (반드시 준수):\n"
    "- '개인정보': 회원가입, 로그인, 개인정보 수집 폼, 쿠키/트래킹이 있는 경우\n"
    "- '보안': 로그인, 비밀번호, 인증, 결제 등 민감한 데이터 처리가 있는 경우\n"
    "- '서비스': 실제 상품/서비스 판매, 결제 시스템, 유료 구독/청약이 있는 경우에만 선택. "
    "정보 제공·전적 조회·커뮤니티·블로그 등 비상거래 사이트에는 선택하지 마세요.\n"
    "\n"
    "다음 형식으로만 응답하세요(목적과 법규 분야는 | 로 구분): "
    "목적: [요약된 목적] | 법규: [선택된 법규 분야 쉼표로 구분]"
    "\n\n"
    "예시 1 (쇼핑몰):\n"
    "목적: 쇼핑몰 | 법규: 개인정보, 보안, 서비스"
    "\n\n"
    "예시 2 (게임 전적 조회 사이트):\n"
    "목적: 게임 전적 조회 | 법규: 개인정보, 보안"
    "\n\n"
    "예시 3 (정보 블로그):\n"
    "목적: 정보 블로그 | 법규: 개인정보"
    "\n\n"
    "예시 4 (단순 회사소개 페이지):\n"
    "목적: 기업 홍보 | 법규: "
    "\n\n"
    "분석할 코드:\n"
)


class Orchestrator:
    """웹사이트 목적에 따라 필요한 에이전트를 동적으로 선택, 실행하고 결과를 병합하는 오케스트레이터."""

    _AGENT_MAP = {
        "개인정보": PrivacyAgent,
        "보안": SecurityAgent,
        "서비스": ServiceAgent,
    }

    def __init__(self, retriever=None, model: str = "gpt-4o-mini") -> None:
        self._retriever = retriever
        self._llm = ChatOpenAI(model=model, temperature=0)

    def _extract_search_query(self, code_text: str) -> str:
        """코드/HTML → 법령 벡터 검색에 최적화된 자연어 쿼리 1회 추출."""
        response = self._llm.invoke(
            [HumanMessage(content=_INTENT_PROMPT + code_text[:1500])]
        )
        return response.content.strip()

    def _determine_website_purpose(self, code_text: str) -> tuple[str, list[str]]:
        """LLM을 사용해 웹사이트 목적과 필요한 법규 분야 식별."""
        prompt = _PURPOSE_PROMPT + code_text[:1500]
        response = self._llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()

        purpose_match = re.search(r"목적:\s*(.*?)\s*\|", content)
        laws_match = re.search(r"법규:\s*(.*)", content)

        purpose = purpose_match.group(1) if purpose_match else "알 수 없음"
        laws_str = laws_match.group(1) if laws_match else ""
        
        required_laws = [law.strip() for law in laws_str.split(",") if law.strip()]
        
        return purpose, required_laws

    def run(self, code_text: str) -> list[ComplianceReport]:
        """목적 식별 → 에이전트 선택 실행 → 결과 병합 반환."""
        if not code_text.strip():
            return []

        # 1. 웹사이트 목적 및 필요 법규 식별
        purpose, required_laws = self._determine_website_purpose(code_text)
        logger.info(f"웹사이트 목적 식별: '{purpose}', 필요 법규: {required_laws}")

        if not required_laws:
            logger.info("관련 법규 없음. 분석을 조기 종료합니다.")
            return []

        # 2. RAG 검색 쿼리를 법령 도메인 자연어로 변환 (1회)
        search_query = (
            self._extract_search_query(code_text)
            if self._retriever is not None
            else code_text
        )

        # 3. 목적에 맞는 에이전트 동적 실행
        raw: list[ComplianceReport] = []
        for law_name in required_laws:
            agent_class = self._AGENT_MAP.get(law_name)
            if agent_class:
                agent = agent_class(retriever=self._retriever)
                logger.info(f"'{law_name}' 분야 분석을 위해 {agent.__class__.__name__} 실행...")
                raw.extend(agent.analyze(code_text, search_query=search_query))
            else:
                logger.warning(f"'{law_name}'에 해당하는 에이전트를 찾을 수 없습니다.")

        # 4. 결과 후처리
        _DEFAULT_SHA = "0" * 64
        _META_DESCRIPTIONS = {"빈 문자열", "없음", "n/a", "compliant", "violation", ""}

        results = []
        for r in raw:
            if r.description.strip().lower() in _META_DESCRIPTIONS:
                continue
            # compliant인데 모든 citation이 기본 SHA → unverifiable로 재분류
            if (
                r.status == ComplianceStatus.COMPLIANT
                and r.citations
                and all(c.sha256 == _DEFAULT_SHA for c in r.citations)
            ):
                r = r.model_copy(update={"status": ComplianceStatus.UNVERIFIABLE, "citations": []})
            results.append(r)
        return results
