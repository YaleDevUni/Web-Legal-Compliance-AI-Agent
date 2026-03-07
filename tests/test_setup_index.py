"""tests/test_setup_index.py — setup_index.py 전체 파이프라인 TDD

테스트 전략:
- 수집(LawAPIClient) → SHA 비교(ArticleDB) → 임베딩(ArticleIndexer) 전체 흐름을 mock으로 검증
- run_setup_index(api_client, db, indexer) → 변경 article_id 집합 반환
- 변경된 조항만 indexer.upsert에 전달됨 확인
- 변경 없을 경우 indexer.upsert 미호출 확인 (또는 빈 set 전달)
- 중복 실행 시 같은 hash → upsert 재호출 없음
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime


@pytest.fixture
def mock_article():
    """테스트용 LawArticle 픽스처"""
    from core.models import LawArticle
    return LawArticle(
        article_id="PA_3",
        law_name="개인정보 보호법",
        article_number="제3조",
        content="개인정보처리자는 처리 목적을 명확하게 하여야 한다.",
        sha256="a" * 64,
        url="https://www.law.go.kr/",
        updated_at=datetime(2024, 1, 1),
    )


class TestSetupIndex:
    def test_returns_changed_ids(self, mock_article):
        """변경된 조항 article_id 집합 반환"""
        from scripts.setup_index import run_setup_index

        api_client = MagicMock()
        api_client.fetch_all.return_value = [mock_article]

        db = MagicMock()
        db.upsert.return_value = True  # 변경 있음

        indexer = MagicMock()

        result = run_setup_index(api_client=api_client, db=db, indexer=indexer)
        assert "PA_3" in result

    def test_changed_articles_passed_to_indexer(self, mock_article):
        """변경된 article_id만 indexer.upsert에 전달됨"""
        from scripts.setup_index import run_setup_index

        api_client = MagicMock()
        api_client.fetch_all.return_value = [mock_article]

        db = MagicMock()
        db.upsert.return_value = True

        indexer = MagicMock()

        run_setup_index(api_client=api_client, db=db, indexer=indexer)
        indexer.upsert.assert_called_once()
        call_kwargs = indexer.upsert.call_args
        changed_ids = call_kwargs[1].get("changed_ids") or call_kwargs[0][1]
        assert "PA_3" in changed_ids

    def test_no_change_skips_indexer(self, mock_article):
        """변경 없는 조항 → indexer.upsert에 빈 set 또는 미호출"""
        from scripts.setup_index import run_setup_index

        api_client = MagicMock()
        api_client.fetch_all.return_value = [mock_article]

        db = MagicMock()
        db.upsert.return_value = False  # 변경 없음

        indexer = MagicMock()

        result = run_setup_index(api_client=api_client, db=db, indexer=indexer)
        assert "PA_3" not in result
        # indexer.upsert가 호출되지 않았거나, 빈 changed_ids로 호출됨
        if indexer.upsert.called:
            call_kwargs = indexer.upsert.call_args
            changed_ids = call_kwargs[1].get("changed_ids") or call_kwargs[0][1]
            assert len(changed_ids) == 0

    def test_api_fetch_all_called(self, mock_article):
        """run_setup_index() 실행 시 api_client.fetch_all() 호출됨"""
        from scripts.setup_index import run_setup_index

        api_client = MagicMock()
        api_client.fetch_all.return_value = [mock_article]
        db = MagicMock()
        db.upsert.return_value = False
        indexer = MagicMock()

        run_setup_index(api_client=api_client, db=db, indexer=indexer)
        api_client.fetch_all.assert_called_once()
