"""src/collector/law_content_api.py — law.go.kr Law Content API 클라이언트 (JSON)"""
import requests
from typing import Any, Optional
from datetime import datetime
from core.logger import logger
from core.models import LawArticle
from integrity.hasher import compute_sha256

_SERVICE_URL = "https://www.law.go.kr/DRF/lawService.do"

class LawContentAPIClient:
    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("api_key must not be empty")
        self._api_key = api_key
        self._session = requests.Session()

    def fetch_law_content(self, law_id: Optional[str] = None, mst: Optional[str] = None) -> dict[str, Any]:
        """법령 상세 내용을 JSON으로 가져온다.
        
        Args:
            law_id: 법령ID (ID 파라미터)
            mst: 법령일련번호 (MST 파라미터)
            
        Returns:
            JSON 응답 본문
        """
        params = {
            "OC": self._api_key,
            "target": "law",
            "type": "JSON",
        }
        if mst:
            params["MST"] = mst
        elif law_id:
            params["ID"] = law_id
        else:
            raise ValueError("Either law_id or mst must be provided")
            
        logger.info(f"법령 본문 조회: MST={mst}, ID={law_id}")
        response = self._session.get(_SERVICE_URL, params=params, timeout=15)
        response.raise_for_status()
        
        return response.json()

    def parse_law_json(self, data: dict[str, Any]) -> list[LawArticle]:
        """JSON 응답을 LawArticle 리스트로 변환한다."""
        law_root = data.get("법령")
        if not law_root:
            logger.error("JSON 응답에 '법령' 키가 없습니다.")
            return []
            
        info = law_root.get("기본정보", {})
        law_name = info.get("법령명_한글", "알 수 없는 법령")
        law_id = info.get("법령ID", "UNKNOWN")
        updated_at_raw = info.get("시행일자", "")
        
        try:
            updated_at = datetime.strptime(updated_at_raw, "%Y%m%d") if updated_at_raw else datetime.now()
        except ValueError:
            updated_at = datetime.now()
            
        articles: list[LawArticle] = []
        jo_list = law_root.get("조문", {}).get("조문단위", [])
        if isinstance(jo_list, dict):
            jo_list = [jo_list]
            
        for jo in jo_list:
            if jo.get("조문여부") != "조문":
                continue
                
            jo_num = jo.get("조문번호", "")
            jo_title = jo.get("조문제목", "")
            jo_content = jo.get("조문내용", "").strip()
            
            # 조문 내용이 제목만 포함하는 경우가 많음. 
            # 실제 세부 내용은 항/호/목에 있음.
            # 전체 텍스트를 재구성할 필요가 있을 수 있음 (Phase 2-1 대비).
            
            full_text = self._reconstruct_content(jo)
            
            try:
                article = LawArticle(
                    article_id=f"{law_id}_{jo_num}",
                    law_name=law_name,
                    article_number=f"제{jo_num}조",
                    content=full_text,
                    sha256=compute_sha256(full_text),
                    url=f"https://www.law.go.kr/법령/{law_name}", # 혹은 상세링크 사용
                    updated_at=updated_at,
                )
                articles.append(article)
            except Exception as e:
                logger.error(f"LawArticle 생성 실패 ({law_id}_{jo_num}): {e}")
                
        return articles

    def _reconstruct_content(self, jo: dict[str, Any]) -> str:
        """항, 호, 목을 포함하여 전체 조문 내용을 재구성한다."""
        lines = []
        lines.append(jo.get("조문내용", "").strip())
        
        hang_list = jo.get("항", [])
        if isinstance(hang_list, dict):
            hang_list = [hang_list]
            
        for hang in hang_list:
            hang_content = hang.get("항내용", "").strip()
            if hang_content:
                lines.append(hang_content)
                
            ho_list = hang.get("호", [])
            if isinstance(ho_list, dict):
                ho_list = [ho_list]
            for ho in ho_list:
                ho_content = ho.get("호내용", "").strip()
                if ho_content:
                    lines.append(ho_content)
                    
                mok_list = ho.get("목", [])
                if isinstance(mok_list, dict):
                    mok_list = [mok_list]
                for mok in mok_list:
                    mok_content = mok.get("목내용", "").strip()
                    if mok_content:
                        lines.append(mok_content)
                        
        return "\n".join(lines)
