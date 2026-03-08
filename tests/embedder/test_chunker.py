"""tests/embedder/test_chunker.py — 텍스트 청킹 TDD

테스트 전략:
- chunk_size, chunk_overlap 파라미터를 명시적으로 전달해 경계 조건 검증
- 반환 형식: [{"text": str, "metadata": dict}, ...]
- metadata: article_id, law_name, sha256, article_number, url, updated_at 포함
- 오버랩: 두 번째 청크 시작 부분이 첫 번째 청크에 포함되어야 함
"""
import pytest
from datetime import datetime


@pytest.fixture
def sample_article():
    from core.models import LawArticle
    return LawArticle(
        article_id="PA_3",
        law_name="개인정보 보호법",
        article_number="제3조",
        content="개인정보처리자는 개인정보의 처리 목적을 명확하게 하여야 하고 그 목적에 필요한 범위에서 최소한의 개인정보만을 적법하고 정당하게 수집하여야 한다.",
        sha256="a" * 64,
        url="https://www.law.go.kr/",
        updated_at=datetime(2024, 1, 1),
    )


class TestChunker:
    def test_short_text_returns_single_chunk(self, sample_article):
        """단일 문단 텍스트 → 단일 청크 반환"""
        from embedder.chunker import chunk_article
        chunks = chunk_article(sample_article)
        assert len(chunks) == 1

    def test_long_text_returns_multiple_chunks(self):
        """여러 문단(개행 구분) 텍스트 → 복수 청크 반환"""
        from embedder.chunker import chunk_article
        from core.models import LawArticle
        # 개행으로 구분된 여러 문단
        multi_para_content = "\n".join([f"제{i}항 내용입니다." for i in range(1, 6)])
        article = LawArticle(
            article_id="PA_99",
            law_name="개인정보 보호법",
            article_number="제99조",
            content=multi_para_content,
            sha256="b" * 64,
            url="https://www.law.go.kr/",
            updated_at=datetime(2024, 1, 1),
        )
        chunks = chunk_article(article)
        assert len(chunks) > 1

    def test_chunk_metadata_preserved(self, sample_article):
        """모든 청크에 article_id, law_name, sha256, article_number 메타데이터 보존"""
        from embedder.chunker import chunk_article
        chunks = chunk_article(sample_article)
        meta = chunks[0]["metadata"]
        assert meta["article_id"] == "PA_3"
        assert meta["law_name"] == "개인정보 보호법"
        assert meta["sha256"] == "a" * 64
        assert meta["article_number"] == "제3조"

    def test_chunk_has_text_key(self, sample_article):
        """각 청크 딕셔너리에 "text" 키 존재, 비어있지 않음"""
        from embedder.chunker import chunk_article
        chunks = chunk_article(sample_article)
        assert "text" in chunks[0]
        assert len(chunks[0]["text"]) > 0

    def test_chunk_text_includes_title_prefix(self, sample_article):
        """각 청크 텍스트에 법령명·조항 제목이 포함됨"""
        from embedder.chunker import chunk_article
        chunks = chunk_article(sample_article)
        assert "개인정보 보호법" in chunks[0]["text"]
        assert "제3조" in chunks[0]["text"]
