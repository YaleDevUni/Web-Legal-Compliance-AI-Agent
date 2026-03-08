"""tests/collector/test_domain.py — 도메인 정의 확인"""
from collector.domain import REAL_ESTATE_LAWS, CASE_KEYWORDS

def test_domain_constants_exist():
    assert len(REAL_ESTATE_LAWS) > 0
    assert "주택법" in REAL_ESTATE_LAWS
    assert "공인중개사법" in REAL_ESTATE_LAWS

def test_case_keywords_exist():
    assert len(CASE_KEYWORDS) > 0
    assert "전세사기" in CASE_KEYWORDS
    assert "임대차" in CASE_KEYWORDS
