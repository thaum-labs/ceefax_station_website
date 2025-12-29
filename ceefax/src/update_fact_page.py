"""
Update page 500 with fact of the day from API.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import List

import requests

from .compiler import PAGE_WIDTH, PAGE_HEIGHT


def _pad(text: str) -> str:
    txt = text[:PAGE_WIDTH]
    return txt.ljust(PAGE_WIDTH)


def fetch_fact_of_the_day() -> str:
    """
    Fetch a fact from working APIs.
    Tries multiple sources for reliability.
    """
    # Try multiple fact APIs - using more reliable sources
    apis = [
        # Cat facts API (very reliable)
        ("https://catfact.ninja/fact", lambda r: r.json().get("fact", "")),
        # Number facts API
        ("https://numbersapi.com/random/trivia?json", lambda r: r.json().get("text", "")),
        # Useless facts (text format - more reliable than JSON)
        ("https://uselessfacts.jsph.pl/random.txt", lambda r: r.text.strip()),
    ]
    
    for url, parser in apis:
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            fact = parser(resp)
            if fact and len(fact) > 10:  # Ensure we got a valid fact
                return fact
        except Exception:  # noqa: BLE001
            continue
    
    # If all APIs fail
    raise RuntimeError("All fact APIs are unavailable. Please try again later.")


def build_fact_page() -> List[str]:
    """Build fact of the day page."""
    lines: List[str] = []
    lines.append(_pad("FACT OF THE DAY"))
    lines.append(_pad("-" * PAGE_WIDTH))
    lines.append(_pad(""))
    
    try:
        fact = fetch_fact_of_the_day()
        lines.append(_pad("Did you know?"))
        lines.append(_pad(""))
        
        # Word wrap the fact to fit page width
        words = fact.split()
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
        lines.append(_pad("Source: Useless Facts API"))
    except Exception as e:  # noqa: BLE001
        lines.append(_pad("Error: Could not fetch fact"))
        lines.append(_pad(""))
        error_msg = str(e)[:PAGE_WIDTH]
        lines.append(_pad(error_msg))
        lines.append(_pad(""))
        lines.append(_pad("Please try again later"))
    
    return lines[:PAGE_HEIGHT]


def main() -> None:
    """Update page 500 with fact of the day."""
    root = Path(__file__).resolve().parent.parent
    pages_dir = root / "pages"
    page_file = pages_dir / "500.json"
    
    content = build_fact_page()
    
    page = {
        "page": "500",
        "title": "Fact of the Day",
        "timestamp": datetime.now().isoformat() + "Z",
        "subpage": 1,
        "content": content,
    }
    
    page_file.write_text(json.dumps(page, indent=2), encoding="utf-8")
    print(f"Updated {page_file} with fact of the day")


if __name__ == "__main__":
    main()

