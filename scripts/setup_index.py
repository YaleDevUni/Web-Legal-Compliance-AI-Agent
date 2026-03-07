"""scripts/setup_index.py — 법령 수집 → SHA 비교 → 벡터 색인 전체 파이프라인"""
from core.models import LawArticle


def run_setup_index(api_client, db, indexer) -> set[str]:
    """법령 수집 → SHA 비교 → 변경 조항만 벡터 색인.

    반환: 변경이 감지된 article_id 집합.
    """
    articles: list[LawArticle] = api_client.fetch_all()
    changed_ids: set[str] = set()

    for article in articles:
        changed = db.upsert(
            article_id=article.article_id,
            sha256=article.sha256,
            updated_at=article.updated_at,
        )
        if changed:
            changed_ids.add(article.article_id)

    if changed_ids:
        indexer.upsert(articles, changed_ids=changed_ids)

    return changed_ids


if __name__ == "__main__":
    import os
    from collector.law_api import LawAPIClient
    from integrity.db import ArticleDB
    from embedder.indexer import ArticleIndexer

    api = LawAPIClient(api_key=os.environ["LAW_API_KEY"])
    db = ArticleDB()
    idx = ArticleIndexer()
    changed = run_setup_index(api_client=api, db=db, indexer=idx)
    print(f"변경된 조항: {len(changed)}개 — {changed}")
