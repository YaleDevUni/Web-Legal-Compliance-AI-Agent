"""scripts/load_html_laws.py — data/laws/*.html 법령 파일 → 색인 파이프라인

실행:
    uv run python scripts/load_html_laws.py

흐름:
    HTML 파싱(parse_law_html) → SHA 비교(ArticleDB) → 변경분 벡터 색인(ArticleIndexer)
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from qdrant_client import QdrantClient

from collector.parser import parse_law_html
from core.config import Settings
from integrity.db import ArticleDB
from embedder.indexer import ArticleIndexer
from core.logger import logger
from core.models import LawArticle

# 파일명 → article_id 접두사 매핑
LAW_PREFIX_MAP: dict[str, str] = {
    "개인정보보호법.html":      "PA",
    "정보통신법.html":          "IC",
    "위치정보법.html":          "LI",
    "안정성확보조치기준.html":  "SA",
    "전자상거래법.html":        "EC",
    "청소년보호법.html":        "YP",
    "신용정보법.html":          "CI",
}

LAWS_DIR = Path(__file__).parent.parent / "data" / "laws"


def load_html_laws(force_reindex: bool = False) -> None:
    """data/laws/*.html을 파싱해 SHA 비교 후 변경분만 벡터 색인."""
    settings = Settings()
    db = ArticleDB()
    qdrant = QdrantClient(url=str(settings.qdrant_url))
    indexer = ArticleIndexer(qdrant_client=qdrant)

    if force_reindex:
        logger.info("--- Vector DB 초기화 및 전체 재색인 시작 (로컬 HTML) ---")
        indexer.recreate_collection("laws")
    
    all_articles_from_files: list[LawArticle] = []
    total_parsed = 0
    
    for fname, prefix in LAW_PREFIX_MAP.items():
        path = LAWS_DIR / fname
        if not path.exists():
            logger.warning(f"[SKIP] {fname} — 파일 없음")
            continue

        html = path.read_text(encoding="utf-8", errors="replace")
        articles = parse_law_html(html, law_id_prefix=prefix)
        all_articles_from_files.extend(articles)

        if not articles:
            logger.warning(f"[WARN] {fname} — 조문 0개 (파일 확인 필요)")
            continue
        total_parsed += len(articles)

    if force_reindex:
        logger.info(f"로컬 HTML에서 총 {len(all_articles_from_files)}개의 조항을 재색인합니다.")
        indexer.upsert_laws(all_articles_from_files)
        # Update local DB for all
        for article in all_articles_from_files:
            db.upsert(
                article_id=article.article_id,
                sha256=article.sha256,
                updated_at=article.updated_at,
                law_name=article.law_name,
                article_number=article.article_number,
                content=article.content,
            )
        total_changed = len(all_articles_from_files)
    else:
        changed_ids: set[str] = set()
        for article in all_articles_from_files:
            changed = db.upsert(
                article_id=article.article_id,
                sha256=article.sha256,
                updated_at=article.updated_at,
                law_name=article.law_name,
                article_number=article.article_number,
                content=article.content,
            )
            if changed:
                changed_ids.add(article.article_id)

        if changed_ids:
            indexer.upsert_laws(all_articles_from_files, changed_ids=changed_ids)
        total_changed = len(changed_ids)
        
    logger.info(f"\n완료 — 총 {total_parsed}개 조문 파싱, {total_changed}개 변경분/전체 색인")


if __name__ == "__main__":
    logger.info("--- 로컬 HTML 법령 파일 색인 시작 ---")
    load_html_laws(force_reindex=True)
    logger.info("--- 로컬 HTML 법령 파일 색인 완료 ---")
