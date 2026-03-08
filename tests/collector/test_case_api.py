"""tests/collector/test_case_api.py — law.go.kr Case API 클라이언트 TDD"""
import pytest
from collector.case_api import CaseAPIClient

STUB_CASE_CONTENT = {
    "PrecService": {
        "사건번호": "2024다12345",
        "사건명": "임대차보증금",
        "선고일자": "20240501",
        "법원명": "대법원",
        "판결유형": "판결",
        "판시사항": "임대차 계약의 효력",
        "판결요지": "보증금은 반환되어야 한다.",
        "참조조문": "민법 제623조, 주택임대차보호법 제3조",
        "판례내용": "판례 전문 텍스트..."
    }
}

@pytest.fixture
def client():
    return CaseAPIClient(api_key="test-law-key")

class TestCaseAPIClient:
    def test_parse_case_json(self, client):
        """JSON 응답을 CaseArticle 모델로 올바르게 변환하는지 확인"""
        article = client.parse_case_json(STUB_CASE_CONTENT, "123456")
        
        assert article is not None
        assert article.case_id == "123456"
        assert article.case_number == "2024다12345"
        assert article.court == "대법원"
        assert len(article.referenced_articles) == 2
        assert "민법 제623조" in article.referenced_articles
        assert article.sha256 is not None
        assert article.decision_date.year == 2024
