"""src/collector/law_content_api.py — law.go.kr Law Content API 클라이언트 (JSON)"""
import requests
from typing import Any, Optional, Union
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
        """법령 상세 내용을 JSON으로 가져온다."""
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
        elif not isinstance(jo_list, list):
            jo_list = []
            
        for jo in jo_list:
            if jo.get("조문여부") != "조문":
                continue
                
            jo_num = jo.get("조문번호", "")
            full_text = self._reconstruct_content(jo)
            
            try:
                article = LawArticle(
                    article_id=f"{law_id}_{jo_num}",
                    law_name=law_name,
                    article_number=f"제{jo_num}조",
                    content=full_text,
                    sha256=compute_sha256(full_text),
                    url=f"https://www.law.go.kr/법령/{law_name}",
                    updated_at=updated_at,
                )
                articles.append(article)
            except Exception as e:
                logger.error(f"LawArticle 생성 실패 ({law_id}_{jo_num}): {e}")
                
        return articles

    def _safe_strip(self, val: Union[str, list, Any]) -> str:
        """값이 리스트인 경우를 대비해 안전하게 strip 처리한다."""
        if val is None:
            return ""
        if isinstance(val, list):
            # 리스트면 모든 요소를 합친다
            return " ".join([str(v) for v in val]).strip()
        return str(val).strip()

    def _reconstruct_content(self, jo: dict[str, Any]) -> str:
        """항, 호, 목을 포함하여 전체 조문 내용을 재구성한다."""
        lines = []
        lines.append(self._safe_strip(jo.get("조문내용", "")))
        
        hang_list = jo.get("항", [])
        if isinstance(hang_list, dict):
            hang_list = [hang_list]
        elif not isinstance(hang_list, list):
            hang_list = []
            
        for hang in hang_list:
            if not isinstance(hang, dict): continue
            hang_content = self._safe_strip(hang.get("항내용", ""))
            if hang_content:
                lines.append(hang_content)
                
            ho_list = hang.get("호", [])
            if isinstance(ho_list, dict):
                ho_list = [ho_list]
            elif not isinstance(ho_list, list):
                ho_list = []

            for ho in ho_list:
                if not isinstance(ho, dict): continue
                ho_content = self._safe_strip(ho.get("호내용", ""))
                if ho_content:
                    lines.append(ho_content)
                    
                mok_list = ho.get("목", [])
                if isinstance(mok_list, dict):
                    mok_list = [mok_list]
                elif not isinstance(mok_list, list):
                    mok_list = []

                for mok in mok_list:
                    if not isinstance(mok, dict): continue
                    mok_content = self._safe_strip(mok.get("목내용", ""))
                    if mok_content:
                        lines.append(mok_content)
                        
        return "\n".join([line for line in lines if line])
