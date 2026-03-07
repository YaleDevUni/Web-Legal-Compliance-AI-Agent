"""scripts/setup_index.py — 법령 수집 → SHA 비교 → 벡터 색인 전체 파이프라인"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

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
    from core.logger import logger
    from core.config import Settings
    from qdrant_client import QdrantClient

    settings = Settings()
    
    logger.info("--- Vector DB 초기화 및 전체 재색인 시작 ---")
    
    api = LawAPIClient(api_key=os.environ["LAW_API_KEY"])
    db = ArticleDB()
    qdrant = QdrantClient(url=str(settings.qdrant_url))
    idx = ArticleIndexer(qdrant_client=qdrant, collection=settings.qdrant_collection)

    # 1. Vector DB 컬렉션 초기화
    idx.recreate_collection()

    # 2. 모든 법령 데이터 가져오기
    articles: list[LawArticle] = api.fetch_all()
    all_article_ids: set[str] = {a.article_id for a in articles}
    logger.info(f"API에서 총 {len(articles)}개의 법령 조항을 가져왔습니다.")

    # 3. 모든 법령을 대상으로 upsert 수행 (강제 재색인)
    logger.info(f"총 {len(all_article_ids)}개의 조항을 재색인합니다.")
    idx.upsert(articles, changed_ids=all_article_ids)
    
    # 4. 로컬 DB에도 정보 업데이트 (SHA 기록)
    for article in articles:
        db.upsert(
            article_id=article.article_id,
            sha256=article.sha256,
            updated_at=article.updated_at,
        )
    logger.info("로컬 DB (SQLite)에 모든 조항의 SHA 및 업데이트 정보를 기록했습니다.")

    logger.info("--- 재색인 완료 ---")
