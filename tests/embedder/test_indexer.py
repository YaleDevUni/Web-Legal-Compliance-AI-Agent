"""tests/embedder/test_indexer.py — Qdrant 색인 TDD (mock)"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock
from embedder.indexer import ArticleIndexer

@pytest.fixture
def indexer(mock_qdrant, mocker):
    mocker.patch("embedder.indexer.OpenAIEmbeddings")
    return ArticleIndexer(qdrant_client=mock_qdrant)

@pytest.fixture
def law_article():
    from core.models import LawArticle
    return LawArticle(
        article_id="L123_1",
        law_name="주택법",
        article_number="제1조",
        content="목적",
        sha256="a"*64,
        url="http://test.com",
        updated_at=datetime.now(),
    )

@pytest.fixture
def case_article():
    from core.models import CaseArticle
    return CaseArticle(
        case_id="C456",
        case_number="2024다456",
        case_name="사건",
        court="법원",
        decision_date=datetime.now(),
        decision_type="판결",
        ruling_summary="판시",
        ruling_text="요지",
        url="http://test.com",
        sha256="b"*64
    )

class TestArticleIndexer:
    def test_recreate_collection(self, indexer, mock_qdrant):
        """컬렉션 재생성 호출 확인"""
        mock_qdrant.collection_exists.return_value = True
        indexer.recreate_collection("laws")
        mock_qdrant.delete_collection.assert_called_with(collection_name="laws")
        mock_qdrant.create_collection.assert_called_once()

    def test_upsert_laws_calls_qdrant(self, indexer, mock_qdrant, law_article, mocker):
        """법령 색인 시 qdrant.upsert 호출 확인"""
        mocker.patch.object(indexer, "_embed", return_value=[[0.1]*1536])
        indexer.upsert_laws([law_article])
        mock_qdrant.upsert.assert_called_with(collection_name="laws", points=mocker.ANY)

    def test_upsert_cases_calls_qdrant(self, indexer, mock_qdrant, case_article, mocker):
        """판례 색인 시 qdrant.upsert 호출 확인"""
        mocker.patch.object(indexer, "_embed", return_value=[[0.1]*1536])
        indexer.upsert_cases([case_article])
        mock_qdrant.upsert.assert_called_with(collection_name="cases", points=mocker.ANY)

    def test_upsert_skip_unchanged(self, indexer, mock_qdrant, law_article, mocker):
        """변경되지 않은 ID는 스킵"""
        indexer.upsert_laws([law_article], changed_ids=set())
        mock_qdrant.upsert.assert_not_called()

    def test_upsert_cases_with_prefix_id(self, indexer, mock_qdrant, case_article, mocker):
        """CASE_ 접두사가 붙은 ID로 변경 감지 확인"""
        mocker.patch.object(indexer, "_embed", return_value=[[0.1]*1536])
        indexer.upsert_cases([case_article], changed_ids={"CASE_C456"})
        mock_qdrant.upsert.assert_called_once()
