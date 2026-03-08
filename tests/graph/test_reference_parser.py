"""tests/graph/test_reference_parser.py — 참조 추출 TDD"""
from graph.reference_parser import ReferenceParser

def test_extract_intra_law_reference():
    """동일 법령 내 단순 참조 추출"""
    content = "이 법 제12조에 따른 처분은..."
    refs = ReferenceParser.extract_references(content, "주택법")
    assert ("주택법", "제12조") in refs

def test_extract_same_law_reference():
    """'동법 제N조' 형식 추출"""
    content = "동법 제15조의 규정에도 불구하고..."
    refs = ReferenceParser.extract_references(content, "주택법")
    assert ("주택법", "제15조") in refs

def test_extract_cross_law_reference():
    """타 법령 참조 추출 (「법령명」 제N조)"""
    content = "「민법」 제623조에 따른 임대인의 의무..."
    refs = ReferenceParser.extract_references(content, "주택법")
    assert ("민법", "제623조") in refs
    # 내부 참조(주택법 제623조)로 중복 추출되지 않아야 함
    assert ("주택법", "제623조") not in refs

def test_extract_article_ui_suffix():
    """'제N조의M' 형식 추출"""
    content = "제5조의2에 따른 등록..."
    refs = ReferenceParser.extract_references(content, "주택법")
    assert ("주택법", "제5조의2") in refs

def test_multiple_references():
    """복수 참조 추출"""
    content = "제10조 및 「건축법」 제11조에 따라..."
    refs = ReferenceParser.extract_references(content, "주택법")
    assert len(refs) == 2
    assert ("주택법", "제10조") in refs
    assert ("건축법", "제11조") in refs
