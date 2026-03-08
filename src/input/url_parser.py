"""src/input/url_parser.py — URL 정적 파싱 (requests + BeautifulSoup4)"""
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

_LEGAL_KEYWORDS = re.compile(
    r"개인정보|privacy|cookie|쿠키|이용약관|terms|consent|동의|법적고지|고지|운영정책|사업자|about",
    re.IGNORECASE,
)
_SUBPAGE_TEXT_LIMIT = 30_000  # 서브페이지 텍스트 최대 30KB


_SPA_THRESHOLD = 500  # 이 글자 수 이하면 SPA 빈 껍데기로 간주


def _fetch_text(url: str, timeout: int) -> str:
    """URL에서 가시 텍스트만 추출. SPA 빈 응답이면 '[SPA: 내용을 가져올 수 없음]' 반환."""
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")
        text = soup.get_text(separator="\n", strip=True)[:_SUBPAGE_TEXT_LIMIT]
        if len(text) < _SPA_THRESHOLD:
            return "[SPA: 자바스크립트 렌더링으로 인해 내용을 가져올 수 없음]"
        return text
    except Exception:
        return ""


def parse_url(url: str, timeout: int = 10) -> dict:
    """URL을 파싱하여 텍스트·링크·메타데이터·법적 서브페이지 내용을 반환한다."""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"유효하지 않은 URL: {url}")

    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"

    soup = BeautifulSoup(response.text, "lxml")

    text = soup.get_text(separator="\n", strip=True)

    links = [
        f'<a href="{t.get("href", "")}">{t.get_text(strip=True)}</a>'
        for t in soup.find_all("a")
        if t.get("href") or t.get_text(strip=True)
    ]

    meta = {
        tag.get("name", tag.get("property", "")): tag.get("content", "")
        for tag in soup.find_all("meta")
        if tag.get("content")
    }

    # 법적 키워드 링크만 선별하여 서브페이지 내용 수집 (중복 제거)
    seen_urls: set[str] = set()
    subpages: list[tuple[str, str, str]] = []  # (link_text, href, content)
    for tag in soup.find_all("a", href=True):
        link_text = tag.get_text(strip=True)
        href = tag["href"]
        if not _LEGAL_KEYWORDS.search(link_text + href):
            continue
        full_url = urljoin(url, href)
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)
        content = _fetch_text(full_url, timeout)
        if content:
            subpages.append((link_text, full_url, content))

    meta_lines = [f'<meta name="{k}" content="{v}">' for k, v in meta.items() if k]

    sections = ["[META]", *meta_lines, "\n[LINKS]", *links, "\n[TEXT]", text]
    for link_text, href, content in subpages:
        sections.append(f"\n[SUBPAGE: {link_text} | {href}]")
        sections.append(content)

    combined = "\n".join(sections)

    return {
        "combined": combined,
        "text": text,
        "links": links,
        "meta": meta,
        "subpages": [{"title": lt, "url": u, "text": c} for lt, u, c in subpages],
    }
