"""scripts/setup_index.py — 법령 및 판례 수집 → 벡터 색인 전체 파이프라인"""
import os
import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from qdrant_client import QdrantClient
from core.config import Settings
from core.logger import logger
from collector.law_list_api import LawListAPIClient
from collector.law_content_api import LawContentAPIClient
from collector.case_api import CaseAPIClient
from collector.domain import REAL_ESTATE_LAWS, CASE_KEYWORDS
from integrity.db import ArticleDB
from embedder.indexer import ArticleIndexer


def run_indexing(args):
    settings = Settings()
    db = ArticleDB()
    qdrant = QdrantClient(url=str(settings.qdrant_url))
    
    api_key = settings.law_api_key
    list_api = LawListAPIClient(api_key=api_key)
    content_api = LawContentAPIClient(api_key=api_key)
    case_api = CaseAPIClient(api_key=api_key)
    
    indexer = ArticleIndexer(qdrant_client=qdrant)

    if args.reset:
        logger.info("컬렉션 초기화 시작...")
        if not args.cases_only:
            indexer.recreate_collection("laws")
        if not args.laws_only:
            indexer.recreate_collection("cases")

    # 1. 법령 수집 및 색인
    if not args.cases_only:
        logger.info("=== 법령 수집 및 색인 시작 ===")
        all_articles = []
        changed_law_ids = set()
        
        for law_name in REAL_ESTATE_LAWS:
            try:
                search_data = list_api.search_laws(query=law_name, nw=3)
                laws = search_data.get("LawSearch", {}).get("law", [])
                if isinstance(laws, dict): laws = [laws]
                
                for law in laws:
                    mst = law.get("법령일련번호")
                    if not mst: continue
                    
                    content_data = content_api.fetch_law_content(mst=mst)
                    articles = content_api.parse_law_json(content_data)
                    all_articles.extend(articles)
                    
                    for art in articles:
                        # reset 모드면 무조건 변경된 것으로 간주하여 색인 대상에 포함
                        changed = db.upsert(
                            art.article_id, art.sha256, art.updated_at,
                            law_name=art.law_name,
                            article_number=art.article_number,
                            content=art.content
                        )
                        if changed or args.reset:
                            changed_law_ids.add(art.article_id)
            except Exception as e:
                logger.error(f"법령 수집 실패 ({law_name}): {e}")
        
        if changed_law_ids:
            logger.info(f"변경된 법령 조문 {len(changed_law_ids)}개 색인 중...")
            indexer.upsert_laws(all_articles, changed_ids=changed_law_ids if not args.reset else None)
        else:
            logger.info("변경된 법령 조문이 없습니다.")

    # 2. 판례 수집 및 색인
    if not args.laws_only:
        logger.info("=== 판례 수집 및 색인 시작 ===")
        all_cases = []
        changed_case_ids = set()
        
        for keyword in CASE_KEYWORDS:
            try:
                cases = case_api.fetch_all_by_keyword(query=keyword, max_count=50)
                all_cases.extend(cases)
                
                for case in cases:
                    db_id = f"CASE_{case.case_id}"
                    changed = db.upsert(
                        db_id, case.sha256, case.decision_date,
                        law_name=case.case_name,
                        article_number=case.case_number,
                        content=case.ruling_text
                    )
                    if changed or args.reset:
                        changed_case_ids.add(db_id)
            except Exception as e:
                logger.error(f"판례 수집 실패 ({keyword}): {e}")
                
        if changed_case_ids:
            logger.info(f"변경된 판례 {len(changed_case_ids)}개 색인 중...")
            indexer.upsert_cases(all_cases, changed_ids=changed_case_ids if not args.reset else None)
        else:
            logger.info("변경된 판례가 없습니다.")

    logger.info("=== 모든 색인 작업 완료 ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="법령 및 판례 색인 스크립트")
    parser.add_argument("--reset", action="store_true", help="기존 컬렉션 삭제 후 전체 재색인")
    parser.add_argument("--laws-only", action="store_true", help="법령만 색인")
    parser.add_argument("--cases-only", action="store_true", help="판례만 색인")
    
    args = parser.parse_args()
    run_indexing(args)
