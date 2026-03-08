"""src/collector/scheduler.py — 법령 및 판례 통합 수집 스케줄러"""
from apscheduler.schedulers.background import BackgroundScheduler
from typing import List

from collector.law_list_api import LawListAPIClient
from collector.law_content_api import LawContentAPIClient
from collector.case_api import CaseAPIClient
from collector.domain import REAL_ESTATE_LAWS, CASE_KEYWORDS
from core.logger import logger
from integrity.db import ArticleDB


class LegalDataCollector:
    """법령 및 판례 수집을 오케스트레이션하는 클래스"""
    def __init__(
        self,
        list_api: LawListAPIClient,
        content_api: LawContentAPIClient,
        case_api: CaseAPIClient,
        db: ArticleDB
    ) -> None:
        self._list_api = list_api
        self._content_api = content_api
        self._case_api = case_api
        self._db = db

    def collect_all(self) -> List[str]:
        """전체 도메인 법령과 판례를 수집하고 변경된 ID 목록을 반환한다."""
        changed_ids = []
        
        # 1. 법령 수집
        logger.info("부동산 도메인 법령 수집 시작...")
        for law_name in REAL_ESTATE_LAWS:
            try:
                # MST(법령일련번호)를 가져오기 위해 검색 (nw=3: 현행법령)
                search_data = self._list_api.search_laws(query=law_name, nw=3)
                root = search_data.get("LawSearch", {})
                laws = root.get("law", [])
                if isinstance(laws, dict): laws = [laws]
                
                for law in laws:
                    mst = law.get("법령일련번호")
                    if not mst: continue
                    
                    content_data = self._content_api.fetch_law_content(mst=mst)
                    articles = self._content_api.parse_law_json(content_data)
                    
                    for art in articles:
                        if self._db.upsert(
                            art.article_id, 
                            art.sha256, 
                            art.updated_at,
                            law_name=art.law_name,
                            article_number=art.article_number,
                            content=art.content
                        ):
                            changed_ids.append(art.article_id)
                            logger.info(f"법령 조문 변경 감지: {art.article_id}")
            except Exception as e:
                logger.error(f"법령 수집 실패 ({law_name}): {e}")

        # 2. 판례 수집
        logger.info("부동산 도메인 판례 수집 시작...")
        for keyword in CASE_KEYWORDS:
            try:
                cases = self._case_api.fetch_all_by_keyword(query=keyword, max_count=50)
                for case in cases:
                    # 판례는 prefix를 붙여 구분 (DB 충돌 방지)
                    db_id = f"CASE_{case.case_id}"
                    if self._db.upsert(db_id, case.sha256, case.decision_date):
                        changed_ids.append(db_id)
                        logger.info(f"판례 변경/신규 감지: {db_id} ({case.case_number})")
            except Exception as e:
                logger.error(f"판례 수집 실패 ({keyword}): {e}")
                
        return changed_ids


class LawScheduler:
    def __init__(
        self,
        collector: LegalDataCollector,
        interval_hours: int = 24
    ) -> None:
        self._collector = collector
        self._interval_hours = interval_hours
        self._scheduler = BackgroundScheduler()

    def start(self) -> None:
        self._scheduler.add_job(
            self._collector.collect_all,
            trigger="interval",
            hours=self._interval_hours,
            id="legal_collect",
        )
        self._scheduler.start()
        logger.info(f"통합 법률 수집 스케줄러 시작 (주기: {self._interval_hours}h)")

    def stop(self) -> None:
        self._scheduler.shutdown(wait=False)
