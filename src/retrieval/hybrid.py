"""retrieval/hybrid.py — BM25 + Vector 하이브리드 검색 (다중 컬렉션 대응)"""
from typing import List, Dict, Any, Optional
from core.logger import logger
from retrieval.bm25 import BM25Retriever
from retrieval.rrf import rrf_merge
from retrieval.vector import VectorRetriever

class HybridRetriever:
    """laws, cases 컬렉션별로 BM25+Vector 하이브리드 검색을 수행한다."""

    def __init__(self, qdrant_client, collection: str, embeddings=None) -> None:
        self._collection = collection
        self._vector = VectorRetriever(qdrant_client, collection, embeddings)
        
        # 전체 코퍼스 로드 (BM25용)
        corpus, self._metadata_index = self._load_corpus(qdrant_client, collection)
        if corpus:
            self._bm25 = BM25Retriever(corpus)
        else:
            self._bm25 = None
            logger.warning(f"컬렉션 '{collection}'이 비어있어 BM25 검색기를 생성하지 못했습니다.")

    @staticmethod
    def _load_corpus(client, collection: str) -> tuple[list[dict], dict[str, dict]]:
        """Qdrant scroll로 전체 코퍼스 로드."""
        corpus = []
        metadata_index = {}
        offset = None

        if not client.collection_exists(collection):
            return [], {}

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

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """하이브리드 검색 수행"""
        fetch_k = top_k * 2

        # 1. BM25 검색
        bm25_results = []
        if self._bm25:
            try:
                bm25_results = self._bm25.search(query, top_k=fetch_k)
            except Exception as e:
                logger.error(f"BM25 검색 실패 ({self._collection}): {e}")

        # 2. 벡터 검색
        vector_results = []
        try:
            vector_results = self._vector.search(query, top_k=fetch_k)
        except Exception as e:
            logger.error(f"Vector 검색 실패 ({self._collection}): {e}")

        # 3. RRF 병합
        merged = rrf_merge(bm25_results, vector_results)[:top_k]
        
        # 4. 결과 재구성 (메타데이터 보강)
        final_results = []
        for r in merged:
            final_results.append({
                "id": r["id"],
                "text": r["text"],
                "score": r["score"],
                "metadata": self._metadata_index.get(r["id"], r.get("metadata", {})),
                "collection": self._collection
            })
            
        return final_results
