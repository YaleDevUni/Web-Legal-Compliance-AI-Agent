"""tests/graph/test_law_graph.py — 법령 그래프 TDD"""
import os
import pytest
from graph.law_graph import LawGraph

@pytest.fixture
def graph():
    g = LawGraph()
    # A -> B -> C
    g.add_article("A")
    g.add_article("B")
    g.add_article("C")
    g.add_reference("A", "B")
    g.add_reference("B", "C")
    return g

def test_get_related_depth_1(graph):
    """Depth 1: 직접 참조/피참조만 반환"""
    related = graph.get_related("B", depth=1)
    assert len(related) == 2
    assert "A" in related
    assert "C" in related

def test_get_related_depth_2(graph):
    """Depth 2: 2단계 건너 조문까지 반환"""
    related = graph.get_related("A", depth=2)
    assert len(related) == 2
    assert "B" in related
    assert "C" in related

def test_save_and_load(graph, tmp_path):
    """그래프 저장 및 로드 확인"""
    save_path = str(tmp_path / "test_graph.pkl")
    graph.save(save_path)
    
    new_graph = LawGraph()
    new_graph.load(save_path)
    
    assert new_graph.node_count == 3
    assert new_graph.edge_count == 2
    assert "C" in new_graph.get_related("B", depth=1)
