"""tests/retrieval/test_dynamic_topk.py — 동적 top-k 선택 TDD

테스트 전략:
- compute_top_k(scores, min_k, max_k, threshold) → int 반환
- threshold 이상 스코어 수가 [min_k, max_k] 범위에 클램핑됨
- 빈 scores → min_k 반환
- 모든 스코어가 threshold 미만 → min_k 반환
- threshold 이상 스코어 수 > max_k → max_k 반환
"""
import pytest


class TestComputeTopK:
    def test_returns_int(self):
        """반환 타입이 int"""
        from retrieval.dynamic_topk import compute_top_k
        result = compute_top_k([0.9, 0.8, 0.5], min_k=1, max_k=10, threshold=0.7)
        assert isinstance(result, int)

    def test_empty_scores_returns_min_k(self):
        """빈 스코어 리스트 → min_k 반환"""
        from retrieval.dynamic_topk import compute_top_k
        assert compute_top_k([], min_k=3, max_k=10, threshold=0.7) == 3

    def test_all_below_threshold_returns_min_k(self):
        """모든 스코어 threshold 미만 → min_k 반환"""
        from retrieval.dynamic_topk import compute_top_k
        assert compute_top_k([0.3, 0.4, 0.5], min_k=2, max_k=10, threshold=0.7) == 2

    def test_above_threshold_count_clamped_to_max(self):
        """threshold 이상 개수 > max_k → max_k 반환"""
        from retrieval.dynamic_topk import compute_top_k
        scores = [0.9] * 20
        assert compute_top_k(scores, min_k=1, max_k=5, threshold=0.7) == 5

    def test_count_within_range(self):
        """threshold 이상 개수가 [min_k, max_k] 내 → 해당 개수 반환"""
        from retrieval.dynamic_topk import compute_top_k
        scores = [0.9, 0.85, 0.8, 0.4, 0.3]
        result = compute_top_k(scores, min_k=1, max_k=10, threshold=0.7)
        assert result == 3

    def test_min_k_floor(self):
        """threshold 이상 개수가 min_k보다 작아도 min_k 보장"""
        from retrieval.dynamic_topk import compute_top_k
        scores = [0.95]
        assert compute_top_k(scores, min_k=3, max_k=10, threshold=0.7) == 3
