"""tests/integrity/test_db.py — SQLite in-memory TDD

테스트 전략:
- ArticleDB(":memory:") 로 실제 파일 없이 격리된 테스트 환경 구성
- upsert() 반환값(True=변경, False=동일)으로 증분 색인 로직 검증
- article_history 테이블에 변경 이력만 기록되는지 확인
"""
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
        """ArticleDB 초기화 시 테이블 자동 생성 확인 (INSERT 성공으로 검증)"""
        db.upsert("ART-001", "aaa" + "a" * 61, datetime(2024, 1, 1))

    def test_insert_new_article_returns_true(self, db):
        """신규 article_id INSERT 시 True 반환 (변경 있음으로 간주)"""
        sha = "a" * 64
        changed = db.upsert("ART-001", sha, datetime(2024, 1, 1))
        assert changed is True

    def test_same_hash_returns_false(self, db):
        """동일 sha256 재요청 시 False 반환 → 재임베딩 스킵 트리거 없음"""
        sha = "a" * 64
        db.upsert("ART-001", sha, datetime(2024, 1, 1))
        changed = db.upsert("ART-001", sha, datetime(2024, 1, 2))
        assert changed is False

    def test_changed_hash_returns_true(self, db):
        """sha256 변경 시 True 반환 → 재임베딩 트리거"""
        db.upsert("ART-001", "a" * 64, datetime(2024, 1, 1))
        changed = db.upsert("ART-001", "b" * 64, datetime(2024, 1, 2))
        assert changed is True

    def test_get_current_hash(self, db):
        """저장된 조항의 현재 sha256 정확히 반환"""
        sha = "c" * 64
        db.upsert("ART-001", sha, datetime(2024, 1, 1))
        assert db.get_hash("ART-001") == sha

    def test_get_hash_nonexistent_returns_none(self, db):
        """존재하지 않는 article_id → None 반환"""
        assert db.get_hash("NOT-EXIST") is None

    def test_history_recorded_on_change(self, db):
        """해시 변경 시 article_history에 이전/현재 해시 모두 기록됨"""
        db.upsert("ART-001", "a" * 64, datetime(2024, 1, 1))
        db.upsert("ART-001", "b" * 64, datetime(2024, 2, 1))
        history = db.get_history("ART-001")
        assert len(history) == 2
        assert history[0]["sha256"] == "a" * 64
        assert history[1]["sha256"] == "b" * 64

    def test_history_not_duplicated_on_no_change(self, db):
        """동일 해시 재요청 시 history에 중복 기록 없음 (len == 1)"""
        sha = "a" * 64
        db.upsert("ART-001", sha, datetime(2024, 1, 1))
        db.upsert("ART-001", sha, datetime(2024, 1, 2))  # 동일 해시
        history = db.get_history("ART-001")
        assert len(history) == 1
