import json
from pathlib import Path
from typing import List

import requests
import xml.etree.ElementTree as ET

from .compiler import PAGE_WIDTH, PAGE_HEIGHT


BBC_SOMERSET_RSS = "https://feeds.bbci.co.uk/news/england/somerset/rss.xml"


def _pad(text: str) -> str:
    txt = text[:PAGE_WIDTH]
    return txt.ljust(PAGE_WIDTH)


def fetch_headlines(limit: int = 6) -> List[str]:
    """
    Fetch top headlines from BBC Somerset RSS.
    """
    resp = requests.get(BBC_SOMERSET_RSS, timeout=10)
    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    items = root.findall("./channel/item/title")
    titles: List[str] = []
    for item in items[:limit]:
        if item.text:
            titles.append(item.text.strip())
    return titles


def build_news_page() -> List[str]:
    lines: List[str] = []
    lines.append(_pad("NEWS HEADLINES"))

    try:
        headlines = fetch_headlines()
    except Exception as exc:  # noqa: BLE001
        lines.append(_pad("Error fetching headlines:"))
        lines.append(_pad(str(exc)[: PAGE_WIDTH]))
        return lines[:PAGE_HEIGHT]

    # Simple horizontal separator line spanning the full page width
    sep = _pad("-" * PAGE_WIDTH)
    # Keep pages uniform: show the "blue line" directly under the top heading.
    lines.append(sep)

    for title in headlines:
        wrapped = []
        text = title
        while text:
            wrapped.append(_pad(text[: PAGE_WIDTH]))
            text = text[PAGE_WIDTH:]
        lines.extend(wrapped)
        # Separator between stories
        lines.append(sep)

    lines.append(_pad("Source: BBC Somerset RSS"))

    return lines[:PAGE_HEIGHT]


def main() -> None:
    """
    Update page 200 with latest local news headlines.
    """
    root = Path(__file__).resolve().parent.parent
    pages_dir = root / "pages"
    page_file = pages_dir / "200.json"

    content = build_news_page()

    page = {
        "page": "200",
        "title": "News Headlines",
        "timestamp": "From BBC Somerset RSS (live)",
        "subpage": 1,
        "content": content,
    }

    page_file.write_text(json.dumps(page, indent=2), encoding="utf-8")
    print(f"Updated {page_file} with latest news headlines")


if __name__ == "__main__":
    main()


