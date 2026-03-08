"""tests/collector/test_scheduler.py — 통합 수집 스케줄러 TDD"""
import pytest
from datetime import datetime
from core.models import LawArticle, CaseArticle
from collector.scheduler import LegalDataCollector, LawScheduler

@pytest.fixture
def mock_clients(mocker):
    return {
        "list": mocker.MagicMock(),
        "content": mocker.MagicMock(),
        "case": mocker.MagicMock(),
        "db": mocker.MagicMock()
    }

class TestLegalDataCollector:
    def test_collect_all_orchestration(self, mocker, mock_clients):
        """법령 및 판례 수집 흐름이 올바르게 호출되는지 확인"""
        # Mock 도메인 데이터
        mocker.patch("collector.scheduler.REAL_ESTATE_LAWS", ["주택법"])
        mocker.patch("collector.scheduler.CASE_KEYWORDS", ["전세사기"])
        
        # Mock Law API responses
        mock_clients["list"].search_laws.return_value = {
            "LawSearch": {"law": [{"법령일련번호": "123"}]}
        }
        law_art = LawArticle(
            article_id="L123_1",
            law_name="주택법",
            article_number="제1조",
            content="목적",
            sha256="a"*64,
            url="http://test.com",
            updated_at=datetime.now()
        )
        mock_clients["content"].parse_law_json.return_value = [law_art]
        
        # Mock Case API responses
        case_art = CaseArticle(
            case_id="C456",
            case_number="2024다456",
            case_name="사건",
            court="법원",
            decision_date=datetime.now(),
            decision_type="판결",
            ruling_summary="요약",
            ruling_text="본문",
            url="http://test.com",
            sha256="b"*64
        )
        mock_clients["case"].fetch_all_by_keyword.return_value = [case_art]
        
        # DB mock
        mock_clients["db"].upsert.return_value = True # 둘 다 변경됨으로 가정
        
        collector = LegalDataCollector(
            mock_clients["list"],
            mock_clients["content"],
            mock_clients["case"],
            mock_clients["db"]
        )
        
        changed_ids = collector.collect_all()
        
        assert "L123_1" in changed_ids
        assert "CASE_C456" in changed_ids
        assert mock_clients["db"].upsert.call_count == 2

class TestLawScheduler:
    def test_scheduler_starts(self, mocker, mock_clients):
        """스케줄러 시작 시 add_job 호출 확인"""
        mock_sched_class = mocker.patch("collector.scheduler.BackgroundScheduler")
        collector = LegalDataCollector(
            mock_clients["list"], mock_clients["content"], mock_clients["case"], mock_clients["db"]
        )
        scheduler = LawScheduler(collector=collector)
        scheduler.start()
        
        mock_sched_class.return_value.add_job.assert_called_once()
        mock_sched_class.return_value.start.assert_called_once()
