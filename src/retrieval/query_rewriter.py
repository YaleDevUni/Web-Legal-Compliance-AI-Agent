"""retrieval/query_rewriter.py — LLM 기반 쿼리 재작성 모듈"""
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

_SYSTEM_PROMPT = (
    "당신은 한국 법령 검색 전문가입니다. "
    "사용자 질문을 법령 검색에 최적화된 쿼리로 재작성하세요. "
    "재작성된 쿼리만 출력하고 다른 설명은 하지 마세요."
)


class QueryRewriter:
    """LLM을 사용해 쿼리를 법령 검색에 최적화된 형태로 재작성."""

    def __init__(self, model: str = "gpt-4o-mini") -> None:
        self._llm = ChatOpenAI(model=model, temperature=0)

    def rewrite(self, query: str) -> str:
        """쿼리를 법령 검색에 적합하게 재작성해 반환.

        빈 쿼리 → ValueError; LLM 빈 응답 → 원본 fallback.
        """
        if not query.strip():
            raise ValueError("쿼리가 비어 있습니다.")
        messages = [
            HumanMessage(content=f"{_SYSTEM_PROMPT}\n\n질문: {query}"),
        ]
        response = self._llm.invoke(messages)
        rewritten = response.content.strip()
        return rewritten if rewritten else query

    def rewrite_multiple(self, query: str, n: int = 3) -> list[str]:
        """쿼리를 n번 재작성해 다양한 관점의 쿼리 리스트 반환."""
        return [self.rewrite(query) for _ in range(n)]
