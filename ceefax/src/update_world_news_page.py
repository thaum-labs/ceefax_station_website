"""
Update page 201 with world news from BBC World RSS.
"""
import json
from pathlib import Path
from typing import List

import requests
import xml.etree.ElementTree as ET

from .compiler import PAGE_WIDTH, PAGE_HEIGHT


BBC_WORLD_RSS = "https://feeds.bbci.co.uk/news/world/rss.xml"


def _pad(text: str) -> str:
    txt = text[:PAGE_WIDTH]
    return txt.ljust(PAGE_WIDTH)


def fetch_headlines(limit: int = 6) -> List[str]:
    """Fetch top headlines from BBC World RSS."""
    resp = requests.get(BBC_WORLD_RSS, timeout=10)
    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    items = root.findall("./channel/item/title")
    titles: List[str] = []
    for item in items[:limit]:
        if item.text:
            titles.append(item.text.strip())
    return titles


def build_world_news_page() -> List[str]:
    lines: List[str] = []
    lines.append(_pad("WORLD NEWS"))

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

    lines.append(_pad("Source: BBC World RSS Feed"))

    return lines[:PAGE_HEIGHT]


def main() -> None:
    """Update page 201 with latest world news headlines."""
    root = Path(__file__).resolve().parent.parent
    pages_dir = root / "pages"
    page_file = pages_dir / "201.json"

    content = build_world_news_page()

    page = {
        "page": "201",
        "title": "World News",
        "timestamp": "From BBC World RSS (live)",
        "subpage": 1,
        "content": content,
    }

    page_file.write_text(json.dumps(page, indent=2), encoding="utf-8")
    print(f"Updated {page_file} with latest world news headlines")


if __name__ == "__main__":
    main()

