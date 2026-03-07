"""src/collector/law_api.py — law.go.kr Open API 클라이언트"""
import requests

from collector.parser import parse_law_xml
from core.logger import logger
from core.models import LawArticle

_BASE_URL = "https://www.law.go.kr/DRF/lawService.do"

_LAW_NAMES = [
    "개인정보 보호법",
    "정보통신망 이용촉진 및 정보보호 등에 관한 법률",
    "위치정보의 보호 및 이용 등에 관한 법률",
    "개인정보의 안전성 확보조치 기준",
    "전자상거래 등에서의 소비자보호에 관한 법률",
    "청소년 보호법",
    "신용정보의 이용 및 보호에 관한 법률",
]


class LawAPIClient:
    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("api_key must not be empty")
        self._api_key = api_key
        self._session = requests.Session()

    def fetch(self, law_name: str) -> list[LawArticle]:
        """단일 법령을 조회하여 LawArticle 리스트로 반환한다."""
        params = {
            "OC": self._api_key,
            "target": "law",
            "type": "XML",
            "query": law_name,
        }
        logger.info(f"법령 조회: {law_name}")
        response = self._session.get(_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        return parse_law_xml(response.text)

    def fetch_all(self) -> list[LawArticle]:
        """7개 대상 법령을 모두 조회하여 합산 반환한다."""
        all_articles: list[LawArticle] = []
        for law_name in _LAW_NAMES:
            try:
                articles = self.fetch(law_name)
                all_articles.extend(articles)
            except Exception as e:
                logger.error(f"법령 수집 실패 ({law_name}): {e}")
        return all_articles
