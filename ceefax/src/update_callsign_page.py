"""
Update page 700 with callsign information from PSK Reporter.

Fetches recent spots and statistics for the user's callsign from PSK Reporter.
"""
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

import requests

from .compiler import PAGE_WIDTH, PAGE_HEIGHT


def _pad(text: str) -> str:
    txt = text[:PAGE_WIDTH]
    return txt.ljust(PAGE_WIDTH)


def get_callsign_from_config() -> Optional[str]:
    """Get callsign from radio_config.json."""
    try:
        root = Path(__file__).resolve().parent.parent
        config_file = root / "radio_config.json"
        if config_file.exists():
            config_data = json.loads(config_file.read_text(encoding="utf-8"))
            return config_data.get("callsign")
    except Exception:  # noqa: BLE001
        pass
    return None


def fetch_psk_reporter_data(callsign: str) -> Optional[ET.Element]:
    """
    Fetch callsign data from PSK Reporter.
    
    PSK Reporter API endpoint: https://retrieve.pskreporter.info/query
    Returns XML data.
    
    Note: PSK Reporter has rate limiting. We'll handle 503 errors gracefully.
    """
    try:
        # PSK Reporter query API
        url = "https://retrieve.pskreporter.info/query"
        
        # Query parameters for recent spots
        # Try both sender and receiver queries to get more data
        # First try: spots where this callsign was the sender (transmitter)
        params = {
            "senderCallsign": callsign,
            "rxtime": "1",  # Last 24 hours
            "limit": "50"  # Limit results
        }
        
        headers = {
            "User-Agent": "Ceefax Station/1.0 (Amateur Radio)",
            "Accept": "application/xml",
            "Referer": "https://pskreporter.info/"
        }
        
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        
        # Check for rate limiting
        if resp.status_code == 503:
            # Try to parse error message
            try:
                error_data = resp.json()
                error_msg = error_data.get("message", "Rate limited")
                print(f"PSK Reporter rate limited: {error_msg}")
            except Exception:
                print("PSK Reporter rate limited (503)")
            return None
        
        resp.raise_for_status()
        
        # Check content type - might be JSON error or XML
        content_type = resp.headers.get("content-type", "").lower()
        if "json" in content_type:
            # Might be an error response in JSON
            try:
                error_data = resp.json()
                error_msg = error_data.get("message", "Unknown error")
                print(f"PSK Reporter API error: {error_msg}")
                return None
            except Exception:
                pass
        
        # PSK Reporter returns XML
        root = ET.fromstring(resp.content)
        return root
        
    except requests.exceptions.RequestException as e:
        print(f"Network error fetching PSK Reporter data: {e}")
        return None
    except ET.ParseError as e:
        print(f"XML parse error: {e}")
        print(f"Response content (first 200 chars): {resp.text[:200] if 'resp' in locals() else 'N/A'}")
        return None
    except Exception as e:  # noqa: BLE001
        print(f"Error fetching PSK Reporter data: {e}")
        return None


def fetch_last_report_days(callsign: str) -> Optional[int]:
    """
    If a callsign has no spots in the last 24h, PSK Reporter's site often still shows
    a "Monitoring CALL (last report XXX days ago)" message. This helper scrapes that
    value so we can show a correct "Last seen" without inventing data.
    """
    try:
        url = "https://pskreporter.info/pskmap.html"
        headers = {"User-Agent": "Ceefax Station/1.0 (Amateur Radio)"}

        # PSK Reporter has changed querystring keys over time; try a small set.
        param_sets = [
            {"callsign": callsign},
            {"senderCallsign": callsign},
            {"call": callsign},
            {"watch": callsign},
            # Some variants require an extra flag to render the "Monitoring ..." banner
            {"callsign": callsign, "mode": "FT8"},
        ]

        # Prefer an exact match for THIS callsign.
        exact_re = re.compile(
            rf"Monitoring\s+{re.escape(callsign)}\s*\(last\s+report\s+(\d+)\s+days?\s+ago\)",
            re.I,
        )
        generic_re = re.compile(r"last\s+report\s+(\d+)\s+days?\s+ago", re.I)

        for params in param_sets:
            try:
                resp = requests.get(url, params=params, timeout=10, headers=headers)
                resp.raise_for_status()
                text = resp.text

                m = exact_re.search(text)
                if m:
                    return int(m.group(1))

                # Fallback: if the page doesn't echo the callsign in the monitoring string,
                # still look for "last report X days ago".
                m2 = generic_re.search(text)
                if m2:
                    return int(m2.group(1))
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        return None
    return None


def parse_psk_data(root: ET.Element, callsign: str) -> Dict:
    """Parse PSK Reporter XML data into useful statistics."""
    stats = {
        "callsign": callsign,
        "total_spots": 0,
        "recent_contacts": [],
        "bands_used": [],
        "modes_used": [],
        "last_spot_time": None,
        "countries": set(),
    }
    
    try:
        # Prefer real spot reports over "activeReceiver" summaries.
        # activeReceiver can be noisy and may include entries that aren't actually
        # spots for the requested sender callsign.
        reports = root.findall(".//receptionReport")
        if not reports:
            # Fallback (older schema)
            reports = root.findall(".//receptionReports/receptionReport")

        # Strict time handling:
        # - Only accept spots with a valid Unix timestamp (seconds)
        # - Filter to last 24 hours for display
        now_ts = int(datetime.utcnow().timestamp())
        cutoff = now_ts - 24 * 60 * 60

        def _base_call(cs: str) -> str:
            return cs.split("/")[0].strip().upper()

        want = _base_call(callsign)

        def _parse_ts(ts_str: str) -> Optional[int]:
            ts_str = (ts_str or "").strip()
            if not ts_str:
                return None
            try:
                ts_val = int(float(ts_str))
            except Exception:  # noqa: BLE001
                return None
            # Handle milliseconds
            if ts_val > 10_000_000_000:
                ts_val = int(ts_val / 1000)
            # Reject non-epoch-ish values
            if ts_val < 1_000_000_000:
                return None
            # Reject future timestamps (clock skew etc.)
            if ts_val > now_ts + 3600:
                return None
            return ts_val

        filtered: List[ET.Element] = []
        latest_any_ts: Optional[int] = None
        for r in reports:
            sender = _base_call((r.get("senderCallsign") or r.get("sender") or ""))
            if sender != want:
                continue
            # flowStartSeconds is unix epoch seconds in PSK Reporter
            ts_val = _parse_ts(r.get("flowStartSeconds") or r.get("time") or r.get("timestamp") or "")
            if ts_val is not None:
                latest_any_ts = ts_val if latest_any_ts is None else max(latest_any_ts, ts_val)
            # Only include in "last 24h" if we have a valid timestamp and it's recent
            if ts_val is None or ts_val < cutoff:
                continue
            filtered.append(r)

        # If we couldn't find receptionReport entries, fall back to activeReceiver,
        # but ONLY if they look like they're tied to the sender and are within 24h.
        if not filtered and not reports:
            receivers = root.findall(".//activeReceiver")
            for r in receivers:
                ts_val = _parse_ts(r.get("flowStartSeconds") or "")
                if ts_val is not None:
                    latest_any_ts = ts_val if latest_any_ts is None else max(latest_any_ts, ts_val)
                if ts_val is None or ts_val < cutoff:
                    continue
                filtered.append(r)

        # Sort by timestamp descending if available
        def _ts(elem: ET.Element) -> int:
            ts_str = (elem.get("flowStartSeconds") or elem.get("time") or elem.get("timestamp") or "").strip()
            try:
                return int(float(ts_str)) if ts_str else 0
            except Exception:  # noqa: BLE001
                return 0

        filtered.sort(key=_ts, reverse=True)

        stats["total_spots"] = len(filtered)
        stats["last_spot_time"] = latest_any_ts

        # Process recent spots
        for receiver in filtered[:10]:  # Top 10 most recent
            contact = {}
            
            # Extract XML attributes
            contact["receiver"] = (
                receiver.get("receiverCallsign")
                or receiver.get("receiver")
                or receiver.get("callsign")
                or "?"
            )
            contact["frequency"] = receiver.get("frequency", "") or receiver.get("freq", "")
            contact["mode"] = receiver.get("mode", "") or receiver.get("modeName", "")
            # SNR might be in different attributes
            contact["snr"] = receiver.get("snr") or receiver.get("signalReport") or receiver.get("signal") or "?"
            contact["country"] = receiver.get("DXCC") or receiver.get("region") or receiver.get("country") or ""
            contact["locator"] = receiver.get("locator", "")
            # Get timestamp if available
            contact["time"] = receiver.get("flowStartSeconds", "")
            
            # Calculate band from frequency
            if contact["frequency"]:
                try:
                    freq_hz = float(contact["frequency"])
                    freq_mhz = freq_hz / 1000000
                    if freq_mhz < 2:
                        band = "160m"
                    elif freq_mhz < 4:
                        band = "80m"
                    elif freq_mhz < 7.5:
                        band = "40m"
                    elif freq_mhz < 10.2:
                        band = "30m"
                    elif freq_mhz < 14.5:
                        band = "20m"
                    elif freq_mhz < 18.2:
                        band = "17m"
                    elif freq_mhz < 21.5:
                        band = "15m"
                    elif freq_mhz < 24.9:
                        band = "12m"
                    elif freq_mhz < 30:
                        band = "10m"
                    elif freq_mhz < 54:
                        band = "6m"
                    elif freq_mhz < 148:
                        band = "2m"
                    elif freq_mhz < 450:
                        band = "70cm"
                    else:
                        band = f"{freq_mhz:.1f}MHz"
                    contact["band"] = band
                    if band not in stats["bands_used"]:
                        stats["bands_used"].append(band)
                except (ValueError, TypeError):
                    contact["band"] = "?"
            
            if contact["mode"] and contact["mode"] not in stats["modes_used"]:
                stats["modes_used"].append(contact["mode"])
            
            if contact["country"]:
                stats["countries"].add(contact["country"])
            
            stats["recent_contacts"].append(contact)
        
        stats["countries"] = sorted(list(stats["countries"]))[:5]  # Top 5 countries
        
    except Exception as e:  # noqa: BLE001
        print(f"Error parsing PSK data: {e}")
    
    return stats


def build_callsign_page(callsign: str) -> List[str]:
    """Build callsign information page."""
    lines: List[str] = []
    lines.append(_pad("CALLSIGN INFORMATION"))
    lines.append(_pad(""))
    
    sep = _pad("-" * PAGE_WIDTH)
    lines.append(_pad(f"CALLSIGN: {callsign.upper()}"))
    lines.append(sep)
    
    # Fetch data from PSK Reporter
    psk_xml = fetch_psk_reporter_data(callsign)
    
    if psk_xml is not None:
        stats = parse_psk_data(psk_xml, callsign)

        def _format_age(seconds_ago: int) -> str:
            if seconds_ago < 0:
                seconds_ago = 0
            if seconds_ago < 60:
                return f"{seconds_ago}s ago"
            if seconds_ago < 3600:
                return f"{seconds_ago // 60}m ago"
            if seconds_ago < 86400:
                return f"{seconds_ago // 3600}h ago"
            return f"{seconds_ago // 86400} days ago"

        # Summary statistics
        lines.append(_pad("RECENT ACTIVITY"))
        lines.append(sep)
        lines.append(_pad(f"Total Spots (24h): {stats['total_spots']}"))

        # Last seen (based on newest valid report time, even if older than 24h)
        last_ts = stats.get("last_spot_time")
        if isinstance(last_ts, int) and last_ts > 0:
            age_s = int(datetime.utcnow().timestamp() - last_ts)
            lines.append(_pad(f"Last seen: {_format_age(age_s)}"))
        else:
            # If XML doesn't contain older timestamps (common when 24h query is empty),
            # scrape PSK Reporter "last report X days ago" text.
            days = fetch_last_report_days(callsign)
            if isinstance(days, int) and days >= 0:
                lines.append(_pad(f"Last seen: {days} days ago"))

        if stats["total_spots"] == 0:
            if isinstance(last_ts, int) and last_ts > 0:
                days_ago = int((datetime.utcnow().timestamp() - last_ts) / 86400)
                lines.append(_pad(f"Monitoring {callsign.upper()} (last report {days_ago} days ago)"))
            else:
                days = fetch_last_report_days(callsign)
                if isinstance(days, int) and days >= 0:
                    lines.append(_pad(f"Monitoring {callsign.upper()} (last report {days} days ago)"))
                else:
                    lines.append(_pad(f"Monitoring {callsign.upper()} (no recent reports)"))
            lines.append(_pad(""))
        else:
            if stats["bands_used"]:
                bands_str = ", ".join(stats["bands_used"][:5])
                lines.append(_pad(f"Bands Used: {bands_str[:PAGE_WIDTH-13]}"))

            if stats["modes_used"]:
                modes_str = ", ".join(stats["modes_used"][:5])
                lines.append(_pad(f"Modes: {modes_str[:PAGE_WIDTH-7]}"))

            if stats["countries"]:
                countries_str = ", ".join(stats["countries"])
                lines.append(_pad(f"Countries: {countries_str[:PAGE_WIDTH-11]}"))

            lines.append(_pad(""))

            # Recent contacts
            if stats["recent_contacts"]:
                lines.append(_pad("RECENT SPOTS"))
                lines.append(sep)

                for contact in stats["recent_contacts"][:6]:  # Show top 6
                    receiver = str(contact.get("receiver", "?"))[:10]
                    band = str(contact.get("band", "?"))[:6]
                    mode = str(contact.get("mode", "?"))[:5]
                    country = str(contact.get("country", ""))[:12]

                    # Format: "Receiver   Band   Mode  Country"
                    if country:
                        line = f"{receiver:<10} {band:<6} {mode:<5} {country}"
                    else:
                        line = f"{receiver:<10} {band:<6} {mode:<5}"
                    lines.append(_pad(line[:PAGE_WIDTH]))
    else:
        lines.append(_pad("PSK REPORTER DATA"))
        lines.append(sep)
        lines.append(_pad("Unable to fetch data from"))
        lines.append(_pad("PSK Reporter at this time."))
        lines.append(_pad(""))
        lines.append(_pad("Possible reasons:"))
        lines.append(_pad("- API rate limit exceeded"))
        lines.append(_pad("- Callsign has no recent"))
        lines.append(_pad("  activity (last 24h)"))
        lines.append(_pad("- Temporary API issue"))
        lines.append(_pad(""))
        lines.append(_pad("Check pskreporter.info"))
        lines.append(_pad("for live data"))
    
    lines.append(_pad(""))
    lines.append(_pad("Source: PSK Reporter"))
    lines.append(_pad("(pskreporter.info)"))
    
    return lines[:PAGE_HEIGHT]


def main() -> None:
    """Update page 700 with callsign information."""
    root = Path(__file__).resolve().parent.parent
    pages_dir = root / "pages"
    page_file = pages_dir / "700.json"
    
    # Get callsign from config
    callsign = get_callsign_from_config()
    
    if not callsign:
        # Create a placeholder page if no callsign is set
        content = [
            _pad("CALLSIGN INFORMATION"),
            _pad(""),
            _pad("-" * PAGE_WIDTH),
            _pad(""),
            _pad("No callsign configured."),
            _pad(""),
            _pad("Set your callsign in the"),
            _pad("update process to see"),
            _pad("PSK Reporter data here."),
            _pad(""),
            _pad("Source: PSK Reporter"),
        ]
        print(f"Updated {page_file} with callsign placeholder (no callsign set)")
    else:
        content = build_callsign_page(callsign)
        print(f"Updated {page_file} with callsign data for {callsign}")
    
    page = {
        "page": "700",
        "title": "Callsign Info",
        "timestamp": datetime.now().isoformat() + "Z",
        "subpage": 1,
        "content": content,
    }
    
    page_file.write_text(json.dumps(page, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

