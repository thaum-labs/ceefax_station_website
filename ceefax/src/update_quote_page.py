"""
Update page 501 with quote of the day from API.
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


def fetch_quote_of_the_day() -> Tuple[str, str]:
    """
    Fetch a quote from working quote APIs.
    Tries multiple sources for reliability.
    """
    # Try multiple quote APIs - using more reliable sources
    apis = [
        # Quote Garden API (usually reliable)
        ("https://quotegarden.io/api/v3/quotes/random", lambda r: (r.json().get("data", {}).get("quoteText", ""), r.json().get("data", {}).get("quoteAuthor", "Unknown"))),
        # Zen Quotes API
        ("https://zenquotes.io/api/random", lambda r: (r.json()[0].get("q", ""), r.json()[0].get("a", "Unknown"))),
        # Quotable API
        ("https://api.quotable.io/random", lambda r: (r.json().get("content", ""), r.json().get("author", "Unknown"))),
    ]
    
    for url, parser in apis:
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            quote, author = parser(resp)
            if quote and len(quote) > 10:  # Ensure we got a valid quote
                return (quote, author)
        except Exception:  # noqa: BLE001
            continue
    
    # If all APIs fail
    raise RuntimeError("All quote APIs are unavailable. Please try again later.")


def build_quote_page() -> List[str]:
    """Build quote of the day page."""
    lines: List[str] = []
    lines.append(_pad("QUOTE OF THE DAY"))
    lines.append(_pad("-" * PAGE_WIDTH))
    lines.append(_pad(""))
    
    try:
        quote, author = fetch_quote_of_the_day()
        
        # Word wrap the quote
        words = quote.split()
        current_line = ""
        for word in words:
            if len(current_line) + len(word) + 1 <= PAGE_WIDTH - 2:  # Account for quotes
                if current_line:
                    current_line += " " + word
                else:
                    current_line = f'"{word}'
            else:
                if current_line:
                    if not current_line.endswith('"'):
                        current_line += '"'
                    lines.append(_pad(current_line))
                current_line = f'"{word}'
        
        if current_line:
            if not current_line.endswith('"'):
                current_line += '"'
            lines.append(_pad(current_line))
        
        lines.append(_pad(""))
        lines.append(_pad(f"                    - {author}"))
        lines.append(_pad(""))
        lines.append(_pad("-" * PAGE_WIDTH))
        lines.append(_pad(""))
        lines.append(_pad("Source: Quote APIs (Zen/Quotable)"))
    except Exception as e:  # noqa: BLE001
        lines.append(_pad("Error: Could not fetch quote"))
        lines.append(_pad(""))
        error_msg = str(e)[:PAGE_WIDTH]
        lines.append(_pad(error_msg))
        lines.append(_pad(""))
        lines.append(_pad("Please try again later"))
    
    return lines[:PAGE_HEIGHT]


def main() -> None:
    """Update page 501 with quote of the day."""
    root = Path(__file__).resolve().parent.parent
    pages_dir = root / "pages"
    page_file = pages_dir / "501.json"
    
    content = build_quote_page()
    
    page = {
        "page": "501",
        "title": "Quote of the Day",
        "timestamp": datetime.now().isoformat() + "Z",
        "subpage": 1,
        "content": content,
    }
    
    page_file.write_text(json.dumps(page, indent=2), encoding="utf-8")
    print(f"Updated {page_file} with quote of the day")


if __name__ == "__main__":
    main()

