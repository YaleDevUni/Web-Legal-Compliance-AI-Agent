"""src/input/file_loader.py — 절대 경로 파일 로더"""
import os

_SUPPORTED = {".py", ".html", ".htm", ".js", ".css", ".ts", ".txt"}


def load_file(path: str) -> str:
    """파일을 읽어 텍스트로 반환한다."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")

    ext = os.path.splitext(path)[1].lower()
    if ext not in _SUPPORTED:
        raise ValueError(f"지원하지 않는 파일 형식입니다: {ext}")

    with open(path, encoding="utf-8") as f:
        return f.read()
