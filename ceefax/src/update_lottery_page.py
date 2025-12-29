"""
Update page 402 with UK National Lottery results.

Fetches UK National Lottery and EuroMillions results by scraping
the official National Lottery website using Playwright for JavaScript rendering.
"""
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

# Try to import Playwright, but make it optional
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from .compiler import PAGE_WIDTH, PAGE_HEIGHT


def _pad(text: str) -> str:
    txt = text[:PAGE_WIDTH]
    return txt.ljust(PAGE_WIDTH)


def _cache_path() -> Path:
    root = Path(__file__).resolve().parent.parent
    cache_dir = root / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "lottery_results.json"


def _load_cached_results() -> Optional[Dict]:
    """
    Load cached lottery results, if present.

    Cache schema:
      {
        "schema": 1,
        "saved_at_iso": "...Z",
        "results": { ... same as fetch_lottery_results() ... }
      }
    """
    try:
        p = _cache_path()
        if not p.exists():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        if int(data.get("schema", 0)) != 1:
            return None
        res = data.get("results")
        return res if isinstance(res, dict) else None
    except Exception:  # noqa: BLE001
        return None


def _save_cached_results(results: Dict) -> None:
    try:
        p = _cache_path()
        payload = {
            "schema": 1,
            "saved_at_iso": datetime.utcnow().isoformat() + "Z",
            "results": results,
        }
        p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        return


def _is_cache_fresh(results: Dict, *, max_age_seconds: int) -> bool:
    """
    Simple freshness check to avoid re-scraping on every `update_all` run.

    If the cache file was saved recently, use it.
    """
    try:
        p = _cache_path()
        if not p.exists():
            return False
        age_s = (datetime.utcnow() - datetime.utcfromtimestamp(p.stat().st_mtime)).total_seconds()
        return age_s <= float(max_age_seconds)
    except Exception:  # noqa: BLE001
        return False


def fetch_national_lottery_with_playwright() -> Optional[Dict]:
    """
    Fetch UK National Lottery results using Playwright to render JavaScript.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return None
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Try the draw history page which might show results more clearly
            url = "https://www.national-lottery.co.uk/results/lotto/draw-history"
            page.goto(url, wait_until="networkidle", timeout=20000)
            
            # Wait for content to load
            # Keep this short; we rely on DOM content and fallback patterns below.
            page.wait_for_timeout(1500)
            
            # Try clicking "Latest Draw" or similar if it exists
            try:
                latest_link = page.query_selector('a:has-text("Latest"), a:has-text("View"), button:has-text("Latest")')
                if latest_link:
                    latest_link.click()
                    page.wait_for_timeout(3000)
            except Exception:
                pass
            
            result = {}
            numbers = []
            bonus = None
            draw_date = None
            
            # Try to extract data using JavaScript - look for data in window/global objects
            try:
                js_result = page.evaluate("""
                    () => {
                        // Try to find lottery data in various possible locations
                        // Look for data in window objects
                        if (window.__NEXT_DATA__) {
                            return window.__NEXT_DATA__;
                        }
                        if (window.__INITIAL_STATE__) {
                            return window.__INITIAL_STATE__;
                        }
                        if (window.lotteryData) {
                            return window.lotteryData;
                        }
                        
                        // Look for JSON-LD structured data
                        let jsonLd = document.querySelector('script[type="application/ld+json"]');
                        if (jsonLd) {
                            try {
                                return JSON.parse(jsonLd.textContent);
                            } catch(e) {}
                        }
                        
                        // Look for any script tags with lottery data
                        let scripts = Array.from(document.querySelectorAll('script'));
                        for (let script of scripts) {
                            let text = script.textContent || script.innerHTML;
                            if (text.includes('numbers') || text.includes('draw')) {
                                try {
                                    let match = text.match(/\\{[^}]*numbers[^}]*\\}/);
                                    if (match) {
                                        return JSON.parse(match[0]);
                                    }
                                } catch(e) {}
                            }
                        }
                        
                        return null;
                    }
                """)
                
                # If we found structured data, try to extract from it
                if js_result:
                    # Try to find numbers in the JSON structure
                    def find_numbers_in_dict(d, path=""):
                        """Recursively search for number arrays in dict/list structures."""
                        if isinstance(d, dict):
                            for key, value in d.items():
                                if 'number' in key.lower() and isinstance(value, list):
                                    nums = [int(n) for n in value if isinstance(n, (int, str)) and str(n).isdigit() and 1 <= int(n) <= 59]
                                    if len(nums) >= 6:
                                        return sorted(nums[:6])
                                found = find_numbers_in_dict(value, f"{path}.{key}")
                                if found:
                                    return found
                        elif isinstance(d, list):
                            for i, item in enumerate(d):
                                found = find_numbers_in_dict(item, f"{path}[{i}]")
                                if found:
                                    return found
                        return None
                    
                    found_numbers = find_numbers_in_dict(js_result)
                    if found_numbers:
                        numbers = found_numbers
            except Exception:
                pass
            
            # Get page text content as fallback
            page_text = page.inner_text("body")
            content = page.content()
            
            page.close()
            browser.close()
            
            # Method 1: Extract from visible text - look for "Ball numbers: XX - XX - XX - XX - XX - XX"
            # This is the format used on the draw history page
            ball_numbers_pattern = r'Ball numbers\s*([0-9\s\-]+)'
            ball_match = re.search(ball_numbers_pattern, page_text, re.I)
            if ball_match:
                ball_text = ball_match.group(1)
                # Extract numbers separated by " - " or spaces
                ball_nums = re.findall(r'\b([1-5]?[0-9])\b', ball_text)
                nums = [int(n) for n in ball_nums if 1 <= int(n) <= 59]
                if len(nums) >= 6:
                    numbers = sorted(nums[:6])
            
            # Look for bonus ball
            if not bonus:
                bonus_pattern = r'Bonus ball\s*(\d{1,2})'
                bonus_match = re.search(bonus_pattern, page_text, re.I)
                if bonus_match:
                    bonus_str = bonus_match.group(1)
                    if bonus_str.isdigit():
                        bonus_num = int(bonus_str)
                        if 1 <= bonus_num <= 59:
                            bonus = bonus_num
            
            # Look for date - format like "Sat 22 Nov 2025"
            if not draw_date:
                date_pattern = r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})'
                date_match = re.search(date_pattern, page_text)
                if date_match:
                    draw_date = date_match.group(0)
            
            # Fallback: Look for other number patterns if we didn't find the ball numbers format
            if not numbers:
                number_patterns = [
                    r'\b([1-5]?[0-9])\s*-\s*([1-5]?[0-9])\s*-\s*([1-5]?[0-9])\s*-\s*([1-5]?[0-9])\s*-\s*([1-5]?[0-9])\s*-\s*([1-5]?[0-9])\b',
                    r'\b([1-5]?[0-9])\s*[,]\s*([1-5]?[0-9])\s*[,]\s*([1-5]?[0-9])\s*[,]\s*([1-5]?[0-9])\s*[,]\s*([1-5]?[0-9])\s*[,]\s*([1-5]?[0-9])\b',
                    r'\b([1-5]?[0-9])\s+([1-5]?[0-9])\s+([1-5]?[0-9])\s+([1-5]?[0-9])\s+([1-5]?[0-9])\s+([1-5]?[0-9])\b',
                ]
                
                for pattern in number_patterns:
                    matches = re.findall(pattern, page_text)
                    for match in matches[:3]:  # Check first few matches
                        nums = [int(n) for n in match if n.isdigit() and 1 <= int(n) <= 59]
                        if len(nums) == 6 and all(1 <= n <= 59 for n in nums):
                            numbers = sorted(nums)
                            break
                    if numbers:
                        break
            
            # Method 2: Parse HTML with BeautifulSoup
            if not numbers:
                soup = BeautifulSoup(content, "html.parser")
                
                # Try to find all elements with numbers
                all_text = soup.get_text()
                # Look for number sequences in the text
                for pattern in number_patterns:
                    matches = re.findall(pattern, all_text)
                    for match in matches[:3]:
                        nums = [int(n) for n in match if n.isdigit() and 1 <= int(n) <= 59]
                        if len(nums) == 6 and all(1 <= n <= 59 for n in nums):
                            numbers = sorted(nums)
                            break
                    if numbers:
                        break
                
                # Look for bonus ball
                bonus_patterns = [
                    r'bonus[^0-9]*([1-5]?[0-9])\b',
                    r'bonus\s*ball[^0-9]*([1-5]?[0-9])\b',
                ]
                for pattern in bonus_patterns:
                    match = re.search(pattern, all_text, re.I)
                    if match:
                        bonus_str = match.group(1)
                        if bonus_str.isdigit():
                            bonus_num = int(bonus_str)
                            if 1 <= bonus_num <= 59:
                                bonus = bonus_num
                                break
                
                # Look for date
                date_patterns = [
                    r'(\d{1,2}[\s/]\d{1,2}[\s/]\d{2,4})',
                    r'(\d{1,2}\s+\w+\s+\d{4})',
                ]
                for pattern in date_patterns:
                    match = re.search(pattern, all_text)
                    if match:
                        draw_date = match.group(1)
                        break
            
            if numbers and len(numbers) == 6:
                result["numbers"] = numbers
                if bonus:
                    result["bonus_ball"] = bonus
                if draw_date:
                    result["draw_date"] = draw_date
                else:
                    result["draw_date"] = "Latest draw"
                return result
            
    except Exception as e:  # noqa: BLE001
        print(f"Error fetching National Lottery with Playwright: {e}")
    
    return None


def fetch_national_lottery() -> Optional[Dict]:
    """
    Fetch UK National Lottery (Lotto) results from official website.
    Uses Playwright if available, otherwise falls back to simple scraping.
    """
    # Try Playwright first (handles JavaScript)
    if PLAYWRIGHT_AVAILABLE:
        result = fetch_national_lottery_with_playwright()
        if result:
            return result
    
    # Fallback to simple scraping (may not work due to JavaScript)
    try:
        url = "https://www.national-lottery.co.uk/results/lotto"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.content, "html.parser")
        result = {}
        
        # Look for embedded JSON data in script tags
        script_tags = soup.find_all("script", type="application/json")
        for script in script_tags:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    draw_data = (data.get("draw") or data.get("latestDraw") or 
                               data.get("result") or data.get("drawData"))
                    if draw_data and isinstance(draw_data, dict):
                        numbers = draw_data.get("numbers") or draw_data.get("mainNumbers")
                        if numbers:
                            result["numbers"] = sorted([int(n) for n in numbers if str(n).isdigit()])[:6]
                        bonus = draw_data.get("bonus") or draw_data.get("bonusBall")
                        if bonus:
                            result["bonus_ball"] = int(bonus) if str(bonus).isdigit() else None
                        date = draw_data.get("date") or draw_data.get("drawDate")
                        if date:
                            result["draw_date"] = str(date)
            except (json.JSONDecodeError, ValueError, AttributeError):
                continue
        
        if result.get("numbers"):
            if not result.get("draw_date"):
                result["draw_date"] = "Latest draw"
            return result
            
    except Exception as e:  # noqa: BLE001
        pass
    
    return None


def fetch_euromillions_with_playwright() -> Optional[Dict]:
    """
    Fetch EuroMillions results using Playwright to render JavaScript.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return None
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Try the draw history page for EuroMillions
            url = "https://www.national-lottery.co.uk/results/euromillions/draw-history"
            page.goto(url, wait_until="networkidle", timeout=20000)
            
            # Wait for content to load
            page.wait_for_timeout(1500)
            
            page_text = page.inner_text("body")
            content = page.content()
            
            page.close()
            browser.close()
            
            result = {}
            numbers = []
            stars = []
            draw_date = None
            
            # Method 1: Extract from text - look for EuroMillions format
            # Main numbers (1-50) - format like "Ball numbers: XX - XX - XX - XX - XX"
            ball_numbers_pattern = r'Ball numbers\s*([0-9\s\-]+)'
            ball_match = re.search(ball_numbers_pattern, page_text, re.I)
            if ball_match:
                ball_text = ball_match.group(1)
                ball_nums = re.findall(r'\b([1-4]?[0-9]|50)\b', ball_text)
                nums = [int(n) for n in ball_nums if 1 <= int(n) <= 50]
                if len(nums) >= 5:
                    numbers = sorted(nums[:5])
            
            # Look for lucky stars (1-12) - format like "Lucky stars: XX - XX" or "Stars: XX - XX"
            if not stars:
                star_patterns = [
                    r'(?:Lucky stars?|Stars?)\s*([0-9\s\-]+)',
                    r'Stars?\s*([0-9\s\-]+)',
                ]
                for pattern in star_patterns:
                    star_match = re.search(pattern, page_text, re.I)
                    if star_match:
                        star_text = star_match.group(1)
                        star_nums = re.findall(r'\b([1-9]|1[0-2])\b', star_text)
                        nums = [int(s) for s in star_nums if 1 <= int(s) <= 12]
                        if nums:
                            stars = sorted(nums[:2])
                            break
            
            # Look for date
            if not draw_date:
                date_pattern = r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})'
                date_match = re.search(date_pattern, page_text)
                if date_match:
                    draw_date = date_match.group(0)
            
            # Fallback patterns if we didn't find the main format
            if not numbers:
                euro_patterns = [
                    r'\b([1-4]?[0-9]|50)\s*-\s*([1-4]?[0-9]|50)\s*-\s*([1-4]?[0-9]|50)\s*-\s*([1-4]?[0-9]|50)\s*-\s*([1-4]?[0-9]|50)\b',
                    r'\b([1-4]?[0-9]|50)\s*[,]\s*([1-4]?[0-9]|50)\s*[,]\s*([1-4]?[0-9]|50)\s*[,]\s*([1-4]?[0-9]|50)\s*[,]\s*([1-4]?[0-9]|50)\b',
                ]
                for pattern in euro_patterns:
                    matches = re.findall(pattern, page_text)
                    for match in matches[:3]:
                        nums = [int(n) for n in match if n.isdigit() and 1 <= int(n) <= 50]
                        if len(nums) == 5:
                            numbers = sorted(nums)
                            break
                    if numbers:
                        break
            
            if not stars:
                star_patterns = [
                    r'\b([1-9]|1[0-2])\s*-\s*([1-9]|1[0-2])\b',
                    r'\b([1-9]|1[0-2])\s*[,]\s*([1-9]|1[0-2])\b',
                ]
                for pattern in star_patterns:
                    matches = re.findall(pattern, page_text)
                    for match in matches[:3]:
                        if isinstance(match, tuple):
                            star_nums = [int(s) for s in match if str(s).isdigit() and 1 <= int(s) <= 12]
                        else:
                            star_nums = [int(match)] if str(match).isdigit() and 1 <= int(match) <= 12 else []
                        if star_nums:
                            stars = sorted(star_nums[:2])
                            break
                    if stars:
                        break
            
            # Method 2: Parse HTML
            if not numbers or not stars:
                soup = BeautifulSoup(content, "html.parser")
                all_text = soup.get_text()
                
                if not numbers:
                    for pattern in euro_patterns:
                        matches = re.findall(pattern, all_text)
                        for match in matches[:3]:
                            nums = [int(n) for n in match if n.isdigit() and 1 <= int(n) <= 50]
                            if len(nums) == 5:
                                numbers = sorted(nums)
                                break
                        if numbers:
                            break
                
                if not stars:
                    for pattern in star_patterns:
                        matches = re.findall(pattern, all_text, re.I)
                        for match in matches[:3]:
                            if isinstance(match, tuple):
                                star_nums = [int(s) for s in match if str(s).isdigit() and 1 <= int(s) <= 12]
                            else:
                                star_nums = [int(match)] if str(match).isdigit() and 1 <= int(match) <= 12 else []
                            if star_nums:
                                stars = sorted(star_nums[:2])
                                break
                        if stars:
                            break
                
                # Look for date
                date_patterns = [
                    r'(\d{1,2}[\s/]\d{1,2}[\s/]\d{2,4})',
                    r'(\d{1,2}\s+\w+\s+\d{4})',
                ]
                for pattern in date_patterns:
                    match = re.search(pattern, all_text)
                    if match:
                        draw_date = match.group(1)
                        break
            
            if numbers and len(numbers) == 5:
                result["numbers"] = numbers
                if stars:
                    result["lucky_stars"] = stars
                if draw_date:
                    result["draw_date"] = draw_date
                else:
                    result["draw_date"] = "Latest draw"
                return result
            
    except Exception as e:  # noqa: BLE001
        print(f"Error fetching EuroMillions with Playwright: {e}")
    
    return None


def fetch_euromillions() -> Optional[Dict]:
    """
    Fetch EuroMillions results from official website.
    Uses Playwright if available, otherwise falls back to simple scraping.
    """
    # Try Playwright first
    if PLAYWRIGHT_AVAILABLE:
        result = fetch_euromillions_with_playwright()
        if result:
            return result
    
    # Fallback to simple scraping
    try:
        url = "https://www.national-lottery.co.uk/results/euromillions"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.content, "html.parser")
        result = {}
        
        # Look for embedded JSON data
        script_tags = soup.find_all("script", type="application/json")
        for script in script_tags:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    draw_data = (data.get("draw") or data.get("latestDraw") or 
                               data.get("result") or data.get("drawData"))
                    if draw_data and isinstance(draw_data, dict):
                        numbers = draw_data.get("numbers") or draw_data.get("mainNumbers")
                        if numbers:
                            result["numbers"] = sorted([int(n) for n in numbers if str(n).isdigit() and 1 <= int(n) <= 50])[:5]
                        stars = draw_data.get("stars") or draw_data.get("luckyStars")
                        if stars:
                            result["lucky_stars"] = sorted([int(s) for s in stars if str(s).isdigit() and 1 <= int(s) <= 12])[:2]
                        date = draw_data.get("date") or draw_data.get("drawDate")
                        if date:
                            result["draw_date"] = str(date)
            except (json.JSONDecodeError, ValueError, AttributeError):
                continue
        
        if result.get("numbers"):
            if not result.get("draw_date"):
                result["draw_date"] = "Latest draw"
            return result
            
    except Exception as e:  # noqa: BLE001
        pass
    
    return None


def fetch_lottery_results() -> Optional[Dict]:
    """
    Fetch UK National Lottery and EuroMillions results.
    
    Returns a dictionary with 'national' and 'euromillions' keys.
    """
    # Fast path: use a recent cache (dramatically reduces update_all time).
    cached = _load_cached_results()
    if cached and _is_cache_fresh(cached, max_age_seconds=60 * 60):
        return cached

    result: Dict = {}

    nat_lottery = fetch_national_lottery()
    if nat_lottery:
        result["national"] = nat_lottery

    euro = fetch_euromillions()
    if euro:
        result["euromillions"] = euro

    if result:
        _save_cached_results(result)
        return result

    # If live fetch failed, fall back to last known good cache (even if stale).
    return cached if cached else None


def format_numbers(numbers: List[int], max_per_line: int = 6) -> List[str]:
    """Format lottery numbers for display."""
    lines = []
    current_line = []
    
    for num in numbers:
        current_line.append(f"{num:2d}")
        if len(current_line) >= max_per_line:
            lines.append("  ".join(current_line))
            current_line = []
    
    if current_line:
        lines.append("  ".join(current_line))
    
    return lines if lines else ["  No numbers"]


def build_lottery_page() -> List[str]:
    """Build lottery results page with live data or template."""
    lines: List[str] = []
    lines.append(_pad("LOTTERY RESULTS"))
    lines.append(_pad(""))
    
    # Try to fetch live data
    lottery_data = fetch_lottery_results()
    
    # National Lottery
    lines.append(_pad("NATIONAL LOTTERY"))
    sep = _pad("-" * PAGE_WIDTH)
    lines.append(sep)
    
    if lottery_data and "national" in lottery_data:
        nat_data = lottery_data["national"]
        draw_date = nat_data.get("draw_date", "Latest draw")
        numbers = nat_data.get("numbers", [])
        bonus = nat_data.get("bonus_ball", None)
        
        lines.append(_pad(f"Draw Date: {draw_date}"))
        lines.append(_pad(""))
        lines.append(_pad("Main Numbers:"))
        for num_line in format_numbers(numbers):
            lines.append(_pad(f"  {num_line}"))
        lines.append(_pad(""))
        if bonus:
            lines.append(_pad(f"Bonus Ball:  {bonus}"))
        else:
            lines.append(_pad("Bonus Ball:  -"))
    else:
        lines.append(_pad("Error: Could not fetch National"))
        lines.append(_pad("Lottery results"))
        lines.append(_pad(""))
        lines.append(_pad("Website may be temporarily"))
        lines.append(_pad("unavailable or structure"))
        lines.append(_pad("has changed."))
    
    lines.append(_pad(""))
    
    # EuroMillions
    lines.append(_pad("EUROMILLIONS"))
    lines.append(sep)
    
    if lottery_data and "euromillions" in lottery_data:
        euro_data = lottery_data["euromillions"]
        draw_date = euro_data.get("draw_date", "Latest draw")
        numbers = euro_data.get("numbers", [])
        stars = euro_data.get("lucky_stars", [])
        
        lines.append(_pad(f"Draw Date: {draw_date}"))
        lines.append(_pad(""))
        lines.append(_pad("Main Numbers:"))
        for num_line in format_numbers(numbers, max_per_line=5):
            lines.append(_pad(f"  {num_line}"))
        lines.append(_pad(""))
        if stars:
            stars_str = "  ".join(f"{s:2d}" for s in stars)
            lines.append(_pad(f"Lucky Stars:  {stars_str}"))
        else:
            lines.append(_pad("Lucky Stars:  -"))
    else:
        lines.append(_pad("Error: Could not fetch"))
        lines.append(_pad("EuroMillions results"))
        lines.append(_pad(""))
        lines.append(_pad("Website may be temporarily"))
        lines.append(_pad("unavailable or structure"))
        lines.append(_pad("has changed."))
    
    lines.append(_pad(""))
    lines.append(_pad("Next Draw: Check official website"))
    lines.append(_pad(""))
    
    if lottery_data:
        lines.append(_pad("Source: National Lottery (live)"))
    else:
        lines.append(_pad("Source: Error - API unavailable"))
        lines.append(_pad("Check: national-lottery.co.uk"))
    
    return lines[:PAGE_HEIGHT]


def main() -> None:
    """Update page 402 with lottery results."""
    root = Path(__file__).resolve().parent.parent
    pages_dir = root / "pages"
    page_file = pages_dir / "402.json"
    
    content = build_lottery_page()
    
    page = {
        "page": "402",
        "title": "Lottery Results",
        "timestamp": datetime.now().isoformat() + "Z",
        "subpage": 1,
        "content": content,
    }
    
    page_file.write_text(json.dumps(page, indent=2), encoding="utf-8")
    
    lottery_data = fetch_lottery_results()
    if lottery_data:
        print(f"Updated {page_file} with lottery results (live data)")
        if "national" in lottery_data:
            nums = lottery_data['national'].get('numbers', [])
            print(f"  National Lottery: {nums}")
        if "euromillions" in lottery_data:
            nums = lottery_data['euromillions'].get('numbers', [])
            stars = lottery_data['euromillions'].get('lucky_stars', [])
            print(f"  EuroMillions: {nums} Stars: {stars}")
    else:
        print(f"Updated {page_file} with lottery results template")
        if not PLAYWRIGHT_AVAILABLE:
            print("NOTE: Playwright not installed - cannot fetch live data")
            print("      Install with: pip install playwright")
            print("      Then run: playwright install chromium")
        else:
            print("NOTE: Could not fetch live lottery data")
            print("      The website structure may have changed")
            print("      or the page requires additional time to load")


if __name__ == "__main__":
    main()
