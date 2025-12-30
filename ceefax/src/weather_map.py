import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from .compiler import PAGE_WIDTH


WTTR_URL = "https://wttr.in/{location}?format=j1"
_WTTR_CACHE_TTL_S = 10 * 60  # 10 minutes
_WTTR_CACHE_LOCK = threading.Lock()
_WTTR_CACHE_MEM: Dict[str, Dict[str, Any]] = {}


def _cache_path() -> Path:
    # ceefax/src -> ceefax/
    ceefax_root = Path(__file__).resolve().parent.parent
    d = ceefax_root / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d / "wttr_cache.json"


def _load_cache_from_disk() -> None:
    """
    Best-effort load of disk cache into memory.

    Cache format:
      { "<location>": { "ts": <epoch_seconds>, "data": <wttr_json> }, ... }
    """
    p = _cache_path()
    if not p.exists():
        return
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return
        with _WTTR_CACHE_LOCK:
            for k, v in raw.items():
                if isinstance(k, str) and isinstance(v, dict) and "data" in v and "ts" in v:
                    _WTTR_CACHE_MEM[k] = v
    except Exception:  # noqa: BLE001
        return


def _save_cache_to_disk() -> None:
    """
    Best-effort write of memory cache to disk.
    """
    p = _cache_path()
    try:
        with _WTTR_CACHE_LOCK:
            # Keep disk file reasonably small by only persisting recent entries.
            now = time.time()
            pruned: Dict[str, Dict[str, Any]] = {}
            for k, v in _WTTR_CACHE_MEM.items():
                ts = float(v.get("ts") or 0)
                if now - ts <= (_WTTR_CACHE_TTL_S * 2):
                    pruned[k] = v
        p.write_text(json.dumps(pruned, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        return


def _normalize_location(location: str) -> str:
    loc = (location or "").strip()
    # wttr.in prefers "UK" over "GB"
    if loc.endswith(",GB"):
        loc = loc[:-3] + ",UK"
    return loc


def _cache_get(location: str) -> tuple[Optional[dict], bool]:
    """
    Returns (data, fresh) where fresh indicates TTL validity.
    """
    key = _normalize_location(location)
    now = time.time()
    with _WTTR_CACHE_LOCK:
        v = _WTTR_CACHE_MEM.get(key)
    if not v:
        return None, False
    try:
        ts = float(v.get("ts") or 0)
        data = v.get("data")
        if not isinstance(data, dict):
            return None, False
        fresh = (now - ts) <= _WTTR_CACHE_TTL_S
        return data, fresh
    except Exception:  # noqa: BLE001
        return None, False


def _cache_set(location: str, data: dict) -> None:
    key = _normalize_location(location)
    with _WTTR_CACHE_LOCK:
        _WTTR_CACHE_MEM[key] = {"ts": time.time(), "data": data}


@dataclass
class WeatherSummary:
    location: str
    temp_c: str
    feels_like_c: str
    description: str
    wind_kph: str
    wind_dir: str
    icon: str
    today_max: str = "?"
    today_min: str = "?"
    today_desc: str = ""
    tonight_min: str = "?"
    tonight_desc: str = ""
    tomorrow_desc: str = ""


def _pick_icon(desc: str) -> str:
    """
    Map a free-text description from wttr.in to a simple Ceefax-style icon.
    """
    lower = desc.lower()
    if "sun" in lower or "clear" in lower:
        return "☀"
    if "rain" in lower or "shower" in lower or "drizzle" in lower:
        return "🌦"
    if "snow" in lower or "sleet" in lower:
        return "❄"
    if "storm" in lower or "thunder" in lower:
        return "⛈"
    if "fog" in lower or "mist" in lower or "haze" in lower:
        return "🌫"
    return "☁"  # default cloud


def fetch_wttr(location: str, max_retries: int = 3) -> WeatherSummary:
    """
    Fetch current weather and forecast for a location from wttr.in and normalise it.

    This uses the same JSON endpoint as the ceefax-weather Rust project:
    https://wttr.in/{location}?format=j1
    
    Args:
        location: Location query string (e.g., "London,UK" or "New York,US")
        max_retries: Maximum number of retry attempts (default: 3)
    
    Raises:
        Exception: If all retry attempts fail
    """
    # Normalize location format - wttr.in prefers "UK" over "GB"
    location = _normalize_location(location)

    # Load disk cache lazily the first time we run.
    if not _WTTR_CACHE_MEM:
        _load_cache_from_disk()

    cached, fresh = _cache_get(location)
    if cached is not None and fresh:
        data = cached
    else:
        data = None
    
    # URL-encode the location to handle spaces, commas, and special characters
    from urllib.parse import quote
    encoded_location = quote(location)
    url = WTTR_URL.format(location=encoded_location)
    
    if data is None:
        last_error = None
        for attempt in range(max_retries):
            try:
                resp = requests.get(
                    url,
                    timeout=6,  # lower timeout; we parallelize + retry
                    headers={"User-Agent": "CeefaxStation/1.0"},
                    allow_redirects=True,
                )
                resp.raise_for_status()
                data = resp.json()

                # Validate response has expected structure
                if "current_condition" not in data or not data["current_condition"]:
                    raise ValueError("Invalid response from wttr.in: missing current_condition")

                _cache_set(location, data)
                # Persist best-effort (don’t do this under lock)
                _save_cache_to_disk()
                break  # Success, exit retry loop
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    # Wait before retry (exponential backoff)
                    time.sleep(0.4 * (attempt + 1))
                else:
                    # If we have stale cache, use it as fallback rather than failing hard.
                    stale, _fresh = _cache_get(location)
                    if stale is not None:
                        data = stale
                        break
                    raise Exception(
                        f"Failed to fetch weather for '{location}' after {max_retries} attempts: {e}"
                    ) from e

    current = data["current_condition"][0]
    desc = current["weatherDesc"][0]["value"]
    
    # Get forecast data (today, tonight, tomorrow)
    weather = data.get("weather", [])
    today_max = "?"
    today_min = "?"
    today_desc = ""
    tonight_min = "?"
    tonight_desc = ""
    tomorrow_desc = ""
    
    if len(weather) > 0:
        today = weather[0]
        today_max = today.get("maxtempC", "?")
        today_min = today.get("mintempC", "?")
        # Get hourly data for today's description
        hourly = today.get("hourly", [])
        if len(hourly) > 0:
            # Use midday forecast for today's description
            midday_idx = min(3, len(hourly) - 1) if len(hourly) > 3 else 0
            today_desc = hourly[midday_idx].get("weatherDesc", [{}])[0].get("value", "")
            # Use evening forecast for tonight
            if len(hourly) > 5:
                tonight_desc = hourly[5].get("weatherDesc", [{}])[0].get("value", "")
                tonight_min = hourly[5].get("tempC", "?")
    
    if len(weather) > 1:
        tomorrow = weather[1]
        hourly = tomorrow.get("hourly", [])
        if len(hourly) > 0:
            # Use midday forecast for tomorrow's description
            midday_idx = min(3, len(hourly) - 1) if len(hourly) > 3 else 0
            tomorrow_desc = hourly[midday_idx].get("weatherDesc", [{}])[0].get("value", "")

    return WeatherSummary(
        location=location.title(),
        temp_c=current.get("temp_C", "?"),
        feels_like_c=current.get("FeelsLikeC", "?"),
        description=desc,
        wind_kph=current.get("windspeedKmph", "?"),
        wind_dir=current.get("winddir16Point", "?"),
        icon=_pick_icon(desc),
        today_max=today_max,
        today_min=today_min,
        today_desc=today_desc,
        tonight_min=tonight_min,
        tonight_desc=tonight_desc,
        tomorrow_desc=tomorrow_desc,
    )


def fetch_wttr_many(locations: List[str], *, max_workers: int = 6) -> Dict[str, WeatherSummary]:
    """
    Fetch many locations concurrently. Returns mapping {normalized_location: WeatherSummary}.

    This dramatically speeds up pages that need multiple locations (UK weather + map).
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Normalize + de-dup
    normed: List[str] = []
    seen: set[str] = set()
    for loc in locations:
        k = _normalize_location(loc)
        if k and k not in seen:
            seen.add(k)
            normed.append(k)

    out: Dict[str, WeatherSummary] = {}
    if not normed:
        return out

    workers = max(1, min(int(max_workers), len(normed)))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fetch_wttr, loc): loc for loc in normed}
        for fut in as_completed(futs):
            loc = futs[fut]
            try:
                out[loc] = fut.result()
            except Exception:  # noqa: BLE001
                # Caller decides how to handle missing entries.
                continue

    return out


def build_ceefax_panel(summary: WeatherSummary) -> List[str]:
    """
    Render a single-location weather panel as Ceefax-style text lines.

    These lines are sized to PAGE_WIDTH so they can be dropped straight
    into a page's 'content' array.
    """

    def pad(text: str) -> str:
        return text[:PAGE_WIDTH].ljust(PAGE_WIDTH)

    lines: List[str] = []
    lines.append(pad(f"{summary.location.upper()} WEATHER"))
    lines.append(pad(""))
    lines.append(
        pad(f"   {summary.icon}    {summary.description[: PAGE_WIDTH - 8]}")
    )
    lines.append(
        pad(f"Temp {summary.temp_c}C (feels {summary.feels_like_c}C)")
    )
    lines.append(
        pad(f"Wind {summary.wind_kph} km/h from {summary.wind_dir}")
    )
    lines.append(pad(""))
    lines.append(
        pad("Data source: wttr.in  (unofficial, may lag real MET data)")
    )

    return lines


def build_ceefax_panel_for(location: str) -> List[str]:
    """
    Convenience helper: fetch + render in one call.

    Example:

        from src.weather_map import build_ceefax_panel_for
        lines = build_ceefax_panel_for("Frome,UK")
        for l in lines:
            print(l)
    """
    summary = fetch_wttr(location)
    return build_ceefax_panel(summary)


