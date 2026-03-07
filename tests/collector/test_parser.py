"""tests/collector/test_parser.py — law.go.kr XML 파서 TDD

테스트 전략:
- SAMPLE_XML: 정상 2개 조항 포함 응답
- MISSING_FIELD_XML: 시행일자 누락 → 기본값으로 파싱 계속
- EMPTY_XML: 조문 없음 → 빈 리스트 반환
- sha256은 조문내용 텍스트로 직접 계산한 값과 일치해야 함
"""
import pytest


SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
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
        <조문제목>개인정보 보호 원칙</조문제목>
        <조문내용>개인정보처리자는 개인정보의 처리 목적을 명확하게 하여야 하고 그 목적에 필요한 범위에서 최소한의 개인정보만을 적법하고 정당하게 수집하여야 한다.</조문내용>
      </조문단위>
      <조문단위>
        <조문번호>17</조문번호>
        <조문제목>개인정보의 제공</조문제목>
        <조문내용>개인정보처리자는 다음 각 호의 어느 하나에 해당되는 경우에는 정보주체의 개인정보를 제3자에게 제공할 수 있다.</조문내용>
      </조문단위>
    </조문>
  </법령>
</LawService>"""

MISSING_FIELD_XML = """<?xml version="1.0" encoding="UTF-8"?>
<LawService>
  <법령>
    <기본정보>
      <법령명_한글>개인정보 보호법</법령명_한글>
      <법령ID>PA</법령ID>
    </기본정보>
    <조문>
      <조문단위>
        <조문번호>3</조문번호>
        <조문내용>내용</조문내용>
      </조문단위>
    </조문>
  </법령>
</LawService>"""

EMPTY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<LawService>
  <법령>
    <기본정보>
      <법령명_한글>개인정보 보호법</법령명_한글>
      <법령ID>PA</법령ID>
    </기본정보>
    <조문/>
  </법령>
</LawService>"""


class TestLawParser:
    def test_parse_returns_law_articles(self):
        """정상 XML → 조문 수(2개)만큼 LawArticle 반환"""
        from collector.parser import parse_law_xml
        articles = parse_law_xml(SAMPLE_XML)
        assert len(articles) == 2

    def test_article_fields_populated(self):
        """파싱된 조항의 law_name, article_number, content, sha256 필드 검증"""
        from collector.parser import parse_law_xml
        articles = parse_law_xml(SAMPLE_XML)
        a = articles[0]
        assert a.law_name == "개인정보 보호법"
        assert "3" in a.article_number
        assert len(a.content) > 0
        assert len(a.sha256) == 64
        assert a.article_id != ""

    def test_article_id_format(self):
        """article_id = {법령ID}_{조문번호} 형식 (예: PA_3, PA_17)"""
        from collector.parser import parse_law_xml
        articles = parse_law_xml(SAMPLE_XML)
        assert articles[0].article_id == "PA_3"
        assert articles[1].article_id == "PA_17"

    def test_missing_field_handled_gracefully(self):
        """시행일자 누락 시 updated_at 기본값 사용, 파싱 중단 없음"""
        from collector.parser import parse_law_xml
        articles = parse_law_xml(MISSING_FIELD_XML)
        assert len(articles) == 1

    def test_empty_articles_returns_empty_list(self):
        """조문이 없는 XML → 빈 리스트 반환"""
        from collector.parser import parse_law_xml
        articles = parse_law_xml(EMPTY_XML)
        assert articles == []

    def test_sha256_computed_from_content(self):
        """조항의 sha256은 content 텍스트로 직접 계산한 값과 동일해야 함"""
        from collector.parser import parse_law_xml
        from integrity.hasher import compute_sha256
        articles = parse_law_xml(SAMPLE_XML)
        assert articles[0].sha256 == compute_sha256(articles[0].content)
