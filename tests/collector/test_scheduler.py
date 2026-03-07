"""tests/collector/test_scheduler.py — APScheduler mock TDD

테스트 전략:
- BackgroundScheduler를 mocker.patch로 대체하여 실제 스케줄링 없이 동작 검증
- _collect_and_check(): fetch_all → upsert → 변경 id 반환 전체 흐름 확인
- start(): add_job / start 호출 여부로 스케줄 등록 검증
"""
import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime


@pytest.fixture
def mock_api(mocker):
    api = mocker.MagicMock()
    api.fetch_all.return_value = []
    return api


@pytest.fixture
def mock_db(mocker):
    db = mocker.MagicMock()
    db.upsert.return_value = True
    return db


class TestLawScheduler:
    def test_scheduler_registers_job(self, mocker, mock_api, mock_db):
        """start() 호출 시 BackgroundScheduler.add_job / start 호출 확인"""
        from collector.scheduler import LawScheduler
        mock_sched = mocker.patch("collector.scheduler.BackgroundScheduler")
        scheduler = LawScheduler(api=mock_api, db=mock_db, interval_hours=24)
        scheduler.start()
        mock_sched.return_value.add_job.assert_called_once()
        mock_sched.return_value.start.assert_called_once()

    def test_collect_and_check_calls_upsert(self, mocker, mock_api, mock_db):
        """_collect_and_check() → db.upsert(article_id, sha256, updated_at) 호출 확인"""
        from collector.scheduler import LawScheduler
        from core.models import LawArticle

        article = LawArticle(
            article_id="PA_3",
            law_name="개인정보 보호법",
            article_number="제3조",
            content="처리 목적을 명확하게",
            sha256="a" * 64,
            url="https://www.law.go.kr/",
            updated_at=datetime(2024, 1, 1),
        )
        mock_api.fetch_all.return_value = [article]

        mocker.patch("collector.scheduler.BackgroundScheduler")
        scheduler = LawScheduler(api=mock_api, db=mock_db, interval_hours=24)
        scheduler._collect_and_check()

        mock_db.upsert.assert_called_once_with("PA_3", "a" * 64, datetime(2024, 1, 1))

    def test_collect_returns_changed_ids(self, mocker, mock_api, mock_db):
        """upsert가 True를 반환한 조항의 article_id가 결과 리스트에 포함됨"""
        from collector.scheduler import LawScheduler
        from core.models import LawArticle

        article = LawArticle(
            article_id="PA_17",
            law_name="개인정보 보호법",
            article_number="제17조",
            content="제3자 제공",
            sha256="b" * 64,
            url="https://www.law.go.kr/",
            updated_at=datetime(2024, 1, 1),
        )
        mock_api.fetch_all.return_value = [article]
        mock_db.upsert.return_value = True  # 변경됨

        mocker.patch("collector.scheduler.BackgroundScheduler")
        scheduler = LawScheduler(api=mock_api, db=mock_db, interval_hours=24)
        changed = scheduler._collect_and_check()

        assert "PA_17" in changed
