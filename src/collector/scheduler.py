"""src/collector/scheduler.py — APScheduler 기반 주기 재수집"""
from apscheduler.schedulers.background import BackgroundScheduler

from collector.law_api import LawAPIClient
from core.logger import logger
from integrity.db import ArticleDB


class LawScheduler:
    def __init__(self, api: LawAPIClient, db: ArticleDB, interval_hours: int = 24) -> None:
        self._api = api
        self._db = db
        self._interval_hours = interval_hours
        self._scheduler = BackgroundScheduler()

    def start(self) -> None:
        self._scheduler.add_job(
            self._collect_and_check,
            trigger="interval",
            hours=self._interval_hours,
            id="law_collect",
        )
        self._scheduler.start()
        logger.info(f"법령 수집 스케줄러 시작 (주기: {self._interval_hours}h)")

    def stop(self) -> None:
        self._scheduler.shutdown(wait=False)

    def _collect_and_check(self) -> list[str]:
        """법령을 수집하고 해시가 변경된 article_id 목록을 반환한다."""
        changed_ids: list[str] = []
        articles = self._api.fetch_all()
        for article in articles:
            changed = self._db.upsert(article.article_id, article.sha256, article.updated_at)
            if changed:
                changed_ids.append(article.article_id)
                logger.info(f"변경 감지: {article.article_id}")
        return changed_ids
