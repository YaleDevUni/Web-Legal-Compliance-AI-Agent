"""retrieval/bm25.py — BM25 희소 키워드 검색 모듈"""
from rank_bm25 import BM25Okapi


class BM25Retriever:
    """rank-bm25 기반 희소 검색기."""

    def __init__(self, corpus: list[dict]) -> None:
        """corpus: [{"id": str, "text": str}, ...]; 빈 목록이면 ValueError."""
        if not corpus:
            raise ValueError("코퍼스가 비어 있습니다. 최소 1개 이상의 항목이 필요합니다.")
        self._corpus = corpus
        tokenized = [doc["text"].split() for doc in corpus]
        self._bm25 = BM25Okapi(tokenized)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """쿼리와 코퍼스를 BM25로 비교해 상위 top_k 결과 반환.

        반환: [{"id": str, "text": str, "score": float}, ...]
        """
        tokens = query.split()
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(
            enumerate(scores), key=lambda x: x[1], reverse=True
        )[:top_k]
        return [
            {
                "id": self._corpus[i]["id"],
                "text": self._corpus[i]["text"],
                "score": float(s),
                "metadata": self._corpus[i].get("metadata", {}),
            }
            for i, s in ranked
        ]
