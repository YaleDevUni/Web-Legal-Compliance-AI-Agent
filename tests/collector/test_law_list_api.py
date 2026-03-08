"""tests/collector/test_law_list_api.py — law.go.kr Law List API 클라이언트 TDD"""
import pytest
import responses as rsps_lib
from collector.law_list_api import LawListAPIClient

STUB_JSON = {
    "LawSearch": {
        "target": "eflaw",
        "totalCnt": "1",
        "page": "1",
        "law": [
            {
                "법령ID": "001234",
                "법령명한글": "주택법",
                "시행일자": "20240315"
            }
        ]
    }
}

STUB_JSON_MULTI = {
    "LawSearch": {
        "target": "eflaw",
        "totalCnt": "2",
        "page": "1",
        "law": [
            {"법령ID": "001234", "법령명한글": "주택법"},
            {"법령ID": "005678", "법령명한글": "공인중개사법"}
        ]
    }
}

@pytest.fixture
def client():
    return LawListAPIClient(api_key="test-law-key")

class TestLawListAPIClient:
    @rsps_lib.activate
    def test_search_laws_returns_json(self, client):
        """법령 검색 API 호출 시 JSON 반환 확인"""
        rsps_lib.add(
            rsps_lib.GET,
            "http://www.law.go.kr/DRF/lawSearch.do",
            json=STUB_JSON,
            status=200
        )
        data = client.search_laws(query="주택법")
        assert data["LawSearch"]["target"] == "eflaw"
        assert data["LawSearch"]["law"][0]["법령ID"] == "001234"

    @rsps_lib.activate
    def test_fetch_all_law_ids_single_page(self, client):
        """단일 페이지 결과에서 법령ID 리스트 추출"""
        rsps_lib.add(
            rsps_lib.GET,
            "http://www.law.go.kr/DRF/lawSearch.do",
            json=STUB_JSON_MULTI,
            status=200
        )
        ids = client.fetch_all_law_ids(query="부동산")
        assert len(ids) == 2
        assert "001234" in ids
        assert "005678" in ids

    @rsps_lib.activate
    def test_fetch_all_law_ids_pagination(self, client):
        """페이지네이션 처리 확인 (2개 페이지)"""
        # Page 1
        rsps_lib.add(
            rsps_lib.GET,
            "http://www.law.go.kr/DRF/lawSearch.do",
            json={
                "LawSearch": {
                    "totalCnt": "3",
                    "law": [
                        {"법령ID": "1"},
                        {"법령ID": "2"}
                    ]
                }
            },
            status=200
        )
        # Page 2
        rsps_lib.add(
            rsps_lib.GET,
            "http://www.law.go.kr/DRF/lawSearch.do",
            json={
                "LawSearch": {
                    "totalCnt": "3",
                    "law": [
                        {"법령ID": "3"}
                    ]
                }
            },
            status=200
        )
        
        # display=2로 설정하여 강제로 페이지네이션 유도 (client 코드에서 100이 기본이지만 search_laws 호출 시 override 가능하도록 수정 필요할지도)
        # 현재 fetch_all_law_ids 내부에 display=100 하드코딩 되어있음.
        # 테스트를 위해 fetch_all_law_ids 수정 제안: display 인자 추가
        
        # 수정 전: 100개씩 가져오므로 stub 1회 호출됨. 
        # stub에 limit=100으로 응답하면 됨.
        
        ids = client.fetch_all_law_ids(query="부동산", display=2)
        assert len(ids) == 3
        assert ids == ["1", "2", "3"]
