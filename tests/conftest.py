"""공통 테스트 픽스처"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime


# ── LLM Mock ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_llm():
    """ChatOpenAI mock - invoke/ainvoke 지원"""
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content="mock response")
    llm.ainvoke = AsyncMock(return_value=MagicMock(content="mock response"))
    return llm


# ── Qdrant Mock ────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_qdrant():
    """QdrantClient mock"""
    client = MagicMock()
    client.collection_exists.return_value = False
    client.create_collection.return_value = True
    client.upsert.return_value = MagicMock(status="completed")
    client.search.return_value = []
    return client


# ── Redis Mock ─────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_redis():
    """Redis client mock"""
    client = MagicMock()
    client.get.return_value = None
    client.set.return_value = True
    client.xadd.return_value = b"1-0"
    client.xread.return_value = []
    return client


# ── 샘플 LawArticle 데이터 ────────────────────────────────────────────────────

@pytest.fixture
def sample_law_article_data():
    return {
        "article_id": "PA_001_0030",
        "law_name": "개인정보 보호법",
        "article_number": "제3조",
        "content": "개인정보처리자는 개인정보의 처리 목적을 명확하게 하여야 하고...",
        "sha256": "a3f2c1d4e5b6789012345678901234567890abcd",
        "url": "https://www.law.go.kr/법령/개인정보보호법",
        "updated_at": datetime(2024, 3, 15),
    }
