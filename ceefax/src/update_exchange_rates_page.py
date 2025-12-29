"""
Update page 400 with exchange rates from exchangerate-api.com (free tier).
"""
import json
from pathlib import Path
from typing import List, Dict

import requests

from .compiler import PAGE_WIDTH, PAGE_HEIGHT


# Using exchangerate-api.com free tier (no API key needed for base USD)
EXCHANGE_API = "https://api.exchangerate-api.com/v4/latest/GBP"


def _pad(text: str) -> str:
    txt = text[:PAGE_WIDTH]
    return txt.ljust(PAGE_WIDTH)


def fetch_exchange_rates() -> Dict[str, float]:
    """Fetch current exchange rates for GBP."""
    try:
        resp = requests.get(EXCHANGE_API, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("rates", {})
    except Exception:  # noqa: BLE001
        return {}


def build_exchange_rates_page() -> List[str]:
    lines: List[str] = []
    lines.append(_pad("EXCHANGE RATES"))

    try:
        rates = fetch_exchange_rates()
    except Exception as exc:  # noqa: BLE001
        lines.append(_pad("Error fetching rates:"))
        lines.append(_pad(str(exc)[: PAGE_WIDTH]))
        return lines[:PAGE_HEIGHT]

    lines.append(_pad(""))
    lines.append(_pad("GBP (British Pound)"))
    sep = _pad("-" * PAGE_WIDTH)
    lines.append(sep)

    # Major currencies
    major_currencies = {
        "USD": "$",
        "EUR": "€",
        "JPY": "¥",
        "CHF": "Fr",
        "CAD": "$",
        "AUD": "$",
    }

    for code, symbol in major_currencies.items():
        if code in rates:
            rate = rates[code]
            if code == "JPY":
                # JPY is typically shown with more precision
                rate_str = f"{rate:.2f}"
            else:
                rate_str = f"{rate:.2f}"
            lines.append(_pad(f"{code:3}  {symbol}{rate_str}"))

    lines.append(_pad(""))
    lines.append(_pad("MAJOR CURRENCIES"))
    lines.append(sep)

    # Cross rates
    if "USD" in rates and "EUR" in rates:
        eur_usd = rates["EUR"] / rates["USD"] if rates["USD"] != 0 else 0
        lines.append(_pad(f"EUR/USD  ${eur_usd:.2f}"))

    if "USD" in rates and "JPY" in rates:
        usd_jpy = rates["JPY"] / rates["USD"] if rates["USD"] != 0 else 0
        lines.append(_pad(f"USD/JPY  ¥{usd_jpy:.2f}"))

    if "EUR" in rates:
        lines.append(_pad(f"GBP/EUR  €{rates['EUR']:.2f}"))

    lines.append(_pad(""))
    lines.append(_pad("Last updated: Live rates"))
    lines.append(_pad("Source: Exchange Rate API"))

    return lines[:PAGE_HEIGHT]


def main() -> None:
    """Update page 400 with latest exchange rates."""
    root = Path(__file__).resolve().parent.parent
    pages_dir = root / "pages"
    page_file = pages_dir / "400.json"

    content = build_exchange_rates_page()

    page = {
        "page": "400",
        "title": "Exchange Rates",
        "timestamp": "From API (live)",
        "subpage": 1,
        "content": content,
    }

    page_file.write_text(json.dumps(page, indent=2), encoding="utf-8")
    print(f"Updated {page_file} with latest exchange rates")


if __name__ == "__main__":
    main()

