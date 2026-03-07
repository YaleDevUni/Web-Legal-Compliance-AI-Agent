"""tests/integrity/test_hasher.py — SHA-256 해시 함수 TDD

테스트 전략:
- hashlib.sha256(text.encode("utf-8")).hexdigest() 결과를 직접 검증
- 빈 문자열 해시는 표준 SHA-256 상수값(e3b0...)과 비교
- 소문자 hex 64자 반환 확인
"""
import pytest


class TestHasher:
    def test_same_text_same_hash(self):
        """동일 입력은 항상 동일 해시 반환 (결정론적)"""
        from integrity.hasher import compute_sha256
        assert compute_sha256("개인정보처리자") == compute_sha256("개인정보처리자")

    def test_different_text_different_hash(self):
        """다른 입력은 다른 해시 반환"""
        from integrity.hasher import compute_sha256
        assert compute_sha256("텍스트A") != compute_sha256("텍스트B")

    def test_empty_string(self):
        """빈 문자열 → SHA-256 표준 상수값 e3b0... (64자)"""
        from integrity.hasher import compute_sha256
        result = compute_sha256("")
        assert len(result) == 64
        assert result == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_returns_lowercase_hex(self):
        """반환값이 소문자 16진수 문자(0-9, a-f)만으로 구성됨"""
        from integrity.hasher import compute_sha256
        result = compute_sha256("test")
        assert result == result.lower()
        assert all(c in "0123456789abcdef" for c in result)

    def test_unicode_consistency(self):
        """한글 유니코드 텍스트도 결정론적으로 동일 해시 반환 (UTF-8 인코딩 기준)"""
        from integrity.hasher import compute_sha256
        text = "제17조(개인정보의 제공)"
        assert compute_sha256(text) == compute_sha256(text)
