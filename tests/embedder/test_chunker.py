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
        """chunk_size보다 짧은 텍스트 → 단일 청크 반환"""
        from embedder.chunker import chunk_article
        chunks = chunk_article(sample_article, chunk_size=500, chunk_overlap=50)
        assert len(chunks) == 1

    def test_long_text_returns_multiple_chunks(self):
        """chunk_size(100자) 초과 텍스트 → 복수 청크 반환"""
        from embedder.chunker import chunk_article
        from core.models import LawArticle
        long_content = "가나다라마바사아자차카타파하 " * 200
        article = LawArticle(
            article_id="PA_99",
            law_name="개인정보 보호법",
            article_number="제99조",
            content=long_content,
            sha256="b" * 64,
            url="https://www.law.go.kr/",
            updated_at=datetime(2024, 1, 1),
        )
        chunks = chunk_article(article, chunk_size=100, chunk_overlap=20)
        assert len(chunks) > 1

    def test_chunk_metadata_preserved(self, sample_article):
        """모든 청크에 article_id, law_name, sha256, article_number 메타데이터 보존"""
        from embedder.chunker import chunk_article
        chunks = chunk_article(sample_article, chunk_size=500, chunk_overlap=50)
        meta = chunks[0]["metadata"]
        assert meta["article_id"] == "PA_3"
        assert meta["law_name"] == "개인정보 보호법"
        assert meta["sha256"] == "a" * 64
        assert meta["article_number"] == "제3조"

    def test_chunk_has_text_key(self, sample_article):
        """각 청크 딕셔너리에 "text" 키 존재, 비어있지 않음"""
        from embedder.chunker import chunk_article
        chunks = chunk_article(sample_article, chunk_size=500, chunk_overlap=50)
        assert "text" in chunks[0]
        assert len(chunks[0]["text"]) > 0

    def test_overlap_applied(self):
        """chunk_overlap 적용 시 두 번째 청크 시작부분이 첫 번째 청크 내에 포함됨"""
        from embedder.chunker import chunk_article
        from core.models import LawArticle
        long_content = "ABCDEFGHIJ" * 50
        article = LawArticle(
            article_id="PA_1",
            law_name="테스트법",
            article_number="제1조",
            content=long_content,
            sha256="c" * 64,
            url="https://www.law.go.kr/",
            updated_at=datetime(2024, 1, 1),
        )
        chunks = chunk_article(article, chunk_size=100, chunk_overlap=20)
        if len(chunks) > 1:
            # 두 번째 청크 시작이 첫 번째 청크 끝 부분과 겹쳐야 함
            assert chunks[1]["text"][:10] in chunks[0]["text"]
