"""
Update page 504 with film picks from public sources.

Uses web scraping from IMDb and other public sources (no API key required).
"""
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

from .compiler import PAGE_WIDTH, PAGE_HEIGHT


def _pad(text: str) -> str:
    txt = text[:PAGE_WIDTH]
    return txt.ljust(PAGE_WIDTH)


def fetch_imdb_popular() -> List[Dict]:
    """Fetch popular films from IMDb's popular movies page."""
    try:
        url = "https://www.imdb.com/chart/moviemeter"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.content, "html.parser")
        films = []
        seen_titles = set()
        
        # Find movie titles in the chart
        title_elements = soup.find_all("h3", class_="ipc-title__text")
        for elem in title_elements[:15]:  # Get more to filter
            title_text = elem.get_text(strip=True)
            # Extract title (remove ranking number if present)
            title = re.sub(r'^\d+\.\s*', '', title_text)
            # Clean up extra text
            title = re.sub(r'\s*(United Kingdom|Sele|More).*$', '', title, flags=re.I)
            title = re.sub(r'\s+', ' ', title).strip()
            
            if title and len(title) > 1 and title not in seen_titles and len(title) < 50:
                seen_titles.add(title)
                films.append({"title": title, "rating": 0})
                if len(films) >= 5:
                    break
        
        return films
    except Exception:  # noqa: BLE001
        return []


def fetch_imdb_box_office() -> List[Dict]:
    """Fetch current box office films from IMDb."""
    try:
        url = "https://www.imdb.com/chart/boxoffice"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.content, "html.parser")
        films = []
        seen_titles = set()
        
        # Find box office titles
        title_elements = soup.find_all("h3", class_="ipc-title__text")
        for elem in title_elements[:10]:
            title_text = elem.get_text(strip=True)
            title = re.sub(r'^\d+\.\s*', '', title_text)
            # Clean up extra text
            title = re.sub(r'\s*(United Kingdom|Sele|More).*$', '', title, flags=re.I)
            title = re.sub(r'\s+', ' ', title).strip()
            
            if title and len(title) > 1 and title not in seen_titles and len(title) < 50:
                seen_titles.add(title)
                films.append({"title": title, "rating": 0})
                if len(films) >= 3:
                    break
        
        return films
    except Exception:  # noqa: BLE001
        return []


def fetch_imdb_coming_soon() -> List[Dict]:
    """Fetch upcoming films from IMDb."""
    try:
        url = "https://www.imdb.com/movies-coming-soon"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.content, "html.parser")
        films = []
        seen_titles = set()
        
        # Try multiple selectors for movie titles
        # Look for links with movie titles
        movie_links = soup.find_all("a", href=re.compile(r"/title/tt"))
        for link in movie_links[:20]:
            title_text = link.get_text(strip=True)
            # Skip if it looks like a date or other metadata
            if (title_text and 
                len(title_text) > 3 and 
                len(title_text) < 50 and
                not re.match(r'^\d{1,2}\s+\w+\s+\d{4}', title_text) and  # Not a date
                not title_text.lower() in ('more', 'select', 'upcoming', 'release', 'united kingdom') and
                title_text not in seen_titles):
                seen_titles.add(title_text)
                films.append({"title": title_text, "rating": 0, "release_date": ""})
                if len(films) >= 3:
                    break
        
        # Fallback to h3 elements if we didn't get enough
        if len(films) < 3:
            title_elements = soup.find_all("h3", class_="ipc-title__text")
            for elem in title_elements:
                title_text = elem.get_text(strip=True)
                title = re.sub(r'^\d+\.\s*', '', title_text)
                title = re.sub(r'\s*(United Kingdom|Sele|More|Upcoming|Release).*$', '', title, flags=re.I)
                title = re.sub(r'\s+', ' ', title).strip()
                
                if (title and len(title) > 3 and 
                    title not in seen_titles and
                    not re.match(r'^\d{1,2}\s+\w+\s+\d{4}', title) and
                    len(title) < 50):
                    seen_titles.add(title)
                    films.append({"title": title, "rating": 0, "release_date": ""})
                    if len(films) >= 3:
                        break
        
        return films[:3]
    except Exception:  # noqa: BLE001
        return []


def fetch_popular_films(limit: int = 5) -> List[Dict]:
    """Fetch popular films from IMDb."""
    return fetch_imdb_popular()[:limit]


def fetch_now_playing(limit: int = 3) -> List[Dict]:
    """Fetch films currently in cinemas (box office)."""
    return fetch_imdb_box_office()[:limit]


def fetch_upcoming(limit: int = 3) -> List[Dict]:
    """Fetch upcoming film releases."""
    return fetch_imdb_coming_soon()[:limit]


def format_rating(vote_average: float) -> str:
    """Convert rating (0-10) to star display (★★★★☆)."""
    stars = int(vote_average / 2)  # Convert 0-10 to 0-5 stars
    full_stars = min(stars, 5)
    return "★" * full_stars + "☆" * (5 - full_stars)


def build_film_picks_page() -> List[str]:
    """Build film picks page."""
    lines: List[str] = []
    lines.append(_pad("FILM PICKS"))
    lines.append(_pad(""))
    
    # Now showing in cinemas
    lines.append(_pad("NOW SHOWING"))
    sep = _pad("-" * PAGE_WIDTH)
    lines.append(sep)
    
    now_playing = fetch_now_playing(limit=3)
    
    if now_playing:
        cinema_num = 1
        for film in now_playing:
            title = film.get("title", "Unknown")[:35]
            lines.append(_pad(f"Cinema {cinema_num}:  {title}"))
            cinema_num += 1
    else:
        lines.append(_pad("Error: Could not fetch now"))
        lines.append(_pad("showing films"))
        lines.append(_pad(""))
        lines.append(_pad("IMDb may be temporarily"))
        lines.append(_pad("unavailable."))
    
    lines.append(_pad(""))
    
    # This week's picks (popular films)
    lines.append(_pad("THIS WEEK'S PICKS"))
    lines.append(sep)
    
    popular = fetch_popular_films(limit=3)
    
    if popular:
        for film in popular:
            title = film.get("title", "Unknown")[:30]
            rating = film.get("vote_average", 0)
            stars = format_rating(rating)
            lines.append(_pad(f"{stars}  {title}"))
    else:
        lines.append(_pad("Error: Could not fetch popular"))
        lines.append(_pad("films"))
        lines.append(_pad(""))
        lines.append(_pad("IMDb may be temporarily"))
        lines.append(_pad("unavailable."))
    
    lines.append(_pad(""))
    
    # Coming soon
    lines.append(_pad("COMING SOON"))
    lines.append(sep)
    
    upcoming = fetch_upcoming(limit=2)
    
    if upcoming:
        for film in upcoming:
            title = film.get("title", "Unknown")[:35]
            release_date = film.get("release_date", "")
            if release_date:
                try:
                    release_dt = datetime.strptime(release_date, "%Y-%m-%d")
                    day_name = release_dt.strftime("%a")
                    lines.append(_pad(f"Next {day_name}:  {title}"))
                except (ValueError, AttributeError):
                    lines.append(_pad(f"Coming soon:  {title}"))
            else:
                lines.append(_pad(f"Coming soon:  {title}"))
    else:
        lines.append(_pad("Error: Could not fetch upcoming"))
        lines.append(_pad("films"))
        lines.append(_pad(""))
        lines.append(_pad("IMDb may be temporarily"))
        lines.append(_pad("unavailable."))
    
    lines.append(_pad(""))
    lines.append(_pad("RATINGS"))
    lines.append(sep)
    lines.append(_pad("All films rated by critics"))
    lines.append(_pad("and audience reviews"))
    lines.append(_pad(""))
    
    lines.append(_pad("Source: IMDb (live data)"))
    
    return lines[:PAGE_HEIGHT]


def main() -> None:
    """Update page 504 with film picks."""
    root = Path(__file__).resolve().parent.parent
    pages_dir = root / "pages"
    page_file = pages_dir / "504.json"
    
    content = build_film_picks_page()
    
    page = {
        "page": "504",
        "title": "Film Picks",
        "timestamp": datetime.now().isoformat() + "Z",
        "subpage": 1,
        "content": content,
    }
    
    page_file.write_text(json.dumps(page, indent=2), encoding="utf-8")
    
    # Check if we got live data
    now_playing = fetch_now_playing()
    popular = fetch_popular_films()
    upcoming = fetch_upcoming()
    
    if now_playing or popular or upcoming:
        print(f"Updated {page_file} with film picks from IMDb")
        if now_playing:
            print(f"  Now showing: {len(now_playing)} films")
        if popular:
            print(f"  Popular: {len(popular)} films")
        if upcoming:
            print(f"  Coming soon: {len(upcoming)} films")
    else:
        print(f"Updated {page_file} with error message (no data available)")


if __name__ == "__main__":
    main()

