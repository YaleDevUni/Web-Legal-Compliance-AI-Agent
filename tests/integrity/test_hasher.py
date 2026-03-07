"""tests/integrity/test_hasher.py"""
import pytest


class TestHasher:
    def test_same_text_same_hash(self):
        from integrity.hasher import compute_sha256
        assert compute_sha256("개인정보처리자") == compute_sha256("개인정보처리자")

    def test_different_text_different_hash(self):
        from integrity.hasher import compute_sha256
        assert compute_sha256("텍스트A") != compute_sha256("텍스트B")

    def test_empty_string(self):
        from integrity.hasher import compute_sha256
        result = compute_sha256("")
        assert len(result) == 64
        assert result == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_returns_lowercase_hex(self):
        from integrity.hasher import compute_sha256
        result = compute_sha256("test")
        assert result == result.lower()
        assert all(c in "0123456789abcdef" for c in result)

    def test_unicode_consistency(self):
        from integrity.hasher import compute_sha256
        # 동일 유니코드 텍스트는 항상 동일 해시
        text = "제17조(개인정보의 제공)"
        assert compute_sha256(text) == compute_sha256(text)
