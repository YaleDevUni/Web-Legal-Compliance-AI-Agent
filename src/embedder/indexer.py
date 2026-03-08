"""src/embedder/indexer.py — Qdrant 벡터 색인 (laws, cases 컬렉션 분리)"""
import uuid
from typing import List, Set, Optional, Any, Union, Dict
from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from core.logger import logger
from core.models import LawArticle, CaseArticle
from embedder.chunker import chunk_article, chunk_case

_VECTOR_SIZE = 1536  # text-embedding-3-small


class ArticleIndexer:
    def __init__(self, qdrant_client: QdrantClient) -> None:
        self._client = qdrant_client
        self._embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    def recreate_collection(self, collection_name: str) -> None:
        """기존 컬렉션을 삭제하고 새로 생성하여 DB를 초기화한다."""
        if self._client.collection_exists(collection_name):
            logger.info(f"기존 컬렉션 '{collection_name}'을(를) 삭제합니다.")
            self._client.delete_collection(collection_name=collection_name)
        
        logger.info(f"새 컬렉션 '{collection_name}'을(를) 생성합니다.")
        self._client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE),
        )

    def _embed(self, texts: List[str]) -> List[List[float]]:
        return self._embeddings.embed_documents(texts)

    def upsert_laws(self, articles: List[LawArticle], changed_ids: Optional[Set[str]] = None) -> None:
        """법령 조문을 'laws' 컬렉션에 색인한다."""
        targets = (
            [a for a in articles if a.article_id in changed_ids]
            if changed_ids is not None
            else articles
        )
        if not targets:
            return

        all_chunks = []
        for article in targets:
            all_chunks.extend(chunk_article(article))
            
        self._batch_upsert("laws", all_chunks)

    def upsert_cases(self, cases: List[CaseArticle], changed_ids: Optional[Set[str]] = None) -> None:
        """판례를 'cases' 컬렉션에 색인한다."""
        # changed_ids는 prefix 'CASE_'가 붙어 있을 수 있음
        targets = []
        for c in cases:
            db_id = f"CASE_{c.case_id}"
            if changed_ids is None or db_id in changed_ids:
                targets.append(c)
                
        if not targets:
            return

        all_chunks = []
        for case in targets:
            all_chunks.extend(chunk_case(case))
            
        self._batch_upsert("cases", all_chunks)

    def _batch_upsert(self, collection_name: str, chunks: List[Dict[str, Any]]) -> None:
        """공통 배치 upsert 로직"""
        if not chunks:
            return
            
        texts = [c["text"] for c in chunks]
        vectors = self._embed(texts)

        points = [
            PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, c["text"])),
                vector=v,
                payload={**c["metadata"], "text": c["text"]},
            )
            for c, v in zip(chunks, vectors)
        ]
        
        _BATCH_SIZE = 100
        logger.info(f"[{collection_name}] 총 {len(points)}개 포인트를 색인합니다.")
        for i in range(0, len(points), _BATCH_SIZE):
            batch = points[i : i + _BATCH_SIZE]
            self._client.upsert(collection_name=collection_name, points=batch)
        logger.info(f"[{collection_name}] 색인 완료.")
