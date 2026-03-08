"""src/core/config.py — 환경변수 기반 설정"""
from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 필수 항목
    openai_api_key: str
    law_api_key: str

    # 선택 항목 (기본값 있음)
    qdrant_url: AnyHttpUrl = Field(default="http://localhost:6333")
    qdrant_collection: str = "law_articles"
    redis_url: str = "redis://localhost:6379"

    # 앱 설정
    env: str = "dev"
    log_level: str = "INFO"

    # 성능 최적화
    llm_concurrency: int = 3                  # 동시 LLM 처리 최대 수
    cache_similarity_threshold: float = 0.92  # 시맨틱 캐시 히트 유사도 임계값
