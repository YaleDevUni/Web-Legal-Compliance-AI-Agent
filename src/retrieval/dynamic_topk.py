"""retrieval/dynamic_topk.py — 검색 결과 스코어 기반 동적 top-k 선택"""


def compute_top_k(
    scores: list[float],
    min_k: int = 3,
    max_k: int = 10,
    threshold: float = 0.7,
) -> int:
    """스코어 분포에 따라 적절한 top-k를 동적으로 결정.

    threshold 이상인 스코어 수를 [min_k, max_k] 범위로 클램핑해 반환.
    """
    count = sum(1 for s in scores if s >= threshold)
    return max(min_k, min(count, max_k))
