"""tests/embedder/test_chunker.py — 계층형 청킹 TDD"""
import pytest
from datetime import datetime
from core.models import LawArticle, CaseArticle
from embedder.chunker import chunk_article, chunk_case

@pytest.fixture
def sample_law():
    return LawArticle(
        article_id="L123_2",
        law_name="주택법",
        article_number="제2조",
        content="제2조(정의) 이 법에서 사용하는 용어의 뜻은 다음과 같다.\n① \"민간임대주택\"이란...\n1. \"민간건설임대주택\"이란...",
        sha256="a"*64,
        url="http://test.com",
        updated_at=datetime.now()
    )

@pytest.fixture
def sample_case():
    return CaseArticle(
        case_id="C456",
        case_number="2024다456",
        case_name="사건",
        court="법원",
        decision_date=datetime.now(),
        decision_type="판결",
        ruling_summary="[1] 판시사항 1<br/>[2] 판시사항 2",
        ruling_text="[1] 판결요지 1<br/>[2] 판결요지 2",
        url="http://test.com",
        sha256="b"*64
    )

class TestChunker:
    def test_chunk_article_hierarchy(self, sample_law):
        """법령 조문이 항/호 계층별로 청킹되고 메타데이터가 보존되는지 확인"""
        chunks = chunk_article(sample_law)
        
        # 줄 수만큼 청크 생성 (3줄)
        assert len(chunks) == 3
        
        # 첫 번째 청크 (조문 제목)
        assert chunks[0]["metadata"]["paragraph"] == ""
        assert "제2조(정의)" in chunks[0]["text"]
        
        # 두 번째 청크 (항)
        assert chunks[1]["metadata"]["paragraph"] == "①"
        assert "① \"민간임대주택\"" in chunks[1]["text"]
        
        # 세 번째 청크 (호)
        assert chunks[2]["metadata"]["subparagraph"] == "1."
        assert "1. \"민간건설임대주택\"" in chunks[2]["text"]
        
        # 공통 메타데이터
        assert chunks[0]["metadata"]["doc_type"] == "law"
        assert chunks[0]["metadata"]["law_name"] == "주택법"

    def test_chunk_case_sections(self, sample_case):
        """판례가 판시사항/판결요지 섹션별로 청킹되는지 확인"""
        chunks = chunk_case(sample_case)
        
        # 판시사항 2개 + 판결요지 2개 = 4개
        assert len(chunks) == 4
        
        # 메타데이터 확인
        assert chunks[0]["metadata"]["doc_type"] == "case"
        assert chunks[0]["metadata"]["section"] == "summary"
        assert "[2024다456 판시사항]" in chunks[0]["text"]
        
        assert chunks[2]["metadata"]["section"] == "ruling"
        assert "[2024다456 판결요지]" in chunks[2]["text"]

    def test_empty_content_fallback(self):
        """내용이 없는 경우 최소 1개의 청크를 반환하는지 확인"""
        art = LawArticle(
            article_id="EMPTY", law_name="법", content="내용 없음", sha256="c"*64, 
            url="http://t.com", updated_at=datetime.now()
        )
        chunks = chunk_article(art)
        assert len(chunks) == 1
        assert chunks[0]["metadata"]["article_id"] == "EMPTY"
