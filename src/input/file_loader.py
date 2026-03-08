"""src/input/file_loader.py — 파일 로더 (단일 파일 + ZIP)"""
import io
import os
import zipfile

_SUPPORTED = {".py", ".html", ".htm", ".js", ".css", ".ts", ".tsx", ".jsx", ".vue", ".txt"}

_BLOCKED_DIRS = {
    "node_modules", ".git", "dist", "build", ".next",
    "__pycache__", ".cache", "coverage", ".venv", "venv",
}

_FILE_SIZE_LIMIT = 100 * 1024  # 100KB per file


def load_file(path: str) -> str:
    """파일을 읽어 텍스트로 반환한다."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")

    ext = os.path.splitext(path)[1].lower()
    if ext not in _SUPPORTED:
        raise ValueError(f"지원하지 않는 파일 형식입니다: {ext}")

    with open(path, encoding="utf-8") as f:
        return f.read()


def _is_blocked(name: str) -> bool:
    """ZIP 내 파일 경로가 필터링 대상인지 확인."""
    parts = name.replace("\\", "/").split("/")
    # 차단 디렉터리 포함 여부
    if any(p in _BLOCKED_DIRS for p in parts):
        return True
    filename = parts[-1]
    # 미지원 확장자
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _SUPPORTED:
        return True
    # 미니파이 파일 (예: vendor.min.js)
    base = os.path.splitext(filename)[0]
    if base.endswith(".min"):
        return True
    return False


def load_zip(data: bytes) -> str:
    """ZIP bytes에서 소스 파일만 추출해 하나의 문자열로 반환한다.

    필터링 대상:
    - node_modules/, .git/, dist/, build/, .next/, __pycache__/ 등 디렉터리
    - *.min.js, *.min.css 등 미니파이 파일
    - 100KB 초과 파일
    - 지원하지 않는 확장자
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ValueError("유효하지 않은 ZIP 파일입니다.")

    sections: list[str] = []
    with zf:
        for info in zf.infolist():
            name = info.filename
            if name.endswith("/"):  # 디렉터리 엔트리 스킵
                continue
            if _is_blocked(name):
                continue
            if info.file_size > _FILE_SIZE_LIMIT:
                continue
            try:
                content = zf.read(name).decode("utf-8", errors="replace")
            except Exception:
                continue
            sections.append(f"// === {name} ===\n{content}")

    return "\n\n".join(sections)
