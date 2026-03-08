"""src/retrieval/graph_expander.py — 그래프 연관 조문 확장기"""
from typing import List, Dict, Any, Set
from core.logger import logger
from graph.law_graph import LawGraph

class GraphExpander:
    """검색 결과(article_id)를 바탕으로 그래프에서 연관 조문을 찾아 확장한다."""

    def __init__(self, law_graph: LawGraph, qdrant_client) -> None:
        self._graph = law_graph
        self._client = qdrant_client

    def expand(self, initial_results: List[Dict[str, Any]], depth: int = 1) -> List[Dict[str, Any]]:
        """검색 결과 내 법령 조문들로부터 연관 조문을 찾아 추가한다."""
        expanded_ids = set()
        
        # 1. 초기 결과에서 법령 article_id 추출
        for res in initial_results:
            meta = res.get("metadata", {})
            if meta.get("doc_type") == "law":
                art_id = meta.get("article_id")
                if art_id:
                    # 그래프에서 연관 조문 조회
                    related = self._graph.get_related(art_id, depth=depth)
                    for rid in related:
                        expanded_ids.add(rid)
                        
        # 2. 이미 초기 결과에 포함된 ID는 제외
        initial_ids = {res.get("metadata", {}).get("article_id") for res in initial_results}
        target_ids = expanded_ids - initial_ids
        
        if not target_ids:
            return []
            
        logger.info(f"그래프 확장: {len(target_ids)}개의 연관 조문을 추가로 불러옵니다.")
        
        # 3. Qdrant에서 해당 ID들의 본문 조회
        # (주의: article_id 필터링을 위해 payload 필터 사용)
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        expanded_docs = []
        for rid in target_ids:
            # article_id 당 1개의 청크만 가져와도 조문 전체(full_content)를 메타데이터로 가지고 있음
            points = self._client.scroll(
                collection_name="laws",
                scroll_filter=Filter(
                    must=[FieldCondition(key="article_id", match=MatchValue(value=rid))]
                ),
                limit=1,
                with_payload=True
            )[0]
            
            if points:
                p = points[0]
                expanded_docs.append({
                    "id": str(p.id),
                    "text": p.payload.get("text"),
                    "score": 0.0, # 확장에 의한 결과이므로 점수 0
                    "metadata": p.payload,
                    "collection": "laws",
                    "is_expanded": True
                })
                
        return expanded_docs
