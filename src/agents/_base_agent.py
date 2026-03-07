"""agents/_base_agent.py — 에이전트 공통 LLM 파싱 로직"""
from datetime import datetime

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from core.models import Citation, ComplianceReport, ComplianceStatus
from integrity.db import ArticleDB

_DEFAULT_SHA = "0" * 64
_DEFAULT_URL = "https://www.law.go.kr/"

# 응답 형식: "status|description|law_name|article_number|article_id|code_snippet"
# status: compliant | violation
# code_snippet: 문제가 된 코드 원문 (violation일 때 필수)


def _make_citation(
    law_name: str,
    article_number: str,
    article_id: str,
    db: ArticleDB | None = None,
) -> Citation:
    sha256 = _DEFAULT_SHA
    updated_at = datetime(2024, 1, 1)
    if db is not None:
        info = db.get_info(article_id)
        if info:
            sha256 = info["sha256"]
            updated_at = datetime.fromisoformat(info["updated_at"])
    url = f"https://www.law.go.kr/법령/{law_name}"
    return Citation(
        article_id=article_id,
        law_name=law_name,
        article_number=article_number,
        sha256=sha256,
        url=url,
        updated_at=updated_at,
    )


def _parse_llm_response(content: str, db: ArticleDB | None = None) -> ComplianceReport | None:
    """pipe-delimited LLM 응답을 ComplianceReport로 변환. 파싱 실패 시 None."""
    parts = [p.strip() for p in content.split("|")]
    if len(parts) < 5:
        return None
    status_str, description, law_name, article_number, article_id = parts[:5]
    code_snippet = parts[6].strip() if len(parts) > 6 else (parts[5].strip() if len(parts) > 5 else "")
    try:
        status = ComplianceStatus(status_str.lower())
    except ValueError:
        return None
    citation = _make_citation(law_name, article_number, article_id, db)
    return ComplianceReport(
        status=status,
        description=description,
        citations=[citation],
        recommendation=code_snippet,
    )


class BaseAgent:
    """공통 LLM 호출 및 파싱 기반 에이전트."""

    _SYSTEM_PROMPT = ""

    def __init__(self, model: str = "gpt-4o-mini", db: ArticleDB | None = None) -> None:
        self._llm = ChatOpenAI(model=model, temperature=0)
        self._db = db

    def analyze(self, code_text: str) -> list[ComplianceReport]:
        """코드 텍스트를 분석해 ComplianceReport 리스트 반환."""
        if not code_text.strip():
            return []
        prompt = f"{self._SYSTEM_PROMPT}\n\n코드:\n{code_text}"
        response = self._llm.invoke([HumanMessage(content=prompt)])
        report = _parse_llm_response(response.content, self._db)
        return [report] if report else []
