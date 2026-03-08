"""src/agents/legal_agent.py — 부동산 법률 추론 에이전트"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from core.logger import logger
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from core.models import LegalAnswer, Citation
from retrieval.hybrid import HybridRetriever
from retrieval.graph_expander import GraphExpander

class LegalReasoningAgent:
    """부동산 법령 및 판례를 기반으로 법률 질문에 답변하는 에이전트"""

    _SYSTEM_PROMPT = (
        "당신은 대한민국 부동산 법률 전문 보조 AI입니다. 사용자와 자연스럽게 대화하면서 법률 질문에 전문적으로 답변합니다.\n\n"
        "## 대화 방식\n"
        "- '고마워', '알겠어', '잘 됐네' 같은 인사나 짧은 반응에는 간단하고 자연스럽게 답하세요. 법적 분석 불필요.\n"
        "- '판례는 없어?', '더 설명해줘', '그럼 어떻게 해?' 같은 follow-up 질문은 **이전 대화 내용을 참고**하여 답하세요.\n"
        "- 이전 대화가 있는 경우, 새 질문이 그 맥락의 연장선인지 파악하세요.\n\n"
        "## 법률 질문 답변 지침\n"
        "1. 제공된 [법령] 및 [판례] 컨텍스트를 우선 활용하세요.\n"
        "2. 컨텍스트에 [판례] 섹션이 하나라도 있으면 **반드시** 해당 사건번호를 답변 본문에 직접 언급하세요. 판례를 절대 생략하지 마세요.\n"
        "3. 판례 인용 시 사건번호(예: 2024다123456)와 판결 요지를 함께 서술하세요.\n"
        "4. 컨텍스트만으로 부족하면 일반 법률 지식으로 보완하되, 그 사실을 밝히세요.\n"
        "5. 실질적인 법률 답변에는 마지막에 면책 고지를 포함하세요: '이 답변은 참고용이며 법적 효력을 갖지 않습니다. 실제 분쟁 시 전문가의 자문을 구하시기 바랍니다.'\n"
        "6. 마크다운 형식으로 가독성 있게 작성하세요."
    )

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        law_retriever: Optional[HybridRetriever] = None,
        case_retriever: Optional[HybridRetriever] = None,
        graph_expander: Optional[GraphExpander] = None
    ) -> None:
        self._llm = ChatOpenAI(model=model, temperature=0)
        self._law_retriever = law_retriever
        self._case_retriever = case_retriever
        self._graph_expander = graph_expander

    async def aask(self, question: str, session_id: str = "default", history: List[Dict] = None):
        """질문에 대해 검색, 확장 후 답변을 비동기 스트림으로 생성한다."""
        logger.info(f"비동기 질문 수신: {question}")

        # 1. 검색 (Retrieval)
        law_results = self._law_retriever.search(question, top_k=5) if self._law_retriever else []
        case_results = self._case_retriever.search(question, top_k=3) if self._case_retriever else []
        
        # 2. 그래프 확장
        expanded_results = []
        if self._graph_expander and law_results:
            expanded_results = self._graph_expander.expand(law_results, depth=1)
            
        # 3. 컨텍스트 구성
        context_str, citation_map = self._build_context(law_results + expanded_results, case_results)
        
        # 4. Citation 데이터 미리 준비
        citations = self._make_citations(citation_map)
        related_ids = [res["metadata"].get("article_id") for res in expanded_results if "article_id" in res["metadata"]]

        # 5. LLM 스트리밍 추론
        messages = [
            SystemMessage(content=self._SYSTEM_PROMPT),
        ]
        if history:
            for h in history[-6:]:
                role = h.get("role")
                content = h.get("content", "")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))

        user_msg = f"질문: {question}"
        if context_str:
            user_msg += f"\n\n[컨텍스트]\n{context_str}"
        messages.append(HumanMessage(content=user_msg))
        
        # 제너레이터로 반환 (텍스트 토큰들 -> 마지막에 citations)
        full_answer = []
        async for chunk in self._llm.astream(messages):
            content = chunk.content
            if content:
                full_answer.append(content)
                yield {"type": "content", "text": content}
        
        yield {
            "type": "citations", 
            "citations": citations, 
            "related_articles": related_ids,
            "full_answer": "".join(full_answer)
        }

    def _build_context(self, laws: List[Dict], cases: List[Dict]) -> tuple[str, dict]:
        """검색 결과로부터 LLM 컨텍스트 문자열과 메타데이터 맵을 생성한다."""
        lines = []
        citation_map = {}
        
        # 법령 조문 합치기 (중복 제거)
        processed_law_ids = set()
        for res in laws:
            meta = res["metadata"]
            art_id = meta.get("article_id")
            if not art_id or art_id in processed_law_ids: continue
            processed_law_ids.add(art_id)
            
            content = meta.get("full_content") or res["text"]
            lines.append(f"[법령] {meta.get('law_name')} {meta.get('article_number')}\n{content}")
            citation_map[art_id] = meta
            
        # 판례 합치기
        processed_case_ids = set()
        for res in cases:
            meta = res["metadata"]
            case_id = meta.get("case_id")
            if not case_id or case_id in processed_case_ids: continue
            processed_case_ids.add(case_id)
            
            lines.append(f"[판례] {meta.get('case_number')} ({meta.get('case_name')})\n{res['text']}")
            citation_map[f"CASE_{case_id}"] = {**meta, "text": res["text"]}
            
        return "\n\n".join(lines), citation_map

    def _make_citations(self, citation_map: dict) -> List[Citation]:
        """메타데이터 맵으로부터 Citation 리스트를 생성한다."""
        citations = []
        for cid, meta in citation_map.items():
            if cid.startswith("CASE_"):
                # 판례 Citation
                citations.append(Citation(
                    article_id=cid,
                    law_name=meta.get("case_name", ""),
                    article_number=meta.get("case_number", ""),
                    sha256=meta.get("sha256", "0"*64),
                    url=meta.get("url", "https://www.law.go.kr/"),
                    updated_at=datetime.fromisoformat(meta.get("decision_date")) if "decision_date" in meta else datetime.now(),
                    article_content=meta.get("text", ""),
                    case_number=meta.get("case_number"),
                    court=meta.get("court"),
                    decision_date=datetime.fromisoformat(meta.get("decision_date")) if "decision_date" in meta else None
                ))
            else:
                # 법령 Citation
                citations.append(Citation(
                    article_id=cid,
                    law_name=meta.get("law_name", ""),
                    article_number=meta.get("article_number", ""),
                    sha256=meta.get("sha256", "0"*64),
                    url=meta.get("url", "https://www.law.go.kr/"),
                    updated_at=datetime.fromisoformat(meta.get("updated_at")) if "updated_at" in meta else datetime.now(),
                    article_content=meta.get("full_content", "")
                ))
        return citations
