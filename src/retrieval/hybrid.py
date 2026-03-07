"""retrieval/hybrid.py — BM25 + Vector 하이브리드 검색 (RRF 병합)

흐름:
  1. 초기화 시 Qdrant scroll로 전체 코퍼스 로드 → BM25 인덱스 빌드
  2. search(query): BM25(top_k*2) + Vector(top_k*2) 병렬 검색
  3. RRF(k=60)로 점수 병합 → 상위 top_k 반환
  4. metadata는 corpus에서 id 기반으로 재부착
"""
from core.logger import logger
from retrieval.bm25 import BM25Retriever
from retrieval.rrf import rrf_merge
from retrieval.vector import VectorRetriever


class HybridRetriever:
    """BM25 + 벡터 검색을 RRF로 병합하는 하이브리드 검색기."""

    def __init__(self, qdrant_client, collection: str, embeddings=None) -> None:
        self._vector = VectorRetriever(qdrant_client, collection, embeddings)
        corpus, self._metadata_index = self._load_corpus(qdrant_client, collection)
        self._bm25 = BM25Retriever(corpus) if corpus else None

    @staticmethod
    def _load_corpus(client, collection: str) -> tuple[list[dict], dict[str, dict]]:
        """Qdrant scroll로 전체 코퍼스 로드.

        반환: (corpus, metadata_index)
          corpus: [{"id": str, "text": str}, ...]
          metadata_index: {article_id: payload_dict}
        """
        corpus: list[dict] = []
        metadata_index: dict[str, dict] = {}
        offset = None

        while True:
            points, next_offset = client.scroll(
                collection_name=collection,
                limit=1000,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                doc_id = str(point.id)
                text = point.payload.get("text", "")
                chunk_metadata = {k: v for k, v in point.payload.items() if k != "text"}
                corpus.append({"id": doc_id, "text": text, "metadata": chunk_metadata})
                metadata_index[doc_id] = chunk_metadata
            if next_offset is None:
                break
            offset = next_offset

        return corpus, metadata_index

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """BM25 + 벡터 검색 결과를 RRF로 병합해 반환.

        반환: [{"id", "text", "score", "metadata"}, ...]
        """
        fetch_k = top_k * 2

        bm25_results: list[dict] = []
        if self._bm25 is not None:
            bm25_results = self._bm25.search(query, top_k=fetch_k)
            logger.debug(f"HybridRetriever - BM25 결과 ({len(bm25_results)}개): " +
                         f"{[(r['metadata'].get('article_id', 'N/A'), r['score']) for r in bm25_results]}")


        vector_results = self._vector.search(query, top_k=fetch_k)
        logger.debug(f"HybridRetriever - Vector 결과 ({len(vector_results)}개): " +
                     f"{[(r['metadata'].get('article_id', 'N/A'), r['score']) for r in vector_results]}")


        merged = rrf_merge(bm25_results, vector_results)[:top_k]
        logger.debug(f"HybridRetriever - RRF 병합 결과 ({len(merged)}개): " +
                     f"{[(r['metadata'].get('article_id', 'N/A'), r['score']) for r in merged]}")


        final_results = [
            {
                "id": r["id"],
                "text": r["text"],
                "score": r["score"],
                "metadata": self._metadata_index.get(r["id"], {}),
            }
            for r in merged
        ]
        logger.debug(f"HybridRetriever - 최종 Top-{top_k} 결과 (article_id, score, text_start): " +
                     f"{[(r['metadata'].get('article_id', 'N/A'), r['score'], r['text'][:50] + '...') for r in final_results]}")
        return final_results
