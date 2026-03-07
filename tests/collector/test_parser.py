"""tests/collector/test_parser.py — law.go.kr XML/HTML 파서 TDD

테스트 전략:
- SAMPLE_XML: 정상 2개 조항 포함 응답 → parse_law_xml 검증
- MISSING_FIELD_XML: 시행일자 누락 → 기본값으로 파싱 계속
- EMPTY_XML: 조문 없음 → 빈 리스트 반환
- sha256은 조문내용 텍스트로 직접 계산한 값과 일치해야 함
- SAMPLE_HTML: 최소 조문 HTML → parse_law_html 검증
  - 법령명, 시행일, 조문번호, 조문내용, sha256 필드 확인
  - 의N 접미사 조문(제7조의2) → article_id에 의2 포함
  - 장 제목(gtit) 스킵 확인
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


# ── HTML 파서 테스트 ──────────────────────────────────────────────────────────

SAMPLE_HTML = """<!DOCTYPE html>
<html><head><title>테스트</title></head>
<body>
<div class="confnla1">
  <h2>개인정보 보호법</h2>
  <div class="subtit1">[시행 2024. 3. 15.] [법률 제12345호]</div>
  <a name="JP1:0" id="JP1:0"></a>
  <div class="pgroup" style="padding-bottom:0px;">
    <p class="gtit">제1장 총칙</p>
  </div>
  <a name="J1:0" id="J1:0"></a>
  <div class="pgroup">
    <p class="pty1"><span class="bl">제1조(목적)</span> 이 법은 개인정보 보호를 위한 것이다.<span class="sfon">&lt;개정 2020. 2. 4.&gt;</span></p>
  </div>
  <a name="J3:0" id="J3:0"></a>
  <div class="pgroup">
    <p class="pty1"><span class="bl">제3조(원칙)</span> 개인정보처리자는 최소 수집 원칙을 준수하여야 한다.</p>
    <p class="pty1_de2_1">② 목적 범위 내에서 처리하여야 한다.</p>
  </div>
  <a name="J7:2" id="J7:2"></a>
  <div class="pgroup">
    <p class="pty1"><span class="bl">제7조의2(보호위원회 구성)</span> 보호위원회는 9명의 위원으로 구성한다.</p>
  </div>
</div>
</body></html>"""


class TestLawHtmlParser:
    def test_parse_html_returns_articles(self):
        """최소 HTML → 3개 조문 LawArticle 반환 (장 제목 스킵)"""
        from collector.parser import parse_law_html
        articles = parse_law_html(SAMPLE_HTML, law_id_prefix="PA")
        assert len(articles) == 3

    def test_html_law_name_extracted(self):
        """h2 태그에서 법령명 추출"""
        from collector.parser import parse_law_html
        articles = parse_law_html(SAMPLE_HTML, law_id_prefix="PA")
        assert articles[0].law_name == "개인정보 보호법"

    def test_html_updated_at_extracted(self):
        """subtit1에서 시행일 2024-03-15 추출"""
        from collector.parser import parse_law_html
        articles = parse_law_html(SAMPLE_HTML, law_id_prefix="PA")
        assert articles[0].updated_at.year == 2024
        assert articles[0].updated_at.month == 3

    def test_html_article_id_format(self):
        """article_id: PA_1, PA_3, PA_7의2 형식"""
        from collector.parser import parse_law_html
        articles = parse_law_html(SAMPLE_HTML, law_id_prefix="PA")
        ids = [a.article_id for a in articles]
        assert "PA_1" in ids
        assert "PA_3" in ids
        assert "PA_7의2" in ids

    def test_html_sfon_removed_from_content(self):
        """개정 주석(sfon)이 content에서 제거됨"""
        from collector.parser import parse_law_html
        articles = parse_law_html(SAMPLE_HTML, law_id_prefix="PA")
        a1 = next(a for a in articles if a.article_id == "PA_1")
        assert "<개정" not in a1.content
        assert "sfon" not in a1.content

    def test_html_chapter_title_skipped(self):
        """gtit 클래스 장 제목 div는 조문으로 파싱되지 않음"""
        from collector.parser import parse_law_html
        articles = parse_law_html(SAMPLE_HTML, law_id_prefix="PA")
        contents = [a.content for a in articles]
        assert not any("총칙" in c and "제1장" in c for c in contents)

    def test_html_sha256_computed(self):
        """sha256은 content로 계산한 값과 동일"""
        from collector.parser import parse_law_html
        from integrity.hasher import compute_sha256
        articles = parse_law_html(SAMPLE_HTML, law_id_prefix="PA")
        assert articles[0].sha256 == compute_sha256(articles[0].content)
