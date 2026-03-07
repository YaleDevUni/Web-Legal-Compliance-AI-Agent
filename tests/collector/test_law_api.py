"""tests/collector/test_law_api.py — law.go.kr API 클라이언트 TDD (responses mock)

테스트 전략:
- responses 라이브러리로 실제 HTTP 없이 API 동작 검증
- STUB_XML: 1조항 응답으로 파싱 결과 확인
- fetch_all(): 7개 법령 순회 → 각 법령당 최소 1개 조항 반환
- 빈 api_key → ValueError, ConnectionError → 예외 전파 확인
"""
import pytest
import responses as rsps_lib
from responses import RequestsMock


STUB_XML = """<?xml version="1.0" encoding="UTF-8"?>
<LawService>
  <법령>
    <기본정보>
      <법령명_한글>개인정보 보호법</법령명_한글>
      <시행일자>20240315</시행일자>
      <법령ID>PA</법령ID>
    </기본정보>
    <조문>
      <조문단위>
        <조문번호>3</조문번호>
        <조문내용>개인정보처리자는 목적을 명확히 해야 한다.</조문내용>
      </조문단위>
    </조문>
  </법령>
</LawService>"""


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("LAW_API_KEY", "test-law-key")
    from collector.law_api import LawAPIClient
    return LawAPIClient(api_key="test-law-key")


class TestLawAPIClient:
    @rsps_lib.activate
    def test_fetch_returns_articles(self, api):
        """단일 법령 조회 → LawArticle 반환, law_name 필드 확인"""
        rsps_lib.add(
            rsps_lib.GET,
            "https://www.law.go.kr/DRF/lawService.do",
            body=STUB_XML,
            status=200,
            content_type="application/xml",
        )
        articles = api.fetch("개인정보 보호법")
        assert len(articles) >= 1
        assert articles[0].law_name == "개인정보 보호법"

    @rsps_lib.activate
    def test_missing_api_key_raises(self):
        """빈 api_key로 LawAPIClient 생성 시 ValueError 발생"""
        from collector.law_api import LawAPIClient
        with pytest.raises(ValueError, match="api_key"):
            LawAPIClient(api_key="")

    @rsps_lib.activate
    def test_network_error_raises(self, api):
        """ConnectionError 발생 시 예외 전파 (재시도 없음)"""
        import requests
        rsps_lib.add(
            rsps_lib.GET,
            "https://www.law.go.kr/DRF/lawService.do",
            body=requests.ConnectionError("연결 실패"),
        )
        with pytest.raises(Exception):
            api.fetch("개인정보 보호법")

    @rsps_lib.activate
    def test_fetch_all_returns_multiple_laws(self, api):
        """fetch_all()이 7개 법령을 모두 순회하여 조항 합산 반환"""
        # 7개 법령 각각 stub (responses 라이브러리가 순서대로 응답 소비)
        for _ in range(7):
            rsps_lib.add(
                rsps_lib.GET,
                "https://www.law.go.kr/DRF/lawService.do",
                body=STUB_XML,
                status=200,
                content_type="application/xml",
            )
        all_articles = api.fetch_all()
        assert len(all_articles) >= 7  # 법령당 최소 1개 조항
