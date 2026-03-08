"""src/collector/case_api.py — law.go.kr 판례 API 클라이언트 (JSON)"""
import requests
from typing import Any, Optional
from datetime import datetime
from core.logger import logger
from core.models import CaseArticle
from integrity.hasher import compute_sha256

_SEARCH_URL = "http://www.law.go.kr/DRF/lawSearch.do"
_SERVICE_URL = "https://www.law.go.kr/DRF/lawService.do"

class CaseAPIClient:
    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("api_key must not be empty")
        self._api_key = api_key
        self._session = requests.Session()

    def search_cases(self, query: str, page: int = 1, display: int = 20) -> dict[str, Any]:
        """판례 목록을 검색한다."""
        params = {
            "OC": self._api_key,
            "target": "prec",
            "type": "JSON",
            "query": query,
            "page": page,
            "display": display,
        }
        logger.info(f"판례 목록 검색: query={query}, page={page}")
        response = self._session.get(_SEARCH_URL, params=params, timeout=10)
        response.raise_for_status()
        return response.json()

    def fetch_case_content(self, case_id: str) -> dict[str, Any]:
        """판례 상세 내용을 가져온다."""
        params = {
            "OC": self._api_key,
            "target": "prec",
            "type": "JSON",
            "ID": case_id,
        }
        logger.info(f"판례 본문 조회: ID={case_id}")
        response = self._session.get(_SERVICE_URL, params=params, timeout=15)
        response.raise_for_status()
        return response.json()

    def fetch_all_by_keyword(self, query: str, max_count: int = 100) -> list[CaseArticle]:
        """키워드로 판례를 검색하고 상세 내용을 모두 가져와 CaseArticle 리스트로 반환한다."""
        articles = []
        data = self.search_cases(query=query, display=max_count)
        
        root = data.get("PrecSearch")
        if not root:
            return []
            
        prec_list = root.get("prec")
        if not prec_list:
            return []
            
        if isinstance(prec_list, dict):
            prec_list = [prec_list]
            
        for p in prec_list:
            case_id = p.get("판례일련번호")
            if not case_id:
                continue
                
            try:
                content_data = self.fetch_case_content(case_id)
                article = self.parse_case_json(content_data, case_id)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.error(f"판례 수집 실패 (ID={case_id}): {e}")
                
        return articles

    def parse_case_json(self, data: dict[str, Any], case_id: str) -> Optional[CaseArticle]:
        """JSON 응답을 CaseArticle 모델로 변환한다."""
        # 상세 API는 'PrecService' 키 아래에 데이터를 반환함
        prec = data.get("PrecService")
        if not prec:
            logger.error(f"JSON 응답에 'PrecService' 키가 없습니다. ID={case_id}")
            return None
            
        case_number = prec.get("사건번호", "알 수 없음")
        case_name = prec.get("사건명", "알 수 없음")
        court = prec.get("법원명", "알 수 없음")
        date_raw = prec.get("선고일자", "")
        
        try:
            decision_date = datetime.strptime(date_raw, "%Y%m%d") if date_raw else datetime.now()
        except ValueError:
            decision_date = datetime.now()
            
        ruling_summary = prec.get("판시사항", "")
        ruling_text = prec.get("판결요지", "")
        full_content = prec.get("판례내용", "")
        ref_articles_raw = prec.get("참조조문", "")
        
        # 참조조문 파싱 (간단히 리스트화, 나중에 정교화 가능)
        ref_articles = [a.strip() for a in ref_articles_raw.split(",") if a.strip()]
        
        try:
            return CaseArticle(
                case_id=case_id,
                case_number=case_number,
                case_name=case_name,
                court=court,
                decision_date=decision_date,
                decision_type=prec.get("판결유형", "판결"),
                ruling_summary=ruling_summary,
                ruling_text=ruling_text,
                referenced_articles=ref_articles,
                url=f"https://www.law.go.kr/판례/{case_id}",
                sha256=compute_sha256(full_content or ruling_text),
            )
        except Exception as e:
            logger.error(f"CaseArticle 생성 실패 (ID={case_id}): {e}")
            return None
