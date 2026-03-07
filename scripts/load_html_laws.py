"""scripts/load_html_laws.py — data/laws/*.html 법령 파일 → 색인 파이프라인

실행:
    uv run python scripts/load_html_laws.py

흐름:
    HTML 파싱(parse_law_html) → SHA 비교(ArticleDB) → 변경분 벡터 색인(ArticleIndexer)
API 키 발급 후에는 setup_index.py(LawAPIClient)로 동일 파이프라인 전환 가능.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from collector.parser import parse_law_html
from integrity.db import ArticleDB
from embedder.indexer import ArticleIndexer
from scripts.setup_index import run_setup_index

# 파일명 → article_id 접두사 매핑
LAW_PREFIX_MAP: dict[str, str] = {
    "개인정보보호법.html":      "PA",
    "정보통신법.html":          "IC",
    "위치정보법.html":          "LI",
    "안정성확보조치기준.html":  "SA",
    "전자상거래법.html":        "EC",
    "청소년보호법.html":        "YP",
    "신용정보법.html":          "CI",
}

LAWS_DIR = Path(__file__).parent.parent / "data" / "laws"


def load_html_laws() -> None:
    """data/laws/*.html을 파싱해 SHA 비교 후 변경분만 벡터 색인."""
    db = ArticleDB()
    indexer = ArticleIndexer()

    total_parsed = 0
    total_changed = 0

    for fname, prefix in LAW_PREFIX_MAP.items():
        path = LAWS_DIR / fname
        if not path.exists():
            print(f"[SKIP] {fname} — 파일 없음")
            continue

        html = path.read_text(encoding="utf-8", errors="replace")
        articles = parse_law_html(html, law_id_prefix=prefix)

        if not articles:
            print(f"[WARN] {fname} — 조문 0개 (파일 확인 필요)")
            continue

        # SHA 비교 → 변경된 article_id 수집
        changed_ids: set[str] = set()
        for article in articles:
            changed = db.upsert(
                article_id=article.article_id,
                sha256=article.sha256,
                updated_at=article.updated_at,
            )
            if changed:
                changed_ids.add(article.article_id)

        # 변경분만 색인
        if changed_ids:
            indexer.upsert(articles, changed_ids=changed_ids)

        total_parsed += len(articles)
        total_changed += len(changed_ids)
        print(f"[OK]   {fname:30s}  {prefix}  {len(articles):3d}개 조문  |  변경 {len(changed_ids):3d}개 색인")

    print(f"\n완료 — 총 {total_parsed}개 조문 파싱, {total_changed}개 변경분 색인")


if __name__ == "__main__":
    load_html_laws()
