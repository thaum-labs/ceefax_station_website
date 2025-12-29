"""
Update page 305 with other sports news from BBC Sport.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict

import requests
import xml.etree.ElementTree as ET

from .compiler import PAGE_WIDTH, PAGE_HEIGHT


def _pad(text: str) -> str:
    txt = text[:PAGE_WIDTH]
    return txt.ljust(PAGE_WIDTH)


def fetch_other_sports() -> Dict[str, List[str]]:
    """
    Fetch other sports news from BBC Sport RSS feeds.
    """
    sports_data = {
        "rugby": [],
        "cricket": [],
        "tennis": [],
        "motorsport": []
    }
    
    # BBC Sport RSS feeds for different sports
    feeds = {
        "rugby": "https://feeds.bbci.co.uk/sport/rugby-union/rss.xml",
        "cricket": "https://feeds.bbci.co.uk/sport/cricket/rss.xml",
        "tennis": "https://feeds.bbci.co.uk/sport/tennis/rss.xml",
        "motorsport": "https://feeds.bbci.co.uk/sport/formula1/rss.xml"
    }
    
    for sport, url in feeds.items():
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            
            root = ET.fromstring(resp.content)
            items = root.findall("./channel/item/title")
            for item in items[:3]:  # Get top 3 headlines per sport
                if item.text:
                    sports_data[sport].append(item.text.strip()[:PAGE_WIDTH])
        except Exception:  # noqa: BLE001
            # Keep empty list if feed fails
            pass
    
    return sports_data


def build_other_sports_page() -> List[str]:
    """Build other sports page."""
    lines: List[str] = []
    lines.append(_pad("OTHER SPORTS"))
    lines.append(_pad(""))
    
    data = fetch_other_sports()
    sep = _pad("-" * PAGE_WIDTH)
    
    # Rugby
    lines.append(_pad("RUGBY"))
    lines.append(sep)
    if data.get("rugby"):
        for headline in data["rugby"]:
            lines.append(_pad(headline))
    else:
        lines.append(_pad("Error: Could not fetch rugby news"))
        lines.append(_pad("BBC Sport RSS may be unavailable"))
    
    lines.append(_pad(""))
    
    # Cricket
    lines.append(_pad("CRICKET"))
    lines.append(sep)
    if data.get("cricket"):
        for headline in data["cricket"]:
            lines.append(_pad(headline))
    else:
        lines.append(_pad("Error: Could not fetch cricket news"))
        lines.append(_pad("BBC Sport RSS may be unavailable"))
    
    lines.append(_pad(""))
    
    # Tennis
    lines.append(_pad("TENNIS"))
    lines.append(sep)
    if data.get("tennis"):
        for headline in data["tennis"]:
            lines.append(_pad(headline))
    else:
        lines.append(_pad("Error: Could not fetch tennis news"))
        lines.append(_pad("BBC Sport RSS may be unavailable"))
    
    lines.append(_pad(""))
    
    # Motorsport
    lines.append(_pad("MOTORSPORT"))
    lines.append(sep)
    if data.get("motorsport"):
        for headline in data["motorsport"]:
            lines.append(_pad(headline))
    else:
        lines.append(_pad("Error: Could not fetch motorsport"))
        lines.append(_pad("news. BBC Sport RSS unavailable"))
    
    lines.append(_pad(""))
    lines.append(_pad("Source: BBC Sport"))
    
    return lines[:PAGE_HEIGHT]


def main() -> None:
    """Update page 305 with other sports news."""
    root = Path(__file__).resolve().parent.parent
    pages_dir = root / "pages"
    page_file = pages_dir / "305.json"
    
    content = build_other_sports_page()
    
    page = {
        "page": "305",
        "title": "Other Sports",
        "timestamp": datetime.now().isoformat() + "Z",
        "subpage": 1,
        "content": content,
    }
    
    page_file.write_text(json.dumps(page, indent=2), encoding="utf-8")
    print(f"Updated {page_file} with other sports news")


if __name__ == "__main__":
    main()

