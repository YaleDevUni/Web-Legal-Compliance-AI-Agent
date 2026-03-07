"""tests/embedder/test_indexer.py — Qdrant 색인 TDD (mock)"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, call


@pytest.fixture
def article():
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


@pytest.fixture
def indexer(mock_qdrant, mocker):
    mocker.patch("embedder.indexer.OpenAIEmbeddings")
    from embedder.indexer import ArticleIndexer
    inst = ArticleIndexer(qdrant_client=mock_qdrant, collection="law_articles")
    return inst


class TestArticleIndexer:
    def test_collection_created_if_not_exists(self, indexer, mock_qdrant):
        mock_qdrant.collection_exists.return_value = False
        indexer._ensure_collection()
        mock_qdrant.create_collection.assert_called_once()

    def test_collection_not_recreated_if_exists(self, indexer, mock_qdrant):
        mock_qdrant.collection_exists.return_value = True
        indexer._ensure_collection()
        mock_qdrant.create_collection.assert_not_called()

    def test_upsert_calls_qdrant(self, indexer, mock_qdrant, article, mocker):
        mocker.patch.object(indexer, "_embed", return_value=[[0.1] * 1536])
        mock_qdrant.collection_exists.return_value = True
        indexer.upsert([article])
        mock_qdrant.upsert.assert_called_once()

    def test_skip_unchanged_article(self, indexer, mock_qdrant, article, mocker):
        """해시가 동일하면 upsert를 호출하지 않는다."""
        mocker.patch.object(indexer, "_embed", return_value=[[0.1] * 1536])
        mock_qdrant.collection_exists.return_value = True
        # 이미 색인된 동일 sha256 시뮬레이션
        indexer.upsert([article], changed_ids=set())  # 변경 없음
        mock_qdrant.upsert.assert_not_called()

    def test_reindex_changed_article(self, indexer, mock_qdrant, article, mocker):
        """changed_ids에 포함된 조항만 재임베딩한다."""
        mocker.patch.object(indexer, "_embed", return_value=[[0.1] * 1536])
        mock_qdrant.collection_exists.return_value = True
        indexer.upsert([article], changed_ids={"PA_3"})
        mock_qdrant.upsert.assert_called_once()
