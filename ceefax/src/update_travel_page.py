"""
Update page 401 with TFL (Transport for London) status information.

Uses TFL Unified API (free, no API key required).
"""
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

import requests

from .compiler import PAGE_WIDTH, PAGE_HEIGHT


def _pad(text: str) -> str:
    txt = text[:PAGE_WIDTH]
    return txt.ljust(PAGE_WIDTH)


TFL_API_BASE = "https://api.tfl.gov.uk"


def fetch_tfl_line_status() -> List[Dict]:
    """
    Fetch TFL line status from TFL Unified API.
    Returns list of line statuses with name and status.
    """
    try:
        url = f"{TFL_API_BASE}/Line/Mode/tube,dlr,overground,elizabeth-line/Status"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        line_statuses = []
        for line_group in data:
            line_name = line_group.get("name", "Unknown")
            line_statuses_list = line_group.get("lineStatuses", [])
            
            # Get the most severe status
            status_text = "Good Service"
            for status in line_statuses_list:
                status_severity = status.get("statusSeverity", 10)
                status_description = status.get("statusSeverityDescription", "")
                reason = status.get("reason", "")
                
                # Lower severity number = worse service
                if status_severity < 10:
                    status_text = status_description
                    if reason:
                        # Truncate reason if too long
                        status_text = f"{status_description}: {reason[:30]}"
                    break
            
            line_statuses.append({
                "name": line_name,
                "status": status_text
            })
        
        return line_statuses
    except Exception as e:  # noqa: BLE001
        # Return empty list on error
        return []


def build_travel_page() -> List[str]:
    """Build travel information page with TFL statuses in table format."""
    lines: List[str] = []
    lines.append(_pad("TRAVEL INFORMATION"))
    lines.append(_pad(""))
    
    # TFL Status section - table format like page 210
    lines.append(_pad("TFL STATUS"))
    sep = _pad("-" * PAGE_WIDTH)
    lines.append(sep)
    
    tfl_statuses = fetch_tfl_line_status()
    
    if tfl_statuses:
        # Format as table: "Line Name        Status"
        for line_info in tfl_statuses[:12]:
            name = line_info.get("name", "Unknown")
            status = line_info.get("status", "Unknown")
            # Truncate status if too long
            if len(status) > 25:
                status = status[:22] + "..."
            # Format: "Bakerloo         Good Service"
            display = f"{name:<18} {status}"
            lines.append(_pad(display[:PAGE_WIDTH]))
    else:
        lines.append(_pad("Error: Could not fetch TFL status"))
        lines.append(_pad(""))
        lines.append(_pad("TFL API may be temporarily"))
        lines.append(_pad("unavailable. Please try again"))
        lines.append(_pad("later."))
    
    lines.append(_pad(""))
    lines.append(_pad("Source: TFL Unified API"))
    
    return lines[:PAGE_HEIGHT]


def main() -> None:
    """Update page 401 with TFL travel information."""
    root = Path(__file__).resolve().parent.parent
    pages_dir = root / "pages"
    page_file = pages_dir / "401.json"
    
    content = build_travel_page()
    
    page = {
        "page": "401",
        "title": "Travel Info",
        "timestamp": datetime.now().isoformat() + "Z",
        "subpage": 1,
        "content": content,
    }
    
    page_file.write_text(json.dumps(page, indent=2), encoding="utf-8")
    print(f"Updated {page_file} with TFL travel information")


if __name__ == "__main__":
    main()

