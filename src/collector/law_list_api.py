"""src/collector/law_list_api.py — law.go.kr Law List API 클라이언트"""
import requests
from typing import Any, Optional
from core.logger import logger

_SEARCH_URL = "http://www.law.go.kr/DRF/lawSearch.do"

class LawListAPIClient:
    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("api_key must not be empty")
        self._api_key = api_key
        self._session = requests.Session()

    def search_laws(
        self,
        query: str = "",
        target: str = "eflaw",
        page: int = 1,
        display: int = 20,
        **kwargs: Any
    ) -> dict[str, Any]:
        """법령 목록을 조회한다.
        
        Args:
            query: 검색어 (법령명 등)
            target: 서비스 대상 (eflaw: 현행법령, law: 법령 등)
            page: 결과 페이지 번호
            display: 페이지당 결과 수 (max 100)
            **kwargs: 추가 요청 변수 (nw, sort, org, knd 등)
            
        Returns:
            JSON 응답 본문
        """
        params = {
            "OC": self._api_key,
            "target": target,
            "type": "JSON",
            "query": query,
            "page": page,
            "display": display,
        }
        params.update(kwargs)
        
        logger.info(f"법령 목록 검색: target={target}, query={query}, page={page}")
        response = self._session.get(_SEARCH_URL, params=params, timeout=10)
        response.raise_for_status()
        
        # law.go.kr JSON API는 때때로 에러가 나도 200 OK를 줄 수 있으므로 응답 확인 필요
        return response.json()

    def fetch_all_law_ids(self, query: str, target: str = "eflaw", display: int = 100) -> list[str]:
        """검색 결과의 모든 법령ID 리스트를 가져온다 (페이지네이션 처리)."""
        law_ids = []
        page = 1
        
        while True:
            data = self.search_laws(query=query, target=target, page=page, display=display)
            
            # JSON 구조 확인 (보통 "LawSearch" 또는 "LawList" 하위에 데이터가 있음)
            # 제공된 필드 설명에 따르면 root에 target, totalCnt 등이 있을 수 있음.
            # 하지만 실제로는 LawSearch 등의 래퍼가 있는 경우가 많음.
            
            root = data.get("LawSearch") or data
            total_cnt_str = root.get("totalCnt", "0")
            try:
                total_cnt = int(total_cnt_str)
            except (ValueError, TypeError):
                total_cnt = 0
                
            laws = root.get("law")
            if not laws:
                break
                
            # 단일 결과인 경우 리스트가 아닐 수 있음
            if isinstance(laws, dict):
                laws = [laws]
                
            for law in laws:
                # "법령ID" 필드 추출
                lid = law.get("법령ID")
                if lid:
                    law_ids.append(str(lid))
            
            if len(law_ids) >= total_cnt or len(laws) < display:
                break
                
            page += 1
            
        return list(dict.fromkeys(law_ids)) # 중복 제거
