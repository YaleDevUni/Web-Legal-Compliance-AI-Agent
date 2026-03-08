"""api/dependencies.py — FastAPI 공유 싱글턴 의존성."""
from functools import lru_cache
from typing import Optional
from qdrant_client import QdrantClient
import redis as redis_lib

from core.config import Settings
from core.logger import logger
from retrieval.hybrid import HybridRetriever
from retrieval.graph_expander import GraphExpander
from graph.law_graph import LawGraph
from agents.legal_agent import LegalReasoningAgent
from session.conversation import SessionManager

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    settings = get_settings()
    return QdrantClient(url=str(settings.qdrant_url), timeout=30)

@lru_cache(maxsize=1)
def get_law_retriever() -> Optional[HybridRetriever]:
    try:
        client = get_qdrant_client()
        return HybridRetriever(client, collection="laws")
    except Exception as e:
        logger.warning(f"Law HybridRetriever 초기화 실패: {e}")
        return None

@lru_cache(maxsize=1)
def get_case_retriever() -> Optional[HybridRetriever]:
    try:
        client = get_qdrant_client()
        return HybridRetriever(client, collection="cases")
    except Exception as e:
        logger.warning(f"Case HybridRetriever 초기화 실패: {e}")
        return None

@lru_cache(maxsize=1)
def get_law_graph() -> Optional[LawGraph]:
    try:
        g = LawGraph()
        path = "data/graph/law_graph.pkl"
        g.load(path)
        return g
    except Exception as e:
        logger.warning(f"LawGraph 로드 실패: {e}")
        return None

@lru_cache(maxsize=1)
def get_graph_expander() -> Optional[GraphExpander]:
    graph = get_law_graph()
    if not graph: return None
    client = get_qdrant_client()
    return GraphExpander(graph, client)

@lru_cache(maxsize=1)
def get_legal_agent() -> LegalReasoningAgent:
    return LegalReasoningAgent(
        law_retriever=get_law_retriever(),
        case_retriever=get_case_retriever(),
        graph_expander=get_graph_expander()
    )

@lru_cache(maxsize=1)
def get_redis_client():
    try:
        settings = get_settings()
        client = redis_lib.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        return client
    except Exception as e:
        logger.warning(f"Redis 연결 실패: {e}")
        return None

@lru_cache(maxsize=1)
def get_session_manager() -> SessionManager:
    settings = get_settings()
    return SessionManager(settings.redis_url)
