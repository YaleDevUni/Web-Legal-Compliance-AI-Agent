"""tests/core/test_models.py — LawArticle, Citation, ComplianceReport TDD

테스트 전략:
- Pydantic ValidationError 발생 여부로 유효성 검증 확인
- LawArticle: article_id 필수, sha256 64자 hex, content 비어있으면 안 됨, url 유효해야 함
- Citation: short_sha(앞 8자), format() → "[법령명 조항 · sha:xxxx · 날짜]" 포맷 검증
- ComplianceReport: COMPLIANT/VIOLATION enum, citations 최소 1개 필수
"""
import pytest
from datetime import datetime
from pydantic import ValidationError


# ── LawArticle ─────────────────────────────────────────────────────────────────

class TestLawArticle:
    def test_valid_law_article(self):
        """모든 필드가 유효할 때 객체 정상 생성"""
        from core.models import LawArticle
        article = LawArticle(
            article_id="PA_001_0030",
            law_name="개인정보 보호법",
            article_number="제3조",
            content="개인정보처리자는 개인정보의 처리 목적을 명확하게 하여야 한다.",
            sha256="a3f2c1d4e5b678901234567890abcdef1234567890abcdef1234567890abcdef",
            url="https://www.law.go.kr/법령/개인정보보호법",
            updated_at=datetime(2024, 3, 15),
        )
        assert article.article_id == "PA_001_0030"
        assert article.law_name == "개인정보 보호법"
        assert article.article_number == "제3조"
        assert article.sha256 == "a3f2c1d4e5b678901234567890abcdef1234567890abcdef1234567890abcdef"

    def test_missing_required_field_raises(self):
        """article_id 누락 시 ValidationError 발생"""
        from core.models import LawArticle
        with pytest.raises(ValidationError):
            LawArticle(
                law_name="개인정보 보호법",
                content="본문",
                sha256="abc",
                url="https://example.com",
                updated_at=datetime.now(),
            )  # article_id 누락

    def test_sha256_must_be_64_hex_chars(self):
        """sha256에 64자 hex가 아닌 값 입력 시 ValidationError 발생"""
        from core.models import LawArticle
        with pytest.raises(ValidationError):
            LawArticle(
                article_id="PA_001_0030",
                law_name="개인정보 보호법",
                article_number="제3조",
                content="본문",
                sha256="too_short",  # 유효하지 않은 SHA-256
                url="https://example.com",
                updated_at=datetime.now(),
            )

    def test_url_must_be_valid(self):
        """유효하지 않은 URL 입력 시 ValidationError 발생"""
        from core.models import LawArticle
        with pytest.raises(ValidationError):
            LawArticle(
                article_id="PA_001_0030",
                law_name="개인정보 보호법",
                article_number="제3조",
                content="본문",
                sha256="a" * 64,
                url="not-a-valid-url",
                updated_at=datetime.now(),
            )

    def test_content_must_not_be_empty(self):
        """빈 문자열 content 입력 시 ValidationError 발생"""
        from core.models import LawArticle
        with pytest.raises(ValidationError):
            LawArticle(
                article_id="PA_001_0030",
                law_name="개인정보 보호법",
                article_number="제3조",
                content="",  # 빈 문자열
                sha256="a" * 64,
                url="https://www.law.go.kr/",
                updated_at=datetime.now(),
            )


# ── Citation ───────────────────────────────────────────────────────────────────

class TestCitation:
    def test_valid_citation(self):
        """유효한 Citation 객체 생성 확인"""
        from core.models import Citation
        citation = Citation(
            law_name="개인정보 보호법",
            article_number="제17조",
            sha256="a3f2c1d4e5b678901234567890abcdef1234567890abcdef1234567890abcdef",
            url="https://www.law.go.kr/법령/개인정보보호법",
            updated_at=datetime(2024, 1, 1),
        )
        assert citation.law_name == "개인정보 보호법"
        assert citation.article_number == "제17조"

    def test_citation_short_sha_property(self):
        """short_sha 프로퍼티가 sha256 앞 8자를 반환하는지 확인"""
        from core.models import Citation
        sha = "a3f2c1d4" + "e" * 56
        citation = Citation(
            law_name="개인정보 보호법",
            article_number="제17조",
            sha256=sha,
            url="https://www.law.go.kr/",
            updated_at=datetime(2024, 1, 1),
        )
        assert citation.short_sha == sha[:8]

    def test_citation_format_string(self):
        """format() → [법령명 조항 · sha:xxxx · 날짜] 포맷 검증"""
        from core.models import Citation
        sha = "a3f2c1d4" + "e" * 56
        citation = Citation(
            law_name="개인정보 보호법",
            article_number="제17조",
            sha256=sha,
            url="https://www.law.go.kr/",
            updated_at=datetime(2024, 1, 1),
        )
        fmt = citation.format()
        assert "개인정보 보호법" in fmt
        assert "제17조" in fmt
        assert "a3f2c1d4" in fmt
        assert "2024-01-01" in fmt


# ── ComplianceReport ───────────────────────────────────────────────────────────

class TestComplianceReport:
    def _make_citation(self):
        from core.models import Citation
        return Citation(
            law_name="개인정보 보호법",
            article_number="제17조",
            sha256="a" * 64,
            url="https://www.law.go.kr/",
            updated_at=datetime(2024, 1, 1),
        )

    def test_compliant_report(self):
        """COMPLIANT 상태: is_compliant=True, is_violation=False"""
        from core.models import ComplianceReport, ComplianceStatus
        report = ComplianceReport(
            status=ComplianceStatus.COMPLIANT,
            description="개인정보 처리방침 하단 게시 확인",
            citations=[self._make_citation()],
        )
        assert report.status == ComplianceStatus.COMPLIANT
        assert report.is_compliant is True
        assert report.is_violation is False

    def test_violation_report(self):
        """VIOLATION 상태: is_violation=True, is_compliant=False"""
        from core.models import ComplianceReport, ComplianceStatus
        report = ComplianceReport(
            status=ComplianceStatus.VIOLATION,
            description="비밀번호 평문 저장 감지",
            citations=[self._make_citation()],
            recommendation="bcrypt / argon2 해싱 적용",
        )
        assert report.status == ComplianceStatus.VIOLATION
        assert report.is_violation is True
        assert report.is_compliant is False

    def test_report_requires_at_least_one_citation(self):
        """citations=[] → ValidationError (min_length=1 제약)"""
        from core.models import ComplianceReport, ComplianceStatus
        with pytest.raises(ValidationError):
            ComplianceReport(
                status=ComplianceStatus.COMPLIANT,
                description="설명",
                citations=[],  # 빈 citations
            )
