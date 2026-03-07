"""retrieval/rrf.py — Reciprocal Rank Fusion (RRF) 병합 모듈"""


def rrf_merge(
    bm25_results: list[dict],
    vector_results: list[dict],
    k: int = 60,
) -> list[dict]:
    """BM25와 벡터 검색 결과를 RRF로 병합.

    RRF score = Σ 1 / (k + rank_i) for each ranked list.
    반환: [{"id", "text", "score"}, ...] 점수 내림차순.
    """
    scores: dict[str, float] = {}
    texts: dict[str, str] = {}

    for ranked_list in (bm25_results, vector_results):
        for rank, item in enumerate(ranked_list, start=1):
            doc_id = item["id"]
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
            texts.setdefault(doc_id, item["text"])

    return sorted(
        [{"id": doc_id, "text": texts[doc_id], "score": score} for doc_id, score in scores.items()],
        key=lambda x: x["score"],
        reverse=True,
    )
