"""src/core/logger.py — loguru 기반 공통 로거"""
import sys
from loguru import logger

# 기본 핸들러 제거 후 재설정
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> — <level>{message}</level>",
    level="DEBUG",
    colorize=True,
)

__all__ = ["logger"]
