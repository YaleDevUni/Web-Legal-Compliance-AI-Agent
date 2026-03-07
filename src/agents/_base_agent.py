"""agents/_base_agent.py — RAG 기반 에이전트 공통 로직

흐름:
  1. 입력 코드 → VectorRetriever로 관련 법령 청크 검색
  2. 검색된 청크 텍스트를 LLM 프롬프트 컨텍스트로 제공
  3. LLM이 제공된 법령 중 위반 여부 판단
  4. 응답의 article_id로 검색 청크 metadata 매칭 → Citation 구성
  5. 원본 코드에서 code_snippet 위치(라인 번호) 매핑
"""
import re
from datetime import datetime

from core.logger import logger
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from core.models import Citation, ComplianceReport, ComplianceStatus, SourceLocation

_DEFAULT_SHA = "0" * 64

# LLM 응답 형식: "status|description|article_id|code_snippet"
# article_id: 제공된 [참고 법령] 목록에서 반드시 선택
# code_snippet: violation 시 문제 코드 1~3줄, compliant 시 빈 문자열

_ARTICLE_NUM_RE = re.compile(r"(\d+(?:의\d+)?)")


def _build_law_context(chunks: list[dict]) -> tuple[str, dict[str, dict]]:
    """검색된 청크 → LLM 컨텍스트 문자열 + article_id별 metadata 인덱스.
    
    동일 article_id를 가진 여러 청크의 텍스트를 하나로 합쳐 컨텍스트 손실을 방지.
    """
    grouped_chunks: dict[str, dict] = {}
    for chunk in chunks:
        meta = chunk.get("metadata", {})
        aid = meta.get("article_id", "")
        if not aid:
            continue

        if aid not in grouped_chunks:
            # 청크 리스트의 순서를 유지하기 위해 meta는 처음 나타난 것을 사용
            grouped_chunks[aid] = {"meta": meta, "texts": []}
        
        # 중복 텍스트는 추가하지 않음
        text_to_add = chunk.get("text", "")
        if text_to_add not in grouped_chunks[aid]["texts"]:
            grouped_chunks[aid]["texts"].append(text_to_add)

    index: dict[str, dict] = {}
    lines: list[str] = []
    for aid, data in grouped_chunks.items():
        meta = data["meta"]
        # 여러 텍스트 청크를 줄바꿈으로 합침
        full_text = "\n\n".join(data["texts"])
        
        # 최종적으로 index와 lines에 병합된 텍스트와 메타데이터 저장
        index[aid] = {**meta, "text": full_text}
        lines.append(
            f"[{aid}] {meta.get('law_name', '')} {meta.get('article_number', '')}\n"
            f"{full_text}"
        )
        
    return "\n\n".join(lines), index


def _make_citation_from_meta(meta: dict) -> Citation:
    """chunk metadata 딕셔너리 → Citation 객체."""
    sha256 = meta.get("sha256", _DEFAULT_SHA)
    updated_at_raw = meta.get("updated_at", "")
    try:
        updated_at = datetime.fromisoformat(updated_at_raw) if updated_at_raw else datetime(2024, 1, 1)
    except ValueError:
        updated_at = datetime(2024, 1, 1)
    url = meta.get("url", "https://www.law.go.kr/")
    return Citation(
        article_id=meta.get("article_id", ""),
        law_name=meta.get("law_name", ""),
        article_number=meta.get("article_number", ""),
        sha256=sha256,
        url=url,
        updated_at=updated_at,
        article_content=meta.get("text", ""),
    )


def _find_source_location(code_text: str, snippet: str) -> SourceLocation | None:
    if not snippet:
        return None
    lines = code_text.splitlines()
    first_line = snippet.strip().splitlines()[0].strip()
    for i, line in enumerate(lines):
        if first_line in line:
            line_start = i + 1
            snippet_line_count = len(snippet.strip().splitlines())
            line_end = min(line_start + snippet_line_count - 1, len(lines))
            matched = "\n".join(lines[line_start - 1 : line_end])
            return SourceLocation(line_start=line_start, line_end=line_end, snippet=matched)
    return None


def _parse_llm_response(
    content: str,
    chunk_index: dict[str, dict],
    code_text: str = "",
) -> list[ComplianceReport]: # Changed return type
    """LLM 응답 파싱 → ComplianceReport 리스트.

    형식: status|description|article_id|code_snippet
    LLM 응답은 여러 줄일 수 있으며, 각 줄이 하나의 보고서에 해당함.
    article_id로 chunk_index에서 실제 법령 metadata 조회.
    """
    reports: list[ComplianceReport] = []
    
    # LLM 응답을 줄 단위로 분리하여 각 보고서 파싱
    for line in content.strip().split("\n"):
        parts = [p.strip() for p in line.split("|", maxsplit=3)]
        if len(parts) < 3:
            logger.warning(f"파싱 실패: LLM 응답 형식이 올바르지 않음 - '{line}'")
            continue
        
        status_str, description, article_id = parts[:3]
        code_snippet = parts[3] if len(parts) > 3 else ""
        
        try:
            status = ComplianceStatus(status_str.lower())
        except ValueError:
            logger.warning(f"파싱 실패: 알 수 없는 상태 값 - '{status_str}' in '{line}'")
            continue

        meta = chunk_index.get(article_id)
        if meta is None:
            # chunk_index에 없으면 article_id에서 직접 법령 정보 구성 (fallback)
            # UNKNOWN일 경우 빈 메타데이터로 처리
            meta = {"article_id": article_id, "law_name": "", "article_number": "",
                    "sha256": _DEFAULT_SHA, "url": "https://www.law.go.kr/",
                    "updated_at": "2024-01-01T00:00:00", "text": ""}

        citation = _make_citation_from_meta(meta)
        source_location = _find_source_location(code_text, code_snippet) if code_snippet else None
        
        reports.append(
            ComplianceReport(
                status=status,
                description=description,
                citations=[citation],
                recommendation=code_snippet,
                source_location=source_location,
            )
        )
    return reports


def _make_rag_instruction(available_ids: list[str]) -> str:
    ids_str = ", ".join(available_ids) if available_ids else "없음"
    return (
        f"위 [참고 법령] 목록에서 관련 조항을 선택하여 코드의 법령 준수 여부를 판단하세요. "
        f"사용 가능한 article_id 목록: [{ids_str}] — 이 목록 내에서 가장 적합한 article_id를 선택하여 주요 근거로 활용하십시오. 만약 제공된 법령만으로는 명확한 판단이 어렵거나, 관련성이 매우 낮아 보인다면, 당신의 지식을 활용하여 'compliant'로 응답하고, 이 경우에도 가장 근접한 article_id를 선택하거나 'UNKNOWN'으로 기입할 수 있습니다. "
        "코드에서 발견한 모든 법규 위반 사항을 개별적으로 보고해야 합니다. 각 위반 사항은 별도의 줄에 다음 형식으로 응답하세요 (| 구분, 정확히 4개 필드): " # Modified instruction
        "status|description|article_id|code_snippet "
        "판단 기준 (매우 중요): "
        "1) 코드에 위반 증거가 명확히 있을 때만 violation — 추측이나 가능성은 compliant. "
        "2) 단순 안내 문구·링크·설명 텍스트만 있는 경우는 compliant. "
        "3) 실제 데이터 수집/처리 코드(form, input, DB저장 등)가 있어야 violation 가능. "
        "4) article_id 우선순위 규칙 (반드시 준수): "
        "건강정보·병력·성생활·종교·노동조합·정치적 견해 등 민감정보 수집 → PA_23 최우선 선택. "
        "주민등록번호·여권번호·운전면허번호 등 고유식별정보 → PA_24 최우선 선택. "
        "일반 개인정보 수집·이용 동의 누락 → PA_15 선택. "
        "PA_15는 민감정보·고유식별정보가 아닌 일반 개인정보에만 사용할 것. "
        "평문 비밀번호·암호화 미적용·접근통제 미비 → SA_ 계열 선택. "
        "5) code_snippet은 violation 시 문제 코드 원문 1~3줄, compliant 시 빈 문자열. "
        "6) description은 반드시 구체적인 한 문장으로 작성. "
        "'빈 문자열' '없음' 'N/A' 등 메타 텍스트는 절대 사용 금지. "
        "예시: violation|건강정보 수집 시 별도 동의 절차 없음|PA_23|<input name=\"health_data\">"
    )


class BaseAgent:
    """RAG 기반 법령 준수 분석 에이전트."""

    _SYSTEM_PROMPT = ""
    # 서브클래스에서 article_id prefix 목록 지정 (빈 목록 = 필터 없음)
    _RELEVANT_PREFIXES: list[str] = []
    # 서브클래스에서 도메인 검색 힌트 지정 (공유 쿼리에 추가해 편향 방지)
    _SEARCH_DOMAIN_HINT: str = ""

    def __init__(self, model: str = "gpt-4o-mini", retriever=None) -> None:
        self._llm = ChatOpenAI(model=model, temperature=0)
        self._retriever = retriever

    def analyze(self, code_text: str, search_query: str | None = None) -> list[ComplianceReport]:
        """코드 텍스트를 분석해 ComplianceReport 리스트 반환.

        search_query: RAG 검색용 자연어 쿼리 (없으면 code_text 사용).
                      Orchestrator가 법령 도메인 쿼리로 변환해 전달하면 정확도 향상.
        """
        agent_name = self.__class__.__name__
        logger.debug(f"[{agent_name}] 분석 시작...")

        if not code_text.strip():
            return []

        # 1. 관련 법령 청크 검색 (top_k=10으로 후보 확보)
        chunks: list[dict] = []
        if self._retriever is not None:
            base_query = search_query or code_text
            # 도메인 힌트를 추가해 에이전트별 편향 방지
            query = f"{base_query} {self._SEARCH_DOMAIN_HINT}".strip()
            logger.info(f"[{agent_name}] Retriever 검색 쿼리: '{query}'")

            raw_chunks = self._retriever.search(query, top_k=10)

            raw_chunks_log = [
                f"id={c.get('metadata', {}).get('article_id', 'N/A')}, score={c.get('score', 0):.4f}"
                for c in raw_chunks
            ]
            logger.debug(f"[{agent_name}] 검색된 Top-K 문서 (필터링 전): {raw_chunks_log}")

            # 에이전트별 담당 법령 prefix 필터링
            if self._RELEVANT_PREFIXES:
                chunks = [
                    c
                    for c in raw_chunks
                    if any(
                        c.get("metadata", {}).get("article_id", "").startswith(p)
                        for p in self._RELEVANT_PREFIXES
                    )
                ]
                filtered_chunks_log = [
                    f"id={c.get('metadata', {}).get('article_id', 'N/A')}" for c in chunks
                ]
                logger.debug(f"[{agent_name}] 필터링 후 최종 문서: {filtered_chunks_log}")
            else:
                chunks = raw_chunks

        # 2. 컨텍스트 + chunk_index 빌드
        law_context, chunk_index = _build_law_context(chunks)

        # 3. 프롬프트 구성
        if law_context:
            rag_instruction = _make_rag_instruction(list(chunk_index.keys()))
            prompt = (
                f"{self._SYSTEM_PROMPT}\n\n"
                f"[참고 법령]\n{law_context}\n\n"
                f"{rag_instruction}\n\n"
                f"코드:\n{code_text}"
            )
        else:
            # retriever 없거나 검색 결과 없을 때 fallback
            # (이 경우 LLM은 자신의 사전 지식으로만 답변 시도. 법규 준수 여부는 거의 판별 불가)
            prompt = f"{self._SYSTEM_PROMPT}\n\n코드:\n{code_text}"
        
        logger.debug(f"[{agent_name}] 최종 프롬프트: {prompt}")

        # 4. LLM 호출
        response = self._llm.invoke([HumanMessage(content=prompt)])

        # 5. 파싱
        reports = _parse_llm_response(response.content, chunk_index, code_text) # Changed variable name
        logger.info(f"[{agent_name}] 분석 완료: {len(reports)}개의 보고서 생성됨") # Changed log message
        return reports # Return the list of reports
