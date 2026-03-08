"""api/main.py — 부동산 법률 상담 AI API 진입점"""
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

# src 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import chat, search
from api.dependencies import get_law_retriever, get_case_retriever, get_redis_client
from core.logger import logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시 싱글턴 초기화 (warm-up)
    logger.info("서비스 초기화 및 검색기 워밍업...")
    get_law_retriever()
    get_case_retriever()
    get_redis_client()
    logger.info("서비스 준비 완료")
    yield
    logger.info("서비스 종료")

app = FastAPI(
    title="부동산 법률 AI 상담사",
    description="대한민국 부동산 법령 및 판례 기반 RAG 상담 API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 개발 환경 편의를 위해 전체 허용 (추후 제한 권장)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(search.router)

@app.get("/health")
def health():
    return {"status": "ok"}
