"""
Update page 202 with UK news from BBC UK RSS.
"""
import json
from pathlib import Path
from typing import List

import requests
import xml.etree.ElementTree as ET

from .compiler import PAGE_WIDTH, PAGE_HEIGHT


BBC_UK_RSS = "https://feeds.bbci.co.uk/news/uk/rss.xml"


def _pad(text: str) -> str:
    txt = text[:PAGE_WIDTH]
    return txt.ljust(PAGE_WIDTH)


def fetch_headlines(limit: int = 6) -> List[str]:
    """Fetch top headlines from BBC UK RSS."""
    resp = requests.get(BBC_UK_RSS, timeout=10)
    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    items = root.findall("./channel/item/title")
    titles: List[str] = []
    for item in items[:limit]:
        if item.text:
            titles.append(item.text.strip())
    return titles


def build_uk_news_page() -> List[str]:
    lines: List[str] = []
    lines.append(_pad("UK NEWS"))

    try:
        headlines = fetch_headlines()
    except Exception as exc:  # noqa: BLE001
        lines.append(_pad("Error fetching headlines:"))
        lines.append(_pad(str(exc)[: PAGE_WIDTH]))
        return lines[:PAGE_HEIGHT]

    sep = _pad("-" * PAGE_WIDTH)

    for title in headlines:
        wrapped = []
        text = title
        while text:
            wrapped.append(_pad(text[: PAGE_WIDTH]))
            text = text[PAGE_WIDTH:]
        lines.extend(wrapped)
        lines.append(sep)

    lines.append(_pad("Source: BBC UK RSS Feed"))

    return lines[:PAGE_HEIGHT]


def main() -> None:
    """Update page 202 with latest UK news headlines."""
    root = Path(__file__).resolve().parent.parent
    pages_dir = root / "pages"
    page_file = pages_dir / "202.json"

    content = build_uk_news_page()

    page = {
        "page": "202",
        "title": "UK News",
        "timestamp": "From BBC UK RSS (live)",
        "subpage": 1,
        "content": content,
    }

    page_file.write_text(json.dumps(page, indent=2), encoding="utf-8")
    print(f"Updated {page_file} with latest UK news headlines")


if __name__ == "__main__":
    main()

