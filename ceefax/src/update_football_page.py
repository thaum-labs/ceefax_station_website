import json
from pathlib import Path
from typing import List

import re
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

from .compiler import PAGE_WIDTH, PAGE_HEIGHT


BBC_FOOTBALL_RSS = "https://feeds.bbci.co.uk/sport/football/rss.xml"
BBC_PL_TABLE_URL = "https://www.bbc.co.uk/sport/football/premier-league/table"
BBC_CHAMPIONSHIP_TABLE_URL = "https://www.bbc.co.uk/sport/football/championship/table"
SCORE_RE = re.compile(r"\b\d{1,2}\s*-\s*\d{1,2}\b")


def _pad(text: str) -> str:
    txt = text[:PAGE_WIDTH]
    return txt.ljust(PAGE_WIDTH)


def fetch_results(limit: int = 6) -> List[str]:
    """
    Fetch recent football headlines from BBC Sport RSS.
    Many titles include scorelines which we can display directly.
    """
    resp = requests.get(BBC_FOOTBALL_RSS, timeout=10)
    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    items = root.findall("./channel/item/title")
    titles: List[str] = []
    for item in items[:limit]:
        if item.text:
            titles.append(item.text.strip())
    return titles


def fetch_league_rows(url: str, limit: int = 20) -> List[List[str]]:
    """
    Fetch league table rows from the BBC table page.

    Returns a list of [pos, team, p, w, d, l, f, a, gd, pts].
    """
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if not table or not table.tbody:
        raise RuntimeError("Could not find league table on BBC page")

    rows: List[List[str]] = []
    for tr in table.tbody.find_all("tr")[:limit]:
        # Get entire row text as tokens
        row_text = tr.get_text(" ", strip=True).replace("–", "-")
        tokens = row_text.split()
        if len(tokens) < 10:
            continue

        # First token is position
        pos = tokens[0]

        # Find index of the first numeric after pos (this is P)
        p_idx = None
        for i, tok in enumerate(tokens[1:], start=1):
            if tok.lstrip("+-").isdigit():
                p_idx = i
                break
        if p_idx is None:
            continue

        # Team name is everything between pos and first numeric token
        team_tokens = tokens[1:p_idx]
        team = " ".join(team_tokens)

        # Remaining numeric tokens: P, W, D, L, F, A, GD, Pts, ...
        numeric_tokens = [t for t in tokens[p_idx:] if t.lstrip("+-").isdigit()]
        if len(numeric_tokens) < 8:
            continue
        p, w, d, l, f, a, gd, pts = numeric_tokens[:8]

        rows.append([pos, team, p, w, d, l, f, a, gd, pts])
    return rows


def build_football_page() -> List[str]:
    lines: List[str] = []
    lines.append(_pad("SPORTS HEADLINES"))
    # Separator line spanning full page width, used between stories
    sep = _pad("-" * PAGE_WIDTH)
    # Keep pages uniform: show the "blue line" directly under the top heading.
    lines.append(sep)

    try:
        results = fetch_results(limit=6)
    except Exception as exc:  # noqa: BLE001
        lines.append(_pad("Error fetching football results:"))
        lines.append(_pad(str(exc)[: PAGE_WIDTH]))
        return lines[:PAGE_HEIGHT]

    lines.append(_pad("COMP / FIXTURE / RESULT"))
    lines.append(sep)

    for title in results:
        # We simply show the RSS title; many already contain scores.
        wrapped = []
        text = title
        while text:
            wrapped.append(_pad(text[: PAGE_WIDTH]))
            text = text[PAGE_WIDTH:]
        lines.extend(wrapped)
        lines.append(sep)

    lines.append(_pad("Source: BBC Sport Football RSS"))

    return lines[:PAGE_HEIGHT]


def build_premier_league_table_page() -> List[str]:
    """
    Ceefax-style Premier League table page.

    Uses the BBC Premier League table HTML, rendered as:
      Pos Team           P  W  D  L  F  A Pts
    """
    lines: List[str] = []
    table_width = PAGE_WIDTH

    def sep(char: str = "-") -> str:
        return _pad(char * table_width)

    lines.append(_pad("PREMIER LEAGUE TABLE (BBC Sport)"))

    # Cleaner header: widen team column and use GD + Pts (fits PAGE_WIDTH=50 nicely)
    header = (
        f"{'Pos':>2} "
        f"{'Team':<25} "
        f"{'P':>2} {'W':>2} {'D':>2} {'L':>2} "
        f"{'GD':>3} {'Pts':>3}"
    )
    lines.append(_pad(header))
    lines.append(sep("="))

    try:
        rows = fetch_league_rows(BBC_PL_TABLE_URL, limit=20)
    except Exception as exc:  # noqa: BLE001
        lines.append(_pad("Error fetching league table:"))
        lines.append(_pad(str(exc)[: PAGE_WIDTH]))
        return lines[:PAGE_HEIGHT]

    for pos, team, p, w, d, l, _f, _a, gd, pts in rows:
        # Allow up to 25 chars for team name; keep alignment stable
        name = team[:25]

        row = (
            f"{pos:>2} "
            f"{name:<25} "
            f"{p:>2} {w:>2} {d:>2} {l:>2} "
            f"{gd:>3} {pts:>3}"
        )
        lines.append(_pad(row))

    lines.append(sep("="))
    lines.append(_pad("Source: BBC Premier League (bbc.co.uk/sport)"))

    return lines[:PAGE_HEIGHT]


def build_championship_table_page() -> List[str]:
    """
    Ceefax-style Championship league table page.

    Uses the BBC Championship table HTML, rendered as:
      Pos Team           P  W  D  L  F  A Pts
    """
    lines: List[str] = []
    table_width = PAGE_WIDTH

    def sep(char: str = "-") -> str:
        return _pad(char * table_width)

    lines.append(_pad("CHAMPIONSHIP TABLE (BBC Sport)"))

    # Match Premier League formatting for consistency
    header = (
        f"{'Pos':>2} "
        f"{'Team':<25} "
        f"{'P':>2} {'W':>2} {'D':>2} {'L':>2} "
        f"{'GD':>3} {'Pts':>3}"
    )
    lines.append(_pad(header))
    lines.append(sep("="))

    try:
        rows = fetch_league_rows(BBC_CHAMPIONSHIP_TABLE_URL, limit=20)
    except Exception as exc:  # noqa: BLE001
        lines.append(_pad("Error fetching league table:"))
        lines.append(_pad(str(exc)[: PAGE_WIDTH]))
        return lines[:PAGE_HEIGHT]

    for pos, team, p, w, d, l, _f, _a, gd, pts in rows:
        name = team[:25]

        row = (
            f"{pos:>2} "
            f"{name:<25} "
            f"{p:>2} {w:>2} {d:>2} {l:>2} "
            f"{gd:>3} {pts:>3}"
        )
        lines.append(_pad(row))

    lines.append(sep("="))
    lines.append(_pad("Source: BBC Championship (bbc.co.uk/sport)"))

    return lines[:PAGE_HEIGHT]

def main() -> None:
    """
    Update page 300 with latest sports headlines,
    page 302 with Premier League table, and page 303 with Championship table.
    """
    root = Path(__file__).resolve().parent.parent
    pages_dir = root / "pages"
    
    # Page 300: Sports Headlines
    page_file = pages_dir / "300.json"
    content = build_football_page()
    page = {
        "page": "300",
        "title": "Sports Headlines",
        "timestamp": "From BBC Sport RSS (live)",
        "subpage": 1,
        "content": content,
    }
    page_file.write_text(json.dumps(page, indent=2), encoding="utf-8")
    print(f"Updated {page_file} with latest sports headlines")

    # Page 302: Premier League Table
    pl_table_content = build_premier_league_table_page()
    page_file_pl = pages_dir / "302.json"
    page_pl = {
        "page": "302",
        "title": "Premier League Table",
        "timestamp": "From BBC Sport (live)",
        "subpage": 1,
        "content": pl_table_content,
    }
    page_file_pl.write_text(json.dumps(page_pl, indent=2), encoding="utf-8")
    print(f"Updated {page_file_pl} with Premier League table")

    # Page 303: Championship Table
    champ_table_content = build_championship_table_page()
    page_file_champ = pages_dir / "303.json"
    page_champ = {
        "page": "303",
        "title": "Championship Table",
        "timestamp": "From BBC Sport (live)",
        "subpage": 1,
        "content": champ_table_content,
    }
    page_file_champ.write_text(json.dumps(page_champ, indent=2), encoding="utf-8")
    print(f"Updated {page_file_champ} with Championship table")


if __name__ == "__main__":
    main()


