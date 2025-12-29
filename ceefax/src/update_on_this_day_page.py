"""
Update page 502 with historical events that happened on this day.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict

import requests

from .compiler import PAGE_WIDTH, PAGE_HEIGHT


def _pad(text: str) -> str:
    txt = text[:PAGE_WIDTH]
    return txt.ljust(PAGE_WIDTH)


def fetch_on_this_day() -> Dict:
    """
    Fetch historical events for today's date from history API.
    """
    try:
        today = datetime.now()
        month = today.month
        day = today.day
        
        url = f"https://history.muffinlabs.com/date/{month}/{day}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        events = []
        if "data" in data and "Events" in data["data"]:
            for event in data["data"]["Events"][:5]:  # Get top 5 events
                year = event.get("year", "")
                text = event.get("text", "")
                if year and text:
                    events.append(f"{year} - {text}")
        
        if not events:
            raise ValueError("API returned no events for today")
        return {
            "date": f"{day} {today.strftime('%B').upper()}",
            "events": events
        }
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"Failed to fetch historical events from API: {str(e)}")


def build_on_this_day_page() -> List[str]:
    """Build on this day page."""
    lines: List[str] = []
    lines.append(_pad("ON THIS DAY"))
    lines.append(_pad(""))
    
    try:
        data = fetch_on_this_day()
        date_str = data.get("date", "")
        
        if date_str:
            lines.append(_pad(date_str))
        
        sep = _pad("-" * PAGE_WIDTH)
        lines.append(sep)
        lines.append(_pad(""))
        
        events = data.get("events", [])
        for event in events:
            # Word wrap if needed
            if len(event) <= PAGE_WIDTH:
                lines.append(_pad(event))
            else:
                words = event.split()
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
        
        lines.append(sep)
        lines.append(_pad(""))
        lines.append(_pad("Source: History API"))
    except Exception as e:  # noqa: BLE001
        lines.append(_pad("Error: Could not fetch historical"))
        lines.append(_pad("events"))
        lines.append(_pad(""))
        error_msg = str(e)[:PAGE_WIDTH]
        lines.append(_pad(error_msg))
        lines.append(_pad(""))
        lines.append(_pad("History API may be temporarily"))
        lines.append(_pad("unavailable. Please try again"))
        lines.append(_pad("later."))
    
    return lines[:PAGE_HEIGHT]


def main() -> None:
    """Update page 502 with on this day events."""
    root = Path(__file__).resolve().parent.parent
    pages_dir = root / "pages"
    page_file = pages_dir / "502.json"
    
    content = build_on_this_day_page()
    
    page = {
        "page": "502",
        "title": "On This Day",
        "timestamp": datetime.now().isoformat() + "Z",
        "subpage": 1,
        "content": content,
    }
    
    page_file.write_text(json.dumps(page, indent=2), encoding="utf-8")
    print(f"Updated {page_file} with on this day events")


if __name__ == "__main__":
    main()

