"""src/collector/parser.py — law.go.kr XML 응답 파서"""
from datetime import datetime
from xml.etree import ElementTree as ET

from core.logger import logger
from core.models import LawArticle
from integrity.hasher import compute_sha256


def _text(el: ET.Element | None, default: str = "") -> str:
    if el is None:
        return default
    return (el.text or "").strip()


def parse_law_xml(xml_text: str) -> list[LawArticle]:
    """law.go.kr XML 응답을 LawArticle 리스트로 변환한다."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.error(f"XML 파싱 실패: {e}")
        return []

    law_info = root.find("법령/기본정보")
    if law_info is None:
        return []

    law_name = _text(law_info.find("법령명_한글"))
    law_id = _text(law_info.find("법령ID"))
    updated_at_raw = _text(law_info.find("시행일자"))

    try:
        updated_at = datetime.strptime(updated_at_raw, "%Y%m%d") if updated_at_raw else datetime.now()
    except ValueError:
        updated_at = datetime.now()

    articles: list[LawArticle] = []
    for unit in root.findall("법령/조문/조문단위"):
        number = _text(unit.find("조문번호"))
        content = _text(unit.find("조문내용"))

        if not content:
            logger.warning(f"조문내용 누락: {law_id}_{number}")
            continue

        try:
            article = LawArticle(
                article_id=f"{law_id}_{number}",
                law_name=law_name,
                article_number=f"제{number}조",
                content=content,
                sha256=compute_sha256(content),
                url=f"https://www.law.go.kr/법령/{law_name}",
                updated_at=updated_at,
            )
            articles.append(article)
        except Exception as e:
            logger.error(f"LawArticle 생성 실패 ({law_id}_{number}): {e}")

    return articles
