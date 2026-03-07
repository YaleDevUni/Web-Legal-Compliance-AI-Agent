"""tests/core/test_config.py — Settings TDD

테스트 전략:
- monkeypatch.setenv/delenv으로 환경변수를 격리 제어
- 필수값(OPENAI_API_KEY) 누락 시 ValidationError 발생 확인
- 선택값(QDRANT_URL, REDIS_URL) 미설정 시 기본값(6333, 6379) 사용 확인
- pydantic-settings case_sensitive=False → 대소문자 무관 로드
"""
import pytest
from pydantic import ValidationError


class TestSettings:
    def test_loads_from_env(self, monkeypatch):
        """환경변수 4개 설정 → Settings 필드에 올바르게 매핑됨"""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setenv("QDRANT_URL", "http://localhost:6333")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        monkeypatch.setenv("LAW_API_KEY", "law-key-123")

        from core.config import Settings
        s = Settings()
        assert s.openai_api_key == "sk-test-key"
        assert str(s.qdrant_url) == "http://localhost:6333/"
        assert s.redis_url == "redis://localhost:6379"
        assert s.law_api_key == "law-key-123"

    def test_missing_openai_key_raises(self, monkeypatch):
        """OPENAI_API_KEY 누락 시 예외 발생"""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("QDRANT_URL", "http://localhost:6333")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        monkeypatch.setenv("LAW_API_KEY", "law-key-123")

        from core.config import Settings
        with pytest.raises((ValidationError, Exception)):
            Settings()

    def test_default_values(self, monkeypatch):
        """QDRANT_URL/REDIS_URL 미설정 시 기본 포트(6333, 6379) 사용"""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("LAW_API_KEY", "law-key")
        # QDRANT_URL, REDIS_URL 미설정 → 기본값 사용

        from core.config import Settings
        s = Settings()
        assert "6333" in str(s.qdrant_url)
        assert "6379" in s.redis_url

    def test_qdrant_collection_default(self, monkeypatch):
        """qdrant_collection 기본값이 "law_articles"임 확인"""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("LAW_API_KEY", "law-key")

        from core.config import Settings
        s = Settings()
        assert s.qdrant_collection == "law_articles"

    def test_env_field_case_insensitive(self, monkeypatch):
        """대문자 환경변수 키 → 소문자 필드명으로 정상 매핑 (case_sensitive=False)"""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-abc")
        monkeypatch.setenv("LAW_API_KEY", "lk-abc")

        from core.config import Settings
        s = Settings()
        assert s.openai_api_key == "sk-abc"
