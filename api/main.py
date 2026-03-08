"""api/main.py — FastAPI 애플리케이션 진입점."""
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import analyze, parse
from api.dependencies import get_retriever, get_redis_client
from core.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시 싱글턴 초기화 (warm-up)
    logger.info("서비스 초기화 중...")
    get_retriever()
    get_redis_client()
    logger.info("서비스 준비 완료")
    yield
    logger.info("서비스 종료")


app = FastAPI(
    title="Web Legal Compliance AI Agent",
    description="한국 개인정보·보안·서비스 규정 자동 준수 검사 API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze.router)
app.include_router(parse.router)


@app.get("/health")
def health():
    return {"status": "ok"}
