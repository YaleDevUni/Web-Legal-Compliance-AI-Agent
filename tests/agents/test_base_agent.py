"""tests/agents/test_base_agent.py — BaseAgent RAG 통합 TDD

테스트 전략:
- _parse_llm_response: 새 4-field 형식 (status|description|article_id|code_snippet)
- code_snippet 내 | 허용 (maxsplit=3)
- chunk_index 기반 Citation 구성 (실제 sha256/law_name/article_number)
- chunk_index에 article_id 없을 때 fallback
- SourceLocation: code_snippet을 원본 코드에서 찾아 라인 번호 반환
- BaseAgent.analyze(): retriever 없을 때도 동작
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock


_SAMPLE_CHUNK_INDEX = {
    "PA_23": {
        "article_id": "PA_23",
        "law_name": "개인정보 보호법",
        "article_number": "제23조",
        "sha256": "a" * 64,
        "url": "https://www.law.go.kr/",
        "updated_at": "2025-01-15T00:00:00",
        "text": "제23조(민감정보의 처리 제한) 개인정보처리자는 ...",
    },
    "PA_15": {
        "article_id": "PA_15",
        "law_name": "개인정보 보호법",
        "article_number": "제15조",
        "sha256": "b" * 64,
        "url": "https://www.law.go.kr/",
        "updated_at": "2025-01-15T00:00:00",
        "text": "제15조(개인정보의 수집·이용) ...",
    },
}


# ── _parse_llm_response 테스트 ──────────────────────────────────────────────

class TestParseCodeSnippet:
    def test_code_snippet_parsed_correctly(self, mocker):
        """4-field 형식: code_snippet이 정확히 파싱됨"""
        mocker.patch("agents._base_agent.ChatOpenAI")
        from agents._base_agent import _parse_llm_response
        result = _parse_llm_response(
            "violation|민감정보 무단 처리|PA_23|db.save(health_data)",
            chunk_index=_SAMPLE_CHUNK_INDEX,
        )
        assert result is not None
        assert result.recommendation == "db.save(health_data)"

    def test_code_snippet_with_pipe_inside_snippet(self, mocker):
        """code_snippet 내부에 | 포함 → maxsplit=3으로 올바르게 보존됨"""
        mocker.patch("agents._base_agent.ChatOpenAI")
        from agents._base_agent import _parse_llm_response
        result = _parse_llm_response(
            "violation|민감정보 무단 처리|PA_23|cat file | grep password",
            chunk_index=_SAMPLE_CHUNK_INDEX,
        )
        assert result is not None
        assert result.recommendation == "cat file | grep password"

    def test_no_code_snippet_returns_empty(self, mocker):
        """code_snippet 없이 3개 필드 → recommendation 빈 문자열"""
        mocker.patch("agents._base_agent.ChatOpenAI")
        from agents._base_agent import _parse_llm_response
        result = _parse_llm_response(
            "compliant|동의 확인됨|PA_15",
            chunk_index=_SAMPLE_CHUNK_INDEX,
        )
        assert result is not None
        assert result.recommendation == ""

    def test_fewer_than_3_parts_returns_none(self, mocker):
        """3개 미만 → None 반환"""
        mocker.patch("agents._base_agent.ChatOpenAI")
        from agents._base_agent import _parse_llm_response
        assert _parse_llm_response("violation|설명", chunk_index={}) is None


# ── chunk_index 기반 Citation 구성 테스트 ──────────────────────────────────

class TestCitationFromChunkIndex:
    def test_citation_uses_real_sha_from_chunk(self, mocker):
        """chunk_index에 article_id가 있으면 실제 sha256 사용"""
        mocker.patch("agents._base_agent.ChatOpenAI")
        from agents._base_agent import _parse_llm_response
        result = _parse_llm_response(
            "violation|민감정보 무단 처리|PA_23|",
            chunk_index=_SAMPLE_CHUNK_INDEX,
        )
        assert result is not None
        assert result.citations[0].sha256 == "a" * 64
        assert result.citations[0].law_name == "개인정보 보호법"
        assert result.citations[0].article_number == "제23조"

    def test_citation_includes_article_content(self, mocker):
        """Citation에 법령 조문 텍스트(article_content)가 포함됨"""
        mocker.patch("agents._base_agent.ChatOpenAI")
        from agents._base_agent import _parse_llm_response
        result = _parse_llm_response(
            "violation|민감정보 무단 처리|PA_23|",
            chunk_index=_SAMPLE_CHUNK_INDEX,
        )
        assert result is not None
        assert "제23조" in result.citations[0].article_content

    def test_citation_fallback_when_article_id_not_in_index(self, mocker):
        """chunk_index에 없는 article_id → fallback Citation (기본값 사용)"""
        mocker.patch("agents._base_agent.ChatOpenAI")
        from agents._base_agent import _parse_llm_response
        result = _parse_llm_response(
            "violation|알 수 없는 위반|UNKNOWN_99|some_code()",
            chunk_index=_SAMPLE_CHUNK_INDEX,
        )
        assert result is not None
        assert result.citations[0].article_id == "UNKNOWN_99"
        assert len(result.citations[0].sha256) == 64  # 기본값이라도 유효한 sha256


# ── SourceLocation 모델 테스트 ─────────────────────────────────────────────

class TestSourceLocation:
    def test_source_location_model_exists(self):
        from core.models import SourceLocation
        loc = SourceLocation(line_start=3, line_end=5, snippet="db.save(health_data)")
        assert loc.line_start == 3
        assert loc.snippet == "db.save(health_data)"

    def test_compliance_report_has_source_location_field(self):
        from core.models import ComplianceReport, ComplianceStatus, Citation, SourceLocation
        citation = Citation(
            article_id="PA_15", law_name="개인정보 보호법", article_number="제15조",
            sha256="a" * 64, url="https://www.law.go.kr/", updated_at=datetime(2025, 1, 1),
        )
        report = ComplianceReport(
            status=ComplianceStatus.VIOLATION, description="민감정보 무단 처리",
            citations=[citation],
            source_location=SourceLocation(line_start=2, line_end=3, snippet="db.save(health_data)"),
        )
        assert report.source_location.line_start == 2

    def test_compliance_report_source_location_optional(self):
        from core.models import ComplianceReport, ComplianceStatus, Citation
        citation = Citation(
            article_id="PA_15", law_name="개인정보 보호법", article_number="제15조",
            sha256="a" * 64, url="https://www.law.go.kr/", updated_at=datetime(2025, 1, 1),
        )
        report = ComplianceReport(
            status=ComplianceStatus.COMPLIANT, description="동의 확인됨", citations=[citation],
        )
        assert report.source_location is None


# ── BaseAgent.analyze() 통합 테스트 ───────────────────────────────────────

class TestBaseAgentSourceLocation:
    def test_analyze_maps_code_snippet_to_line_numbers(self, mock_llm, mocker):
        """analyze() 결과에 source_location.line_start/end가 원본 코드와 일치"""
        mocker.patch("agents._base_agent.ChatOpenAI", return_value=mock_llm)
        from agents._base_agent import BaseAgent

        code = "def foo():\n    bar = 1\n    db.save(health_data)\n    return bar\n"
        mock_llm.invoke.return_value.content = (
            "violation|민감정보 무단 처리|PA_23|db.save(health_data)"
        )
        mock_retriever = MagicMock()
        mock_retriever.search.return_value = [
            {"id": "x", "text": "제23조 내용", "score": 0.9,
             "metadata": _SAMPLE_CHUNK_INDEX["PA_23"]}
        ]
        agent = BaseAgent(retriever=mock_retriever)
        reports = agent.analyze(code)
        assert len(reports) == 1
        loc = reports[0].source_location
        assert loc is not None
        assert loc.line_start == 3
        assert "db.save" in loc.snippet

    def test_analyze_no_snippet_location_is_none(self, mock_llm, mocker):
        """code_snippet이 없으면 source_location은 None"""
        mocker.patch("agents._base_agent.ChatOpenAI", return_value=mock_llm)
        from agents._base_agent import BaseAgent

        code = "def foo():\n    pass\n"
        mock_llm.invoke.return_value.content = "compliant|동의 확인됨|PA_15"
        mock_retriever = MagicMock()
        mock_retriever.search.return_value = [
            {"id": "x", "text": "제15조 내용", "score": 0.9,
             "metadata": _SAMPLE_CHUNK_INDEX["PA_15"]}
        ]
        agent = BaseAgent(retriever=mock_retriever)
        reports = agent.analyze(code)
        assert len(reports) == 1
        assert reports[0].source_location is None

    def test_analyze_without_retriever_still_works(self, mock_llm, mocker):
        """retriever 없이도 analyze()가 동작 (fallback 모드)"""
        mocker.patch("agents._base_agent.ChatOpenAI", return_value=mock_llm)
        from agents._base_agent import BaseAgent

        code = "db.save(password)"
        mock_llm.invoke.return_value.content = (
            "violation|평문 비밀번호 저장|PA_29|db.save(password)"
        )
        agent = BaseAgent(retriever=None)
        reports = agent.analyze(code)
        assert len(reports) == 1
        assert reports[0].citations[0].article_id == "PA_29"
