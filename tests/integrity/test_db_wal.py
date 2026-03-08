"""tests/integrity/test_db_wal.py — WAL 모드 활성화 TDD

테스트 전략:
- ArticleDB 초기화 후 journal_mode가 WAL인지 확인
- 임시 파일 DB 사용 (WAL은 :memory: 에선 적용 안 됨)
"""
import pytest
import tempfile
import os


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


class TestWALMode:
    def test_wal_mode_is_enabled(self, db_path):
        """ArticleDB 초기화 후 journal_mode = WAL 이어야 한다."""
        from integrity.db import ArticleDB

        db = ArticleDB(db_path)
        row = db._conn.execute("PRAGMA journal_mode").fetchone()
        db.close()

        assert row[0].upper() == "WAL"
