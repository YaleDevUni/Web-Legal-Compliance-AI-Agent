"""src/embedder/chunker.py — 법령 조항 텍스트 청킹"""
from core.models import LawArticle


def chunk_article(article: LawArticle) -> list[dict]:
    """LawArticle을 의미 단위(문단)로 분할하고, 각 청크에 제목을 추가한다.

    반환 형식: [{"text": str, "metadata": dict}, ...]
    """
    # full_content: 어떤 문단 청크가 검색되더라도 전체 조문을 LLM에 제공하기 위해 metadata에 저장
    metadata = {
        "article_id": article.article_id,
        "law_name": article.law_name,
        "article_number": article.article_number,
        "sha256": article.sha256,
        "url": str(article.url),
        "updated_at": article.updated_at.isoformat(),
        "full_content": article.content,
    }
    title_prefix = f"{article.law_name} {article.article_number}"

    paragraphs = [p.strip() for p in article.content.split('\n') if p.strip()]

    chunks = []
    if paragraphs:
        for p_text in paragraphs:
            chunk_text = f"{title_prefix}\n{p_text}"
            chunks.append({"text": chunk_text, "metadata": metadata})
    else:
        chunk_text = f"{title_prefix}\n{article.content}"
        chunks.append({"text": chunk_text, "metadata": metadata})

    return chunks
