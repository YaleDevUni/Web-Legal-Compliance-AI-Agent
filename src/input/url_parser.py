"""src/input/url_parser.py — URL 정적 파싱 (requests + BeautifulSoup4)"""
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


def parse_url(url: str, timeout: int = 10) -> dict:
    """URL을 파싱하여 텍스트, 메타, 스크립트, 스타일시트를 반환한다."""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"유효하지 않은 URL: {url}")

    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"

    soup = BeautifulSoup(response.text, "lxml")

    meta = {
        tag.get("name", tag.get("property", "")): tag.get("content", "")
        for tag in soup.find_all("meta")
        if tag.get("content")
    }

    scripts = [
        urljoin(url, tag["src"])
        for tag in soup.find_all("script", src=True)
    ]

    stylesheets = [
        urljoin(url, tag["href"])
        for tag in soup.find_all("link", rel="stylesheet")
    ]

    text = soup.get_text(separator="\n", strip=True)

    return {"text": text, "meta": meta, "scripts": scripts, "stylesheets": stylesheets}
