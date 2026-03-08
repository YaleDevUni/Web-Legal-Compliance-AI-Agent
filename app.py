"app.py — Web Legal Compliance AI Agent Streamlit UI"
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import streamlit as st
from qdrant_client import QdrantClient
import redis as redis_lib

from agents.orchestrator import Orchestrator
from retrieval.hybrid import HybridRetriever
from input.url_parser import parse_url
from input.file_loader import load_zip
from core.models import ComplianceStatus
from core.config import Settings
from core.logger import logger
from cache.url_cache import URLAnalysisCache
from streaming.redis_stream import RedisStream

@st.cache_resource
def _get_retriever() -> HybridRetriever | None:
    """HybridRetriever 싱글턴 — BM25 코퍼스 로드 포함."""
    try:
        settings = Settings()
        client = QdrantClient(url=str(settings.qdrant_url), timeout=30)
        return HybridRetriever(client, collection=settings.qdrant_collection)
    except Exception:
        return None

@st.cache_resource
def _get_redis_client():
    """Redis 클라이언트 싱글턴 — 연결 실패 시 None."""
    try:
        settings = Settings()
        client = redis_lib.from_url(settings.redis_url, decode_responses=False)
        client.ping()
        return client
    except Exception:
        return None

def _get_url_cache() -> URLAnalysisCache | None:
    rc = _get_redis_client()
    return URLAnalysisCache(redis_client=rc) if rc else None

def _get_stream() -> RedisStream | None:
    rc = _get_redis_client()
    return RedisStream(redis_client=rc) if rc else None

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

tab_file, tab_zip, tab_url, tab_text = st.tabs(["📄 파일 분석", "📦 ZIP 프로젝트 분석", "🌐 URL 분석", "💬 코드/텍스트 직접 입력"])

input_text: str | None = None
current_url: str | None = None  # URL 탭에서 입력한 URL (캐시 키로 사용)

with tab_file:
    uploaded = st.file_uploader(
        "분석할 소스 파일 업로드 (.py .html .js .css .ts .txt)",
        type=["py", "html", "htm", "js", "css", "ts", "txt"],
    )
    if uploaded is not None:
        input_text = uploaded.read().decode("utf-8", errors="replace")
        st.code(input_text[:500] + ("..." if len(input_text) > 500 else ""), language="python")

with tab_zip:
    st.caption("프로젝트 ZIP을 업로드하면 node_modules, dist, .git 등을 자동 제거하고 소스 파일만 분석합니다.")
    uploaded_zip = st.file_uploader(
        "프로젝트 ZIP 파일 업로드",
        type=["zip"],
        key="zip_uploader",
    )
    if uploaded_zip is not None:
        try:
            input_text = load_zip(uploaded_zip.read())
            if input_text:
                file_count = input_text.count("// === ")
                st.success(f"ZIP 파싱 완료 — 소스 파일 {file_count}개, {len(input_text)}자 추출")
            else:
                st.warning("분석 가능한 소스 파일이 없습니다. (node_modules 등 전부 필터링됨)")
        except ValueError as e:
            st.error(str(e))

with tab_url:
    url_input = st.text_input("분석할 웹페이지 URL 입력", placeholder="https://example.com")
    if url_input:
        try:
            parsed = parse_url(url_input)
            input_text = parsed["combined"]
            current_url = url_input
            n_sub = len(parsed.get("subpages", []))
            sub_titles = ", ".join(s["title"] for s in parsed.get("subpages", []))
            st.success(f"URL 파싱 완료 — {len(input_text)}자 추출 (법적 서브페이지 {n_sub}개{': ' + sub_titles if sub_titles else ''})")
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
        # URL 탭 입력이면 캐시 확인
        url_cache = _get_url_cache()
        cached = url_cache.get(current_url) if (url_cache and current_url) else None

        if cached is not None:
            reports = cached
            st.info("⚡ 캐시된 결과를 사용합니다. (동일 URL 이전 분석 결과)")
        else:
            with st.spinner("AI 에이전트 분석 중..."):
                try:
                    retriever = _get_retriever()
                    orchestrator = Orchestrator(retriever=retriever, stream=_get_stream())
                    reports = orchestrator.run(input_text)
                    if url_cache and current_url:
                        url_cache.set(current_url, reports)
                except Exception as e:
                    logger.exception("분석 중 오류 발생:")
                    st.error(f"분석 오류: {e}")
                    reports = []

        if not reports:
            st.info("분석 결과가 없습니다. 법령 관련 코드를 입력해주세요.")
        else:
            compliant = [r for r in reports if r.status == ComplianceStatus.COMPLIANT]
            violations = [r for r in reports if r.status == ComplianceStatus.VIOLATION]
            unverifiable = [r for r in reports if r.status == ComplianceStatus.UNVERIFIABLE]

            col1, col2, col3 = st.columns(3)
            col1.metric("⚠️ 보완 필요 항목", len(violations))
            col2.metric("✅ 준수 항목", len(compliant))
            col3.metric("🔍 확인 불가 항목", len(unverifiable))

            # 보완 필요 + 준수 항목을 나란히 2열로
            left, right = st.columns(2)

            with left:
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

            with right:
                if compliant:
                    st.subheader("✅ 준수 항목")
                    for report in compliant:
                        with st.expander(f"준수: {report.description}"):
                            st.write(report.description)
                            _render_citations(report.citations)

            # 확인 불가 항목은 전체 폭으로 아래에
            if unverifiable:
                st.subheader("🔍 확인 불가 항목")
                st.caption("소스코드 부재(SPA, 서버사이드 로직 등)로 인해 준수 여부를 판단할 수 없는 항목입니다.")
                cols = st.columns(2)
                for i, report in enumerate(unverifiable):
                    with cols[i % 2].expander(f"확인 불가: {report.description}"):
                        st.write(report.description)