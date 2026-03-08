"""api/routers/parse.py — URL / 파일 파싱 엔드포인트."""
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from input.url_parser import parse_url
from input.file_loader import load_zip

router = APIRouter(prefix="/api", tags=["parse"])


class ParseURLRequest(BaseModel):
    url: str


class ParseURLResponse(BaseModel):
    combined: str
    char_count: int
    subpage_count: int
    subpage_titles: list[str]


class ParseFileResponse(BaseModel):
    combined: str
    char_count: int
    file_count: int


@router.post("/parse-url", response_model=ParseURLResponse)
def parse_url_endpoint(body: ParseURLRequest):
    try:
        parsed = parse_url(body.url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    subpages = parsed.get("subpages", [])
    return ParseURLResponse(
        combined=parsed["combined"],
        char_count=len(parsed["combined"]),
        subpage_count=len(subpages),
        subpage_titles=[s["title"] for s in subpages],
    )


@router.post("/parse-file", response_model=ParseFileResponse)
async def parse_file_endpoint(file: UploadFile = File(...)):
    data = await file.read()

    if file.filename and file.filename.endswith(".zip"):
        try:
            combined = load_zip(data)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        file_count = combined.count("// === ")
        return ParseFileResponse(
            combined=combined,
            char_count=len(combined),
            file_count=file_count,
        )

    # 일반 텍스트 파일
    try:
        combined = data.decode("utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"파일 디코딩 실패: {e}")

    return ParseFileResponse(combined=combined, char_count=len(combined), file_count=1)
