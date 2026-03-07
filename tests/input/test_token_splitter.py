"""tests/input/test_token_splitter.py — tiktoken 기반 토큰 스플리터 TDD

테스트 전략:
- chunk_size = ctx_limit × 0.7 공식을 get_chunk_size()로 검증
- split_by_tokens(): 토큰 수 ≤ chunk_size 이면 단일 청크 반환
- CHUNK_OVERLAP 상수가 200임을 직접 확인
- 알 수 없는 모델명 → 기본 ctx_limit 사용 (size > 0 확인)
"""
import pytest


class TestTokenSplitter:
    def test_short_text_returns_single_chunk(self):
        """토큰 수 ≤ chunk_size → 원본 텍스트를 단일 청크로 반환"""
        from input.token_splitter import split_by_tokens
        text = "짧은 텍스트입니다."
        chunks = split_by_tokens(text, model="gpt-4o-mini")
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_text_returns_multiple_chunks(self):
        """gpt-4 기준(ctx=8192, chunk=5734) 초과 텍스트 → 복수 청크 반환"""
        from input.token_splitter import split_by_tokens
        # gpt-4 ctx=8192 × 0.7 = 5734 토큰 → 한글 2000반복(~6000토큰)으로 초과 유도 → 약 6000 토큰 텍스트로 분할 유도
        long_text = "가나다라마바사아자차카타파하 " * 2000
        chunks = split_by_tokens(long_text, model="gpt-4")
        assert len(chunks) > 1

    def test_chunk_size_is_70_percent_of_ctx_limit(self):
        """get_chunk_size("gpt-4o-mini") = int(128000 × 0.7) = 89600"""
        from input.token_splitter import get_chunk_size
        size = get_chunk_size("gpt-4o-mini")
        assert size == int(128000 * 0.7)

    def test_overlap_is_200_tokens(self):
        """CHUNK_OVERLAP 상수가 200 토큰임을 확인 (아키텍처 명세 기준)"""
        from input.token_splitter import CHUNK_OVERLAP
        assert CHUNK_OVERLAP == 200

    def test_unknown_model_uses_default(self):
        """알 수 없는 모델명 → 기본 ctx_limit(16385) 사용, chunk_size > 0 확인"""
        from input.token_splitter import get_chunk_size
        size = get_chunk_size("unknown-model")
        assert size > 0
