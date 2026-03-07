"""tests/agents/test_citation.py — Citation Assembler TDD

테스트 전략:
- CitationAssembler가 검색 결과(chunks)를 Citation 객체 리스트로 변환
- 중복 article_id 제거 후 단일 Citation 반환
- sha256 + url + updated_at 필드 정확히 부착
- 결과가 core.models.Citation 인스턴스임을 확인
- 빈 입력 → 빈 리스트 반환
"""
import pytest
from datetime import datetime


SAMPLE_CHUNKS = [
    {
        "id": "PA_3",
        "text": "개인정보처리자는 처리 목적을 명확하게 하여야 한다.",
        "score": 0.9,
        "metadata": {
            "article_id": "PA_3",
            "law_name": "개인정보 보호법",
            "article_number": "제3조",
            "sha256": "a" * 64,
            "url": "https://www.law.go.kr/",
            "updated_at": "2024-01-01T00:00:00",
        },
    },
    {
        "id": "PA_3",
        "text": "개인정보처리자는 처리 목적을 명확하게 하여야 한다. (중복)",
        "score": 0.85,
        "metadata": {
            "article_id": "PA_3",
            "law_name": "개인정보 보호법",
            "article_number": "제3조",
            "sha256": "a" * 64,
            "url": "https://www.law.go.kr/",
            "updated_at": "2024-01-01T00:00:00",
        },
    },
    {
        "id": "PA_17",
        "text": "제17조 개인정보처리자는 제3자에게 개인정보를 제공할 수 있다.",
        "score": 0.8,
        "metadata": {
            "article_id": "PA_17",
            "law_name": "개인정보 보호법",
            "article_number": "제17조",
            "sha256": "b" * 64,
            "url": "https://www.law.go.kr/",
            "updated_at": "2024-03-15T00:00:00",
        },
    },
]


class TestCitationAssembler:
    def test_returns_citation_list(self):
        """결과가 Citation 인스턴스 리스트임을 확인"""
        from agents.citation import CitationAssembler
        from core.models import Citation
        assembler = CitationAssembler()
        citations = assembler.assemble(SAMPLE_CHUNKS)
        assert all(isinstance(c, Citation) for c in citations)

    def test_deduplicates_by_article_id(self):
        """중복 article_id(PA_3) → 단 하나의 Citation만 반환"""
        from agents.citation import CitationAssembler
        assembler = CitationAssembler()
        citations = assembler.assemble(SAMPLE_CHUNKS)
        ids = [c.article_id for c in citations]
        assert ids.count("PA_3") == 1

    def test_sha256_attached(self):
        """Citation에 sha256 필드가 정확히 부착됨"""
        from agents.citation import CitationAssembler
        assembler = CitationAssembler()
        citations = assembler.assemble(SAMPLE_CHUNKS)
        pa3 = next(c for c in citations if c.article_id == "PA_3")
        assert pa3.sha256 == "a" * 64

    def test_empty_input_returns_empty(self):
        """빈 청크 리스트 → 빈 리스트 반환"""
        from agents.citation import CitationAssembler
        assembler = CitationAssembler()
        assert assembler.assemble([]) == []

    def test_all_unique_articles_present(self):
        """고유 article_id 수만큼 Citation 반환 (PA_3, PA_17)"""
        from agents.citation import CitationAssembler
        assembler = CitationAssembler()
        citations = assembler.assemble(SAMPLE_CHUNKS)
        ids = {c.article_id for c in citations}
        assert ids == {"PA_3", "PA_17"}
