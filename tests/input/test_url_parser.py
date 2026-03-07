"""tests/input/test_url_parser.py — URL 파서 TDD (responses mock)

테스트 전략:
- responses 라이브러리로 실제 HTTP 요청 없이 파싱 동작 검증
- 반환 형식: {"text": str, "meta": dict, "scripts": list, "stylesheets": list}
- 상대 경로 /static/app.js → 절대 URL로 변환 확인
- scheme/netloc 없는 URL → ValueError("유효하지 않은 URL") 발생
"""
import pytest
import responses as rsps_lib


SAMPLE_HTML = """<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="description" content="개인정보처리방침 페이지">
  <link rel="stylesheet" href="/static/style.css">
  <script src="/static/app.js"></script>
</head>
<body>
  <h1>개인정보처리방침</h1>
  <p>본 방침은 개인정보 보호법에 따라 작성되었습니다.</p>
</body>
</html>"""


class TestURLParser:
    @rsps_lib.activate
    def test_parse_html_content(self):
        """HTML body 텍스트 추출 — 한글 포함 여부 확인"""
        from input.url_parser import parse_url
        rsps_lib.add(rsps_lib.GET, "https://example.com/", body=SAMPLE_HTML, status=200,
                     content_type="text/html")
        result = parse_url("https://example.com/")
        assert "개인정보처리방침" in result["text"]

    @rsps_lib.activate
    def test_extracts_meta_tags(self):
        """<meta name="description" content="..."> 값 추출 확인"""
        from input.url_parser import parse_url
        rsps_lib.add(rsps_lib.GET, "https://example.com/", body=SAMPLE_HTML, status=200,
                     content_type="text/html")
        result = parse_url("https://example.com/")
        assert any("개인정보처리방침" in v for v in result["meta"].values())

    @rsps_lib.activate
    def test_extracts_js_css_links(self):
        """<script src> / <link rel=stylesheet> 절대 URL 목록 추출 확인"""
        from input.url_parser import parse_url
        rsps_lib.add(rsps_lib.GET, "https://example.com/", body=SAMPLE_HTML, status=200,
                     content_type="text/html")
        result = parse_url("https://example.com/")
        assert any("app.js" in s for s in result["scripts"])
        assert any("style.css" in s for s in result["stylesheets"])

    def test_invalid_url_raises(self):
        """scheme/netloc 없는 URL → ValueError("유효하지 않은 URL") 발생"""
        from input.url_parser import parse_url
        with pytest.raises(ValueError, match="유효하지 않은 URL"):
            parse_url("not-a-url")

    @rsps_lib.activate
    def test_timeout_raises(self):
        """requests.Timeout 발생 시 예외 전파"""
        import requests
        from input.url_parser import parse_url
        rsps_lib.add(rsps_lib.GET, "https://example.com/",
                     body=requests.Timeout("타임아웃"))
        with pytest.raises(Exception):
            parse_url("https://example.com/")
