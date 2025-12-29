import json
from pathlib import Path

from .uk_weather_map import build_uk_weather_map


def main() -> None:
    """
    Generate a UK weather map and write it to pages/103.json.
    """
    root = Path(__file__).resolve().parent.parent
    pages_dir = root / "pages"
    page_file = pages_dir / "103.json"

    lines = build_uk_weather_map()

    page = {
        "page": "103",
        "title": "Weather Map",
        "timestamp": "From wttr.in (live)",
        "subpage": 1,
        "content": lines,
    }

    page_file.write_text(json.dumps(page, indent=2), encoding="utf-8")
    print(f"Updated {page_file} with UK weather map")


if __name__ == "__main__":
    main()


