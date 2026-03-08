"""tests/collector/test_law_content_api.py — law.go.kr Law Content API 클라이언트 TDD"""
import pytest
from collector.law_content_api import LawContentAPIClient

STUB_JO = {
    "조문번호": "2",
    "조문내용": "제2조(정의) 이 법에서 사용하는 용어의 뜻은 다음과 같다.",
    "조문여부": "조문",
    "항": [
        {
            "항번호": "①",
            "항내용": "① \"민간임대주택\"이란...",
            "호": [
                {
                    "호번호": "1.",
                    "호내용": "1. \"민간건설임대주택\"이란...",
                    "목": [
                        {
                            "목번호": "가.",
                            "목내용": "가. 임대사업자가..."
                        }
                    ]
                }
            ]
        }
    ]
}

@pytest.fixture
def client():
    return LawContentAPIClient(api_key="test-law-key")

class TestLawContentAPIClient:
    def test_reconstruct_content(self, client):
        """항, 호, 목을 포함하여 전체 텍스트가 올바르게 합쳐지는지 확인"""
        text = client._reconstruct_content(STUB_JO)
        assert "제2조(정의)" in text
        assert "① \"민간임대주택\"" in text
        assert "1. \"민간건설임대주택\"" in text
        assert "가. 임대사업자가" in text
        # 줄바꿈 확인
        assert text.count("\n") >= 3

    def test_parse_law_json(self, client):
        """JSON 응답을 LawArticle 리스트로 변환하는지 확인"""
        stub_data = {
            "법령": {
                "기본정보": {
                    "법령명_한글": "주택법",
                    "법령ID": "000123",
                    "시행일자": "20240315"
                },
                "조문": {
                    "조문단위": [STUB_JO]
                }
            }
        }
        articles = client.parse_law_json(stub_data)
        assert len(articles) == 1
        assert articles[0].article_id == "000123_2"
        assert articles[0].law_name == "주택법"
        assert "제2조" in articles[0].article_number
        assert "민간임대주택" in articles[0].content
