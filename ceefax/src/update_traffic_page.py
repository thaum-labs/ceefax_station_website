"""
Update page 171 with road traffic information.

Uses UK traffic APIs to fetch motorway and road conditions.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

import requests

from .compiler import PAGE_WIDTH, PAGE_HEIGHT


def _pad(text: str) -> str:
    txt = text[:PAGE_WIDTH]
    return txt.ljust(PAGE_WIDTH)


# Google Maps API key (optional - for traffic data)
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")


def fetch_traffic_incidents() -> List[Dict]:
    """
    Fetch UK traffic incidents and road conditions.
    
    Uses TFL API for London traffic incidents.
    """
    incidents = []
    
    try:
        # TFL Road Disruptions API (free, no key needed)
        url = "https://api.tfl.gov.uk/Road/all/Disruption"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        for disruption in data[:5]:  # Get top 5 incidents
            category = disruption.get("category", "")
            severity = disruption.get("severity", "")
            description = disruption.get("description", "")
            location = disruption.get("location", "")
            
            if description:
                incidents.append({
                    "description": description[:PAGE_WIDTH - 20],
                    "location": location or "London",
                    "severity": severity,
                    "category": category
                })
    except Exception:  # noqa: BLE001
        pass
    
    return incidents


def fetch_motorway_status() -> List[Dict]:
    """
    Fetch UK motorway status from TFL API.
    Note: TFL API primarily covers London, but we'll use it for motorway info.
    """
    motorways = []
    
    try:
        # TFL Road Status API
        url = "https://api.tfl.gov.uk/Road"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        # Filter for motorways and major roads
        motorway_keywords = ["M1", "M4", "M5", "M6", "M25", "M40", "M3", "M2", "M11", "M20"]
        
        for road in data:
            display_name = road.get("displayName", "")
            status_severity = road.get("statusSeverity", "")
            status_description = road.get("statusSeverityDescription", "")
            
            # Check if it's a motorway
            is_motorway = any(keyword in display_name for keyword in motorway_keywords)
            
            if is_motorway or "Motorway" in display_name:
                motorways.append({
                    "road": display_name,
                    "status": status_description or "Good Service",
                    "details": ""
                })
        
        return motorways
    except Exception:  # noqa: BLE001
        # Return empty list on error - will show error message
        return []


def build_traffic_page() -> List[str]:
    """Build road/traffic information page."""
    lines: List[str] = []
    lines.append(_pad("ROAD / TRAFFIC INFORMATION"))
    lines.append(_pad(""))
    
    # Motorways section
    lines.append(_pad("MOTORWAYS"))
    sep = _pad("-" * PAGE_WIDTH)
    lines.append(sep)
    
    motorway_status = fetch_motorway_status()
    
    if motorway_status:
        for motorway in motorway_status[:5]:
            road = motorway.get("road", "Unknown")
            status = motorway.get("status", "Unknown")
            details = motorway.get("details", "")
            if details:
                lines.append(_pad(f"{road}: {status} {details}"))
            else:
                lines.append(_pad(f"{road}: {status}"))
    else:
        lines.append(_pad("Error: Could not fetch motorway"))
        lines.append(_pad("status"))
        lines.append(_pad(""))
        lines.append(_pad("TFL API may be temporarily"))
        lines.append(_pad("unavailable."))
    
    lines.append(_pad(""))
    
    # Major roads section
    lines.append(_pad("MAJOR ROADS"))
    lines.append(sep)
    
    lines.append(_pad("Error: A-road status not"))
    lines.append(_pad("available"))
    lines.append(_pad(""))
    lines.append(_pad("API integration required"))
    
    lines.append(_pad(""))
    
    # Incidents section
    lines.append(_pad("INCIDENTS"))
    lines.append(sep)
    
    incidents = fetch_traffic_incidents()
    
    if incidents:
        for incident in incidents[:3]:
            desc = incident.get("description", "Unknown")[:PAGE_WIDTH - 5]
            location = incident.get("location", "")
            if location:
                lines.append(_pad(f"{location}: {desc}"))
            else:
                lines.append(_pad(desc))
    else:
        lines.append(_pad("Error: Could not fetch"))
        lines.append(_pad("traffic incidents"))
        lines.append(_pad(""))
        lines.append(_pad("TFL API may be unavailable"))
    
    lines.append(_pad(""))
    
    # Roadworks section
    lines.append(_pad("ROADWORKS"))
    lines.append(sep)
    
    lines.append(_pad("Error: Roadworks data not"))
    lines.append(_pad("available"))
    lines.append(_pad(""))
    lines.append(_pad("API integration required"))
    
    lines.append(_pad(""))
    lines.append(_pad("Source: TFL Unified API"))
    
    return lines[:PAGE_HEIGHT]


def main() -> None:
    """Update page 171 with road/traffic information."""
    root = Path(__file__).resolve().parent.parent
    pages_dir = root / "pages"
    page_file = pages_dir / "171.json"
    
    content = build_traffic_page()
    
    page = {
        "page": "171",
        "title": "Road / Traffic Info",
        "timestamp": datetime.now().isoformat() + "Z",
        "subpage": 1,
        "content": content,
    }
    
    page_file.write_text(json.dumps(page, indent=2), encoding="utf-8")
    print(f"Updated {page_file} with traffic information")


if __name__ == "__main__":
    main()

