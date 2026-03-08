"""tests/embedder/test_indexer.py — Qdrant 색인 TDD (mock)

테스트 전략:
- conftest.py의 mock_qdrant 픽스처로 실제 Qdrant 없이 테스트
- OpenAIEmbeddings도 mocker.patch로 대체 (실제 API 호출 없음)
- changed_ids=None → 전체 색인, changed_ids=set() → 스킵, changed_ids={"PA_3"} → 해당만 색인
"""
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
        """컬렉션 미존재 시 create_collection 호출"""
        mock_qdrant.collection_exists.return_value = False
        indexer.recreate_collection()
        mock_qdrant.create_collection.assert_called_once()

    def test_collection_deleted_and_recreated_if_exists(self, indexer, mock_qdrant):
        """컬렉션 존재 시 삭제 후 재생성"""
        mock_qdrant.collection_exists.return_value = True
        indexer.recreate_collection()
        mock_qdrant.delete_collection.assert_called_once()
        mock_qdrant.create_collection.assert_called_once()

    def test_upsert_calls_qdrant(self, indexer, mock_qdrant, article, mocker):
        """changed_ids 미지정(전체 색인) → qdrant.upsert 1회 호출"""
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
