"""tests/integrity/test_db.py — SQLite in-memory TDD"""
import pytest
from datetime import datetime


@pytest.fixture
def db():
    from integrity.db import ArticleDB
    instance = ArticleDB(":memory:")
    yield instance
    instance.close()


class TestArticleDB:
    def test_table_created_on_init(self, db):
        from integrity.db import ArticleDB
        # 테이블이 존재하면 INSERT가 가능함 (예외 없음)
        db.upsert("ART-001", "aaa" + "a" * 61, datetime(2024, 1, 1))

    def test_insert_new_article_returns_true(self, db):
        sha = "a" * 64
        changed = db.upsert("ART-001", sha, datetime(2024, 1, 1))
        assert changed is True  # 신규 → 변경됨

    def test_same_hash_returns_false(self, db):
        sha = "a" * 64
        db.upsert("ART-001", sha, datetime(2024, 1, 1))
        changed = db.upsert("ART-001", sha, datetime(2024, 1, 2))
        assert changed is False  # 동일 해시 → 스킵

    def test_changed_hash_returns_true(self, db):
        db.upsert("ART-001", "a" * 64, datetime(2024, 1, 1))
        changed = db.upsert("ART-001", "b" * 64, datetime(2024, 1, 2))
        assert changed is True  # 해시 변경 → 재임베딩 필요

    def test_get_current_hash(self, db):
        sha = "c" * 64
        db.upsert("ART-001", sha, datetime(2024, 1, 1))
        assert db.get_hash("ART-001") == sha

    def test_get_hash_nonexistent_returns_none(self, db):
        assert db.get_hash("NOT-EXIST") is None

    def test_history_recorded_on_change(self, db):
        db.upsert("ART-001", "a" * 64, datetime(2024, 1, 1))
        db.upsert("ART-001", "b" * 64, datetime(2024, 2, 1))
        history = db.get_history("ART-001")
        assert len(history) == 2
        assert history[0]["sha256"] == "a" * 64
        assert history[1]["sha256"] == "b" * 64

    def test_history_not_duplicated_on_no_change(self, db):
        sha = "a" * 64
        db.upsert("ART-001", sha, datetime(2024, 1, 1))
        db.upsert("ART-001", sha, datetime(2024, 1, 2))  # 동일 해시
        history = db.get_history("ART-001")
        assert len(history) == 1
