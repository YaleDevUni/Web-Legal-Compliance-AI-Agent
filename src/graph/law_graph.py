"""src/graph/law_graph.py — NetworkX 기반 법령 관계 그래프"""
import networkx as nx
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional

class LawGraph:
    def __init__(self) -> None:
        self._graph = nx.DiGraph()

    def add_article(self, article_id: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """조문 노드를 추가한다."""
        if not self._graph.has_node(article_id):
            self._graph.add_node(article_id, **(metadata or {}))

    def add_reference(self, src_id: str, dst_id: str) -> None:
        """참조 관계(엣지)를 추가한다."""
        self._graph.add_edge(src_id, dst_id)

    def get_related(self, article_id: str, depth: int = 2) -> List[str]:
        """BFS로 연관 조문 ID 리스트를 반환한다 (본인 제외)."""
        if not self._graph.has_node(article_id):
            return []
            
        related = set()
        visited = {article_id}
        current_layer = {article_id}
        
        for _ in range(depth):
            next_layer = set()
            for node in current_layer:
                # 1. 내가 참조하는 조문 (Successors)
                for neighbor in self._graph.successors(node):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        related.add(neighbor)
                        next_layer.add(neighbor)
                # 2. 나를 참조하는 조문 (Predecessors)
                for pred in self._graph.predecessors(node):
                    if pred not in visited:
                        visited.add(pred)
                        related.add(pred)
                        next_layer.add(pred)
            current_layer = next_layer
            if not current_layer:
                break
                
        return list(related)

    def save(self, path: str) -> None:
        """그래프를 파일로 저장한다."""
        parent = Path(path).parent
        parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self._graph, f)

    def load(self, path: str) -> None:
        """그래프를 파일에서 로드한다."""
        if Path(path).exists():
            with open(path, "rb") as f:
                self._graph = pickle.load(f)
        else:
            raise FileNotFoundError(f"Graph file not found: {path}")

    @property
    def node_count(self) -> int:
        return self._graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self._graph.number_of_edges()
