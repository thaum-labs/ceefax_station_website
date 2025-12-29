"""
Update page 301 with live football scores from BBC Sport.
"""
import json
from pathlib import Path
from typing import List

import requests
import xml.etree.ElementTree as ET

from .compiler import PAGE_WIDTH, PAGE_HEIGHT


BBC_FOOTBALL_RSS = "https://feeds.bbci.co.uk/sport/football/rss.xml"


def _pad(text: str) -> str:
    txt = text[:PAGE_WIDTH]
    return txt.ljust(PAGE_WIDTH)


def extract_scores(headlines: List[str]) -> List[str]:
    """Extract scorelines from football headlines."""
    import re

    score_re = re.compile(r"\b(\d{1,2})\s*[-–]\s*(\d{1,2})\b")
    scores = []

    for headline in headlines:
        # Look for score patterns like "Team 2-1 Other Team"
        match = score_re.search(headline)
        if match:
            # Try to extract team names and score
            parts = headline.split(match.group(0))
            if len(parts) >= 2:
                team1 = parts[0].strip()[-20:].strip()  # Last 20 chars before score
                team2 = parts[1].strip()[:20].strip()  # First 20 chars after score
                score = match.group(0)
                scores.append(f"{team1:20} {score:>6} {team2:<20}")
            else:
                scores.append(headline[:PAGE_WIDTH])
        else:
            # No score, but might be a fixture
            if "v" in headline.lower() or "vs" in headline.lower():
                scores.append(headline[:PAGE_WIDTH])

    return scores[:10]  # Limit to 10 items


def build_football_scores_page() -> List[str]:
    lines: List[str] = []
    lines.append(_pad("FOOTBALL LIVE SCORES"))

    try:
        resp = requests.get(BBC_FOOTBALL_RSS, timeout=10)
        resp.raise_for_status()

        root = ET.fromstring(resp.content)
        items = root.findall("./channel/item/title")
        headlines: List[str] = []
        for item in items[:15]:
            if item.text:
                headlines.append(item.text.strip())

        scores = extract_scores(headlines)

        sep = _pad("-" * PAGE_WIDTH)
        lines.append(sep)
        lines.append(_pad("PREMIER LEAGUE"))
        lines.append(sep)

        for score in scores[:6]:
            lines.append(_pad(score))
            if score != scores[-1]:
                lines.append(_pad(""))

        if len(scores) > 6:
            lines.append(sep)
            lines.append(_pad("OTHER LEAGUES"))
            lines.append(sep)
            for score in scores[6:]:
                lines.append(_pad(score))
                if score != scores[-1]:
                    lines.append(_pad(""))

    except Exception as exc:  # noqa: BLE001
        lines.append(_pad("Error fetching scores:"))
        lines.append(_pad(str(exc)[: PAGE_WIDTH]))
        return lines[:PAGE_HEIGHT]

    lines.append(_pad(""))
    lines.append(_pad("Source: BBC Sport"))

    return lines[:PAGE_HEIGHT]


def main() -> None:
    """Update page 301 with latest football live scores."""
    root = Path(__file__).resolve().parent.parent
    pages_dir = root / "pages"
    page_file = pages_dir / "301.json"

    content = build_football_scores_page()

    page = {
        "page": "301",
        "title": "Football Live Scores",
        "timestamp": "From BBC Sport (live)",
        "subpage": 1,
        "content": content,
    }

    page_file.write_text(json.dumps(page, indent=2), encoding="utf-8")
    print(f"Updated {page_file} with latest football live scores")


if __name__ == "__main__":
    main()

