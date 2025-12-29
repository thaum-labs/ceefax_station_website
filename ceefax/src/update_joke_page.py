"""
Update page 600 with joke of the day from API.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import requests

from .compiler import PAGE_WIDTH, PAGE_HEIGHT


def _pad(text: str) -> str:
    txt = text[:PAGE_WIDTH]
    return txt.ljust(PAGE_WIDTH)


def fetch_joke_of_the_day() -> Tuple[str, str]:
    """
    Fetch a random joke from joke API.
    Returns (setup, punchline) tuple.
    """
    try:
        url = "https://official-joke-api.appspot.com/random_joke"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        setup = data.get("setup", "Why don't scientists trust atoms?")
        punchline = data.get("punchline", "Because they make up everything!")
        if not setup or not punchline:
            raise ValueError("API returned incomplete joke data")
        return (setup, punchline)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"Failed to fetch joke from API: {str(e)}")


def build_joke_page() -> List[str]:
    """Build joke of the day page."""
    lines: List[str] = []
    lines.append(_pad("JOKE OF THE DAY"))
    lines.append(_pad("-" * PAGE_WIDTH))
    lines.append(_pad(""))
    
    try:
        setup, punchline = fetch_joke_of_the_day()
        
        # Word wrap setup
        words = setup.split()
        current_line = ""
        for word in words:
            if len(current_line) + len(word) + 1 <= PAGE_WIDTH:
                if current_line:
                    current_line += " " + word
                else:
                    current_line = word
            else:
                if current_line:
                    lines.append(_pad(current_line))
                current_line = word
        if current_line:
            lines.append(_pad(current_line))
        
        lines.append(_pad(""))
        
        # Word wrap punchline
        words = punchline.split()
        current_line = ""
        for word in words:
            if len(current_line) + len(word) + 1 <= PAGE_WIDTH:
                if current_line:
                    current_line += " " + word
                else:
                    current_line = word
            else:
                if current_line:
                    lines.append(_pad(current_line))
                current_line = word
        if current_line:
            lines.append(_pad(current_line))
        
        lines.append(_pad(""))
        lines.append(_pad("-" * PAGE_WIDTH))
        lines.append(_pad(""))
        lines.append(_pad("Source: Official Joke API"))
    except Exception as e:  # noqa: BLE001
        lines.append(_pad("Error: Could not fetch joke"))
        lines.append(_pad(""))
        error_msg = str(e)[:PAGE_WIDTH]
        lines.append(_pad(error_msg))
        lines.append(_pad(""))
        lines.append(_pad("Please try again later"))
    
    return lines[:PAGE_HEIGHT]


def main() -> None:
    """Update page 600 with joke of the day."""
    root = Path(__file__).resolve().parent.parent
    pages_dir = root / "pages"
    page_file = pages_dir / "600.json"
    
    content = build_joke_page()
    
    page = {
        "page": "600",
        "title": "Joke of the Day",
        "timestamp": datetime.now().isoformat() + "Z",
        "subpage": 1,
        "content": content,
    }
    
    page_file.write_text(json.dumps(page, indent=2), encoding="utf-8")
    print(f"Updated {page_file} with joke of the day")


if __name__ == "__main__":
    main()

