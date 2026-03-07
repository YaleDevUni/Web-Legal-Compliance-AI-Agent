"""tests/core/test_config.py — Settings TDD"""
import pytest
from pydantic import ValidationError


class TestSettings:
    def test_loads_from_env(self, monkeypatch):
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
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("QDRANT_URL", "http://localhost:6333")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        monkeypatch.setenv("LAW_API_KEY", "law-key-123")

        from core.config import Settings
        with pytest.raises((ValidationError, Exception)):
            Settings()

    def test_default_values(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("LAW_API_KEY", "law-key")
        # QDRANT_URL, REDIS_URL 미설정 → 기본값 사용

        from core.config import Settings
        s = Settings()
        assert "6333" in str(s.qdrant_url)
        assert "6379" in s.redis_url

    def test_qdrant_collection_default(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("LAW_API_KEY", "law-key")

        from core.config import Settings
        s = Settings()
        assert s.qdrant_collection == "law_articles"

    def test_env_field_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-abc")
        monkeypatch.setenv("LAW_API_KEY", "lk-abc")

        from core.config import Settings
        s = Settings()
        assert s.openai_api_key == "sk-abc"
