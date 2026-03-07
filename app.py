"app.py — Web Legal Compliance AI Agent Streamlit UI"
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import streamlit as st
from qdrant_client import QdrantClient

from agents.orchestrator import Orchestrator
from retrieval.hybrid import HybridRetriever
from input.url_parser import parse_url
from core.models import ComplianceStatus
from core.config import Settings
from core.logger import logger

@st.cache_resource
def _get_retriever() -> HybridRetriever | None:
    """HybridRetriever 싱글턴 — BM25 코퍼스 로드 포함."""
    try:
        settings = Settings()
        client = QdrantClient(url=str(settings.qdrant_url))
        return HybridRetriever(client, collection=settings.qdrant_collection)
    except Exception:
        return None

st.set_page_config(
    page_title="Web Legal Compliance AI Agent",
    page_icon="⚖️",
    layout="wide",
)

st.title("⚖️ Web Legal Compliance AI Agent")
st.caption("한국 개인정보·보안·서비스 규정 자동 준수 검사")


def _render_citations(citations) -> None:
    """Citation 카드 렌더링 (법령명·조항·조문 내용·SHA·링크)."""
    for citation in citations:
        st.markdown(
            f"📚 **{citation.law_name} {citation.article_number}** "
            f"· `sha:{citation.short_sha}` "
            f"· {citation.updated_at.strftime('%Y-%m-%d')} "
            f"· [원문 링크]({citation.url})"
        )
        if citation.article_content:
            with st.expander("법령 조문 내용 보기"):
                st.caption(citation.article_content)


# ── 입력 탭 ──────────────────────────────────────────────────────────────────

tab_file, tab_url, tab_text = st.tabs(["📄 파일 분석", "🌐 URL 분석", "💬 코드/텍스트 직접 입력"])

input_text: str | None = None

with tab_file:
    uploaded = st.file_uploader(
        "분석할 소스 파일 업로드 (.py .html .js .css .ts .txt)",
        type=["py", "html", "htm", "js", "css", "ts", "txt"],
    )
    if uploaded is not None:
        input_text = uploaded.read().decode("utf-8", errors="replace")
        st.code(input_text[:500] + ("..." if len(input_text) > 500 else ""), language="python")

with tab_url:
    url_input = st.text_input("분석할 웹페이지 URL 입력", placeholder="https://example.com")
    if url_input:
        try:
            parsed = parse_url(url_input)
            input_text = parsed.get("text", "")
            st.success(f"URL 파싱 완료 — 텍스트 {len(input_text)}자 추출")
        except Exception as e:
            st.error(f"URL 파싱 실패: {e}")

with tab_text:
    code_input = st.text_area(
        "코드 또는 텍스트를 직접 붙여넣기",
        height=250,
        placeholder="def save_user(user, password):\n    db.save(password)  # 평문 저장?",
    )
    if code_input.strip():
        input_text = code_input

# ── 분석 실행 ──────────────────────────────────────────────────────────────

st.divider()

if st.button("🔍 준수 여부 분석", type="primary", disabled=not input_text):
    if not input_text:
        st.warning("분석할 내용을 먼저 입력하세요.")
    else:
        with st.spinner("AI 에이전트 분석 중..."):
            try:
                retriever = _get_retriever()
                orchestrator = Orchestrator(retriever=retriever)
                reports = orchestrator.run(input_text)
            except Exception as e:
                logger.exception("분석 중 오류 발생:") # Added console logging
                st.error(f"분석 오류: {e}")
                reports = []

        if not reports:
            st.info("분석 결과가 없습니다. 법령 관련 코드를 입력해주세요.")
        else:
            compliant = [r for r in reports if r.status == ComplianceStatus.COMPLIANT]
            violations = [r for r in reports if r.status == ComplianceStatus.VIOLATION]

            col1, col2 = st.columns(2)
            col1.metric("✅ 준수 항목", len(compliant))
            col2.metric("⚠️ 보완 필요 항목", len(violations))

            if violations:
                st.subheader("⚠️ 보완 필요 항목")
                for report in violations:
                    with st.expander(f"위반: {report.description}", expanded=True):
                        st.write(report.description)
                        if report.source_location:
                            loc = report.source_location
                            st.markdown(f"**문제 코드 위치** (라인 {loc.line_start}–{loc.line_end})")
                            st.code(loc.snippet, language="python")
                        elif report.recommendation:
                            st.markdown("**문제 코드**")
                            st.code(report.recommendation)
                        _render_citations(report.citations)

            if compliant:
                st.subheader("✅ 준수 항목")
                for report in compliant:
                    with st.expander(f"준수: {report.description}"):
                        st.write(report.description)
                        _render_citations(report.citations)