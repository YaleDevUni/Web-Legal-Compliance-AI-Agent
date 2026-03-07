"""agents/citation.py — Citation Assembler: 검색 결과를 Citation 객체로 변환"""
from datetime import datetime

from core.models import Citation


class CitationAssembler:
    """검색 청크 리스트를 Citation 객체 리스트로 변환하고 중복을 제거."""

    def assemble(self, chunks: list[dict]) -> list[Citation]:
        """chunks → 중복 제거된 Citation 리스트.

        article_id 기준으로 첫 번째 등장 청크만 사용.
        """
        seen: set[str] = set()
        citations: list[Citation] = []
        for chunk in chunks:
            meta = chunk.get("metadata", {})
            article_id = meta.get("article_id", chunk.get("id", ""))
            if article_id in seen:
                continue
            seen.add(article_id)
            updated_at = meta.get("updated_at")
            if isinstance(updated_at, str):
                updated_at = datetime.fromisoformat(updated_at)
            citations.append(
                Citation(
                    article_id=article_id,
                    law_name=meta.get("law_name", ""),
                    article_number=meta.get("article_number", ""),
                    sha256=meta.get("sha256", "0" * 64),
                    url=meta.get("url", "https://www.law.go.kr/"),
                    updated_at=updated_at or datetime.now(),
                )
            )
        return citations
