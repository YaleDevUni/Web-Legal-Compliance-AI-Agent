"""src/embedder/chunker.py — 법령 조항 텍스트 청킹"""
from core.models import LawArticle


def chunk_article(article: LawArticle) -> list[dict]:
    """LawArticle을 의미 단위(문단)로 분할하고, 각 청크에 제목을 추가한다.

    반환 형식: [{"text": str, "metadata": dict}, ...]
    """
    metadata = {
        "article_id": article.article_id,
        "law_name": article.law_name,
        "article_number": article.article_number,
        "sha256": article.sha256,
        "url": str(article.url),
        "updated_at": article.updated_at.isoformat(),
    }
    # 검색 시 컨텍스트를 풍부하게 하기 위해 모든 청크에 제목을 추가
    title_prefix = f"{article.law_name} {article.article_number}"

    # 파서에서 줄바꿈(\n)으로 문단을 구분했으므로, 이를 기준으로 분할
    paragraphs = [p.strip() for p in article.content.split('\n') if p.strip()]
    
    chunks = []
    if paragraphs:
        for p_text in paragraphs:
            # 모든 문단 청크에 제목을 덧붙임
            chunk_text = f"{title_prefix}\n{p_text}"
            chunks.append({"text": chunk_text, "metadata": metadata})
    else:
        # 문단 분할에 실패한 경우, 전체 내용을 하나의 청크로 사용
        chunk_text = f"{title_prefix}\n{article.content}"
        chunks.append({"text": chunk_text, "metadata": metadata})

    return chunks
