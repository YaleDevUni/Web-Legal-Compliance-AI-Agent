"""scripts/build_graph.py — SQLite 조문 로드 → 참조 파싱 → 그래프 생성"""
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from integrity.db import ArticleDB
from graph.reference_parser import ReferenceParser
from graph.law_graph import LawGraph
from core.logger import logger

def build_graph():
    db = ArticleDB()
    graph = LawGraph()
    parser = ReferenceParser()
    
    logger.info("조문 데이터를 로드합니다...")
    articles = db.get_all_articles()
    
    # 1. 모든 조문을 그래프 노드로 추가
    for art in articles:
        # 판례는 제외 (일단 법령 간 관계만)
        if art["article_id"].startswith("CASE_"):
            continue
        graph.add_article(art["article_id"], {
            "law_name": art["law_name"],
            "article_number": art["article_number"]
        })

    logger.info(f"총 {graph.node_count}개의 조문 노드가 추가되었습니다.")

    # 2. 각 조문의 본문을 파싱하여 참조 관계(엣지) 추가
    edge_count = 0
    for art in articles:
        if art["article_id"].startswith("CASE_"):
            continue
            
        src_id = art["article_id"]
        content = art["content"]
        current_law = art["law_name"]
        
        # 참조 추출: [(target_law, target_art_num), ...]
        references = parser.extract_references(content, current_law)
        
        for target_law, target_art_num in references:
            # DB에서 target_article_id 검색
            dst_id = db.find_article_id_by_law_and_num(target_law, target_art_num)
            
            if dst_id:
                graph.add_reference(src_id, dst_id)
                edge_count += 1
                
    logger.info(f"총 {edge_count}개의 참조 관계가 구축되었습니다.")

    # 3. 그래프 저장
    graph_path = "data/graph/law_graph.pkl"
    graph.save(graph_path)
    logger.info(f"그래프가 {graph_path}에 저장되었습니다.")
    
    db.close()

if __name__ == "__main__":
    build_graph()
