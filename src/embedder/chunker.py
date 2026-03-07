"""src/embedder/chunker.py — 법령 조항 텍스트 청킹"""
from langchain_text_splitters import RecursiveCharacterTextSplitter

from core.models import LawArticle


def chunk_article(
    article: LawArticle,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> list[dict]:
    """LawArticle을 청크 리스트로 분할한다.

    반환 형식: [{"text": str, "metadata": dict}, ...]
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    texts = splitter.split_text(article.content)
    metadata = {
        "article_id": article.article_id,
        "law_name": article.law_name,
        "article_number": article.article_number,
        "sha256": article.sha256,
        "url": str(article.url),
        "updated_at": article.updated_at.isoformat(),
    }
    return [{"text": t, "metadata": metadata} for t in texts]
