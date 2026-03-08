"""tests/retrieval/test_graph_expander.py — 그래프 확장 TDD (mock)"""
import pytest
from unittest.mock import MagicMock
from retrieval.graph_expander import GraphExpander

@pytest.fixture
def mock_graph():
    g = MagicMock()
    # A -> B 관계
    g.get_related.side_effect = lambda art_id, depth: ["B"] if art_id == "A" else []
    return g

@pytest.fixture
def mock_qdrant():
    q = MagicMock()
    # B 조문 페이로드
    point = MagicMock()
    point.id = "doc_b"
    point.payload = {"article_id": "B", "text": "조문 B 본문", "doc_type": "law"}
    q.scroll.return_value = ([point], None)
    return q

class TestGraphExpander:
    def test_expand_finds_related(self, mock_graph, mock_qdrant):
        """A 조문 결과가 있을 때 그래프에서 B를 찾아 확장하는지 확인"""
        expander = GraphExpander(mock_graph, mock_qdrant)
        
        initial = [
            {"metadata": {"article_id": "A", "doc_type": "law"}}
        ]
        
        expanded = expander.expand(initial, depth=1)
        
        assert len(expanded) == 1
        assert expanded[0]["metadata"]["article_id"] == "B"
        assert expanded[0]["is_expanded"] is True
        
    def test_expand_skips_if_already_in_initial(self, mock_graph, mock_qdrant):
        """이미 초기 결과에 포함된 연관 조문은 중복 추가하지 않음"""
        expander = GraphExpander(mock_graph, mock_qdrant)
        
        initial = [
            {"metadata": {"article_id": "A", "doc_type": "law"}},
            {"metadata": {"article_id": "B", "doc_type": "law"}}
        ]
        
        expanded = expander.expand(initial, depth=1)
        assert len(expanded) == 0
