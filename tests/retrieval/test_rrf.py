"""tests/retrieval/test_rrf.py — Reciprocal Rank Fusion (RRF) TDD

테스트 전략:
- rrf_merge(bm25_results, vector_results, k=60) → 병합 정렬 결과 검증
- 두 리스트 모두에 나타나는 항목이 상위에 랭크됨 (RRF 보너스)
- 한쪽 리스트에만 있는 항목도 결과에 포함됨
- 중복 id → 하나의 항목으로 합산
- 빈 입력 → 빈 리스트 반환
- 결과 형식: [{"id", "text", "score"}, ...] 점수 내림차순
"""
import pytest


BM25_RESULTS = [
    {"id": "PA_17", "text": "제17조 제3자 제공", "score": 10.0},
    {"id": "PA_3",  "text": "처리 목적 명확화",  "score": 8.0},
    {"id": "PA_29", "text": "보안 조치",         "score": 5.0},
]

VECTOR_RESULTS = [
    {"id": "PA_17", "text": "제17조 제3자 제공", "score": 0.95},
    {"id": "PA_5",  "text": "정보주체 권리",     "score": 0.88},
    {"id": "PA_3",  "text": "처리 목적 명확화",  "score": 0.80},
]


class TestRRFMerge:
    def test_overlap_item_ranked_top(self):
        """두 리스트 공통 항목(PA_17)이 최상위에 위치"""
        from retrieval.rrf import rrf_merge
        results = rrf_merge(BM25_RESULTS, VECTOR_RESULTS, k=60)
        assert results[0]["id"] == "PA_17"

    def test_all_ids_present(self):
        """두 리스트의 모든 고유 id가 결과에 포함됨"""
        from retrieval.rrf import rrf_merge
        results = rrf_merge(BM25_RESULTS, VECTOR_RESULTS, k=60)
        ids = {r["id"] for r in results}
        assert ids == {"PA_17", "PA_3", "PA_29", "PA_5"}

    def test_no_duplicate_ids(self):
        """결과에 중복 id 없음"""
        from retrieval.rrf import rrf_merge
        results = rrf_merge(BM25_RESULTS, VECTOR_RESULTS, k=60)
        ids = [r["id"] for r in results]
        assert len(ids) == len(set(ids))

    def test_result_format(self):
        """각 항목에 id, text, score 키 포함"""
        from retrieval.rrf import rrf_merge
        results = rrf_merge(BM25_RESULTS, VECTOR_RESULTS, k=60)
        for r in results:
            assert "id" in r
            assert "text" in r
            assert "score" in r

    def test_scores_descending(self):
        """결과가 score 내림차순으로 정렬됨"""
        from retrieval.rrf import rrf_merge
        results = rrf_merge(BM25_RESULTS, VECTOR_RESULTS, k=60)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_empty_inputs_returns_empty(self):
        """두 리스트 모두 빈 경우 빈 리스트 반환"""
        from retrieval.rrf import rrf_merge
        assert rrf_merge([], [], k=60) == []

    def test_one_empty_list(self):
        """한쪽 리스트가 비어도 나머지 결과 반환"""
        from retrieval.rrf import rrf_merge
        results = rrf_merge(BM25_RESULTS, [], k=60)
        assert len(results) == len(BM25_RESULTS)
