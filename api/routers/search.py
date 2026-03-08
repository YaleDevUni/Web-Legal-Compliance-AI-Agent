"""src/api/routers/search.py — 법령 및 판례 검색 엔드포인트"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from api.dependencies import get_law_retriever, get_case_retriever, get_qdrant_client
from qdrant_client.models import Filter, FieldCondition, MatchValue

router = APIRouter(prefix="/api", tags=["search"])

@router.get("/search")
async def search(
    q: str = Query(..., description="검색어"),
    type: str = Query("law", description="검색 대상: law | case | both"),
    top_k: int = 5,
    law_ret = Depends(get_law_retriever),
    case_ret = Depends(get_case_retriever)
):
    """법령 또는 판례를 직접 검색한다."""
    results = []
    
    if type in ["law", "both"] and law_ret:
        results.extend(law_ret.search(q, top_k=top_k))
        
    if type in ["case", "both"] and case_ret:
        results.extend(case_ret.search(q, top_k=top_k))
        
    # 점수 기준 정렬
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]

@router.get("/articles/{article_id}")
async def get_article_detail(
    article_id: str,
    client = Depends(get_qdrant_client)
):
    """특정 조문의 상세 내용을 조회한다 (Qdrant 기반)."""
    # laws 컬렉션에서 먼저 검색
    try:
        points = client.scroll(
            collection_name="laws",
            scroll_filter=Filter(
                must=[FieldCondition(key="article_id", match=MatchValue(value=article_id))]
            ),
            limit=1,
            with_payload=True
        )[0]
        
        if points:
            return points[0].payload
            
        # 없으면 cases 컬렉션에서 검색
        points = client.scroll(
            collection_name="cases",
            scroll_filter=Filter(
                must=[FieldCondition(key="case_id", match=MatchValue(value=article_id))]
            ),
            limit=1,
            with_payload=True
        )[0]
        
        if points:
            return points[0].payload
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    raise HTTPException(status_code=404, detail="해당 문서를 찾을 수 없습니다.")
