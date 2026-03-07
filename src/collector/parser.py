"""src/collector/parser.py — law.go.kr XML/HTML 파서

parse_law_xml : API 응답 XML → list[LawArticle]  (API 키 사용 시)
parse_law_html: 다운로드 HTML → list[LawArticle] (직접 파일 제공 시)
두 함수 모두 동일한 LawArticle 형식을 반환하므로 이후 파이프라인은 동일하게 동작함.
"""
import re
from datetime import datetime
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

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


# ── 앵커 ID 파싱 헬퍼 ──────────────────────────────────────────────────────

_ANCHOR_RE = re.compile(r"^J(\d+):(\d+)$")          # J1:0, J7:2
_ENACT_DATE_RE = re.compile(r"\[시행\s*(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.")
_ARTICLE_NUM_RE = re.compile(r"^(제\d+조(?:의\d+)?)")


def _anchor_to_article_id(name: str, prefix: str) -> str | None:
    """'J7:2' → '{prefix}_7의2', 'J1:0' → '{prefix}_1', JP → None(스킵)."""
    m = _ANCHOR_RE.match(name)
    if not m:
        return None
    jo, ui = m.group(1), m.group(2)
    suffix = f"{jo}의{ui}" if ui != "0" else jo
    return f"{prefix}_{suffix}"


def parse_law_html(
    html_text: str,
    law_id_prefix: str = "LAW",
) -> list[LawArticle]:
    """law.go.kr 다운로드 HTML을 LawArticle 리스트로 변환한다.

    law_id_prefix: article_id 앞에 붙을 접두사. 법령별로 지정.
    예) 개인정보 보호법 → "PA", 정보통신망법 → "IC"
    API 키 발급 후 parse_law_xml 으로 전환해도 동일 포맷이므로 파이프라인 변경 불필요.
    """
    soup = BeautifulSoup(html_text, "lxml")

    # ── 법령명 ────────────────────────────────────────────────────────────────
    confnla = soup.find("div", class_="confnla1")
    law_name = "알 수 없음"
    h2_tag = None

    if confnla:
        h2_tag = confnla.find("h2") # Try finding as child first
        if not h2_tag:
            h2_tag = confnla.find_next_sibling("h2") # If not found, try as sibling

    if h2_tag:
        law_name = h2_tag.get_text(strip=True)

    if law_name == "알 수 없음":
        logger.warning(f"HTML에서 법령명 추출 실패. (confnla1 내부 h2 또는 다음 형제 h2 찾기 실패)")
        return []

    # ── 시행일 ────────────────────────────────────────────────────────────────
    updated_at = datetime.now()
    subtit = soup.find("div", class_="subtit1")
    if subtit:
        m = _ENACT_DATE_RE.search(subtit.get_text())
        if m:
            updated_at = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    else:
        logger.warning(f"HTML에서 'subtit1' div를 찾을 수 없음. 시행일 파싱 실패. 현재 시간 사용.")

    law_url = f"https://www.law.go.kr/법령/{law_name}"

    # ── 조문 순회 ─────────────────────────────────────────────────────────────
    articles: list[LawArticle] = []
    # name 속성이 _ANCHOR_RE 패턴과 일치하는 <a> 태그를 찾아 조문 시작점을 식별
    anchor_tags = soup.find_all("a", attrs={"name": _ANCHOR_RE})
    if not anchor_tags:
        logger.warning(f"HTML에서 조문 앵커 태그를 찾을 수 없음. (법령명: {law_name})")

    for anchor in anchor_tags:
        article_id_raw = anchor["name"]
        article_id = _anchor_to_article_id(article_id_raw, law_id_prefix)
        if not article_id:
            logger.warning(f"앵커 '{article_id_raw}'에서 article_id 파싱 실패. 스킵.")
            continue

        pgroup = anchor.find_next_sibling("div", class_="pgroup")
        if not pgroup:
            logger.warning(f"article_id '{article_id}'에 해당하는 'pgroup' div를 찾을 수 없음. 스킵.")
            continue

        # 장/절 제목 div는 gtit 클래스 p 포함 → 스킵
        if pgroup.find("p", class_="gtit"):
            logger.debug(f"article_id '{article_id}'는 장/절 제목이므로 스킵.")
            continue

        # 조문 제목 확인 (span.bl에 '제N조' 포함)
        bl = pgroup.find("span", class_="bl")
        if not bl:
            logger.warning(f"article_id '{article_id}'에서 조문 제목 span.bl을 찾을 수 없음. 스킵.")
            continue
        header_text = bl.get_text(strip=True)
        mn = _ARTICLE_NUM_RE.match(header_text)
        if not mn:
            logger.warning(f"article_id '{article_id}'의 헤더 텍스트 '{header_text}'에서 조문 번호 패턴 불일치. 스킵.")
            continue
        article_number = mn.group(1)

        # 개정·신설 주석 제거 후 텍스트 추출
        for sfon in pgroup.find_all("span", class_="sfon"):
            sfon.decompose()

        content = "\n".join(
            p.get_text(strip=True)
            for p in pgroup.find_all("p")
            if p.get_text(strip=True)
        ).strip()

        if not content:
            logger.warning(f"조문내용 누락: {article_id}. 스킵.")
            continue

        try:
            articles.append(
                LawArticle(
                    article_id=article_id,
                    law_name=law_name,
                    article_number=article_number,
                    content=content,
                    sha256=compute_sha256(content),
                    url=law_url,
                    updated_at=updated_at,
                )
            )
        except Exception as e:
            logger.error(f"LawArticle 생성 실패 ({article_id}): {e}")

    if not articles:
        logger.warning(f"'{law_name}' ({law_id_prefix}) 파일에서 최종적으로 파싱된 조문이 0개입니다.")
        
    return articles
