"""
Update page 304 with Premier League fixtures and results from BBC Sport.
Scrapes https://www.bbc.co.uk/sport/football/scores-fixtures for Premier League data only.
"""
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict

import requests
from bs4 import BeautifulSoup

from .compiler import PAGE_WIDTH, PAGE_HEIGHT


def _pad(text: str) -> str:
    txt = text[:PAGE_WIDTH]
    return txt.ljust(PAGE_WIDTH)


PL_TEAMS: List[str] = [
    "Arsenal",
    "Aston Villa",
    "Bournemouth",
    "Burnley",
    "Brentford",
    "Brighton & Hove Albion",
    "Chelsea",
    "Crystal Palace",
    "Everton",
    "Fulham",
    "Ipswich Town",
    "Leicester City",
    "Liverpool",
    "Manchester City",
    "Manchester United",
    "Newcastle United",
    "Nottingham Forest",
    "Southampton",
    "Tottenham Hotspur",
    "West Ham United",
    "Wolverhampton Wanderers",
]


def fetch_premier_league_data() -> Dict:
    """
    Fetch Premier League fixtures and results from BBC Sport scores-fixtures page.
    Returns dict with 'scores' (completed matches) and 'fixtures' (upcoming matches).
    """
    scores: List[str] = []
    fixtures: List[str] = []

    try:
        url = "https://www.bbc.co.uk/sport/football/scores-fixtures"
        resp = requests.get(
            url,
            timeout=15,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            },
        )
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # BBC’s accessibility text is often easier to parse than visual HTML.
        # Strategy:
        # - Pull plain text from the whole page.
        # - Slice from "Premier League" to the next league heading.
        page_text = soup.get_text(separator="\n", strip=True)

        start_match = re.search(r"\bPremier League\b", page_text, flags=re.I)
        if not start_match:
            return {"scores": [], "fixtures": [], "error": "Premier League section not found"}

        # Find the earliest "next league" heading after Premier League.
        next_headings = [
            "Scottish Premiership",
            "Championship",
            "Women's Super League",
            "League One",
            "League Two",
            "Women's FA Cup",
        ]
        end_idx = None
        for h in next_headings:
            m = re.search(rf"\b{re.escape(h)}\b", page_text[start_match.end() :], flags=re.I)
            if m:
                cand = start_match.end() + m.start()
                if end_idx is None or cand < end_idx:
                    end_idx = cand

        pl_block = page_text[start_match.start() : end_idx].replace("\n", " ")
        pl_block = re.sub(r"\s+", " ", pl_block).strip()

        def _norm(s: str) -> str:
            return re.sub(r"\s+", " ", s).strip()

        def _fmt_score(team1: str, s1: str, s2: str, team2: str) -> str:
            score_str = f"{s1}-{s2}"
            return f"{team1[-18:]:18} {score_str:>6} {team2[:18]:<18}"[:PAGE_WIDTH]

        def _fmt_fixture(time_str: str, team1: str, team2: str) -> str:
            return f"{time_str:>5}  {team1[-18:]} v {team2[:18]}"[:PAGE_WIDTH]

        def _extract_teams_from_block(text: str) -> List[str]:
            """
            Option A: automatically derive the team list from the Premier League
            block itself, so we don't need to keep PL_TEAMS updated manually.
            """
            teams: List[str] = []
            seen = set()

            def add(name: str) -> None:
                name = _norm(name)
                # Reject very short/obviously-not-team strings
                if len(name) < 3:
                    return
                key = name.lower()
                if key in seen:
                    return
                seen.add(key)
                teams.append(name)

            # Completed matches often look like:
            #   "Chelsea 2 , Everton 0 at Full time"
            completed_loose = re.compile(
                r"(?P<t1>[A-Za-z0-9&.' -]{3,50}?)\s+"
                r"(?P<s1>\d{1,2})\s*,\s*"
                r"(?P<t2>[A-Za-z0-9&.' -]{3,50}?)\s+"
                r"(?P<s2>\d{1,2})\s+"
                r"(?:at\s+Full\s+time|Full\s+timeFT|Full\s+time)\b",
                flags=re.I,
            )
            for m in completed_loose.finditer(text):
                add(m.group("t1"))
                add(m.group("t2"))

            # Some pages surface a dash version:
            #   "Burnley 2-3 Fulham at Full time"
            completed_dash_loose = re.compile(
                r"(?P<t1>[A-Za-z0-9&.' -]{3,50}?)\s+"
                r"(?P<s1>\d{1,2})\s*[-–]\s*(?P<s2>\d{1,2})\s+"
                r"(?P<t2>[A-Za-z0-9&.' -]{3,50}?)\s+"
                r"(?:at\s+Full\s+time|Full\s+timeFT|Full\s+time)\b",
                flags=re.I,
            )
            for m in completed_dash_loose.finditer(text):
                add(m.group("t1"))
                add(m.group("t2"))

            # Fixtures sometimes show up as:
            #   "19:45 Chelsea v Everton"
            fixture_loose = re.compile(
                r"\b(?P<time>\d{1,2}:\d{2})\b\s+"
                r"(?P<t1>[A-Za-z0-9&.' -]{3,50}?)\s+v\s+"
                r"(?P<t2>[A-Za-z0-9&.' -]{3,50}?)\b",
                flags=re.I,
            )
            for m in fixture_loose.finditer(text):
                add(m.group("t1"))
                add(m.group("t2"))

            return teams

        derived_teams = _extract_teams_from_block(pl_block)
        # If extraction fails (BBC format change etc.), fall back to the last-known list.
        teams_for_regex = derived_teams if len(derived_teams) >= 10 else PL_TEAMS

        # Build a team-regex so we capture only these teams (avoid stray text).
        team_by_lower = {t.lower(): t for t in teams_for_regex}
        team_alt = "|".join(re.escape(t) for t in sorted(teams_for_regex, key=len, reverse=True))

        # Completed matches in BBC accessibility text typically look like:
        # "Chelsea 2 , Everton 0 at Full time"
        completed_re = re.compile(
            rf"(?P<t1>{team_alt})\s+(?P<s1>\d{{1,2}})\s*,\s*(?P<t2>{team_alt})\s+(?P<s2>\d{{1,2}})\s+"
            r"(?:at\s+Full\s+time|Full\s+timeFT|Full\s+time)\b",
            flags=re.I,
        )
        for m in completed_re.finditer(pl_block):
            t1 = team_by_lower.get(m.group("t1").lower(), m.group("t1"))
            t2 = team_by_lower.get(m.group("t2").lower(), m.group("t2"))
            line = _fmt_score(t1, m.group("s1"), m.group("s2"), t2)
            if line not in scores:
                scores.append(line)

        # Some pages occasionally surface a dash version in text (defensive):
        completed_dash_re = re.compile(
            rf"(?P<t1>{team_alt})\s+(?P<s1>\d{{1,2}})\s*[-–]\s*(?P<s2>\d{{1,2}})\s+(?P<t2>{team_alt})\s+"
            r"(?:at\s+Full\s+time|Full\s+timeFT|Full\s+time)\b",
            flags=re.I,
        )
        for m in completed_dash_re.finditer(pl_block):
            t1 = team_by_lower.get(m.group("t1").lower(), m.group("t1"))
            t2 = team_by_lower.get(m.group("t2").lower(), m.group("t2"))
            line = _fmt_score(t1, m.group("s1"), m.group("s2"), t2)
            if line not in scores:
                scores.append(line)

        # Fixtures: use time token + whitelist teams nearby.
        time_token_re = re.compile(r"\b(\d{1,2}:\d{2})\b")
        for tm in time_token_re.finditer(pl_block):
            time_str = tm.group(1)
            start = max(0, tm.start() - 120)
            end = min(len(pl_block), tm.end() + 120)
            frag = _norm(pl_block[start:end])
            if not re.search(r"\b(versus|kick off|plays| v )\b", frag, flags=re.I):
                continue

            teams_here = re.findall(rf"({team_alt})", frag, flags=re.I)
            canon = []
            for t in teams_here:
                c = team_by_lower.get(t.lower(), t)
                if c not in canon:
                    canon.append(c)
            if len(canon) >= 2:
                line = _fmt_fixture(time_str, canon[0], canon[1])
                if line not in fixtures:
                    fixtures.append(line)

        return {"scores": scores[:10], "fixtures": fixtures[:10]}

    except requests.RequestException as e:
        return {"scores": [], "fixtures": [], "error": f"Network error: {str(e)}"}
    except Exception as e:  # noqa: BLE001
        return {"scores": [], "fixtures": [], "error": str(e)}


def build_fixtures_page() -> List[str]:
    """Build Premier League fixtures and results page."""
    def _center(text: str) -> str:
        # Center a single line within the fixed page width.
        t = (text or "")[:PAGE_WIDTH]
        return t.center(PAGE_WIDTH)

    def _center_compact(line: str) -> str:
        """
        Compact and center common fixture/score formats.

        - Scores typically arrive as: "Chelsea               2-0 Everton"
        - Fixtures often as:         "19:45  Chelsea v Everton"
        """
        s = (line or "").strip()
        if not s:
            return _pad("")

        # Compact score line into a fixed score "column" centered on screen:
        #   <team1 right-aligned> <score centered> <team2 left-aligned>
        m = re.match(r"^(?P<t1>.+?)\s+(?P<score>\d{1,2}\s*[-–]\s*\d{1,2})\s+(?P<t2>.+)$", s)
        if m:
            t1 = m.group("t1").strip()
            score = re.sub(r"\s+", "", m.group("score")).replace("–", "-")
            t2 = m.group("t2").strip()
            score_width = 5  # fits e.g. "2-0", "10-0"
            gap = 2  # one space each side of score
            left_width = max(1, (PAGE_WIDTH - score_width - gap) // 2)
            right_width = max(1, PAGE_WIDTH - score_width - gap - left_width)

            t1_disp = t1[-left_width:]  # keep the end (team suffix) if too long
            t2_disp = t2[:right_width]

            formatted = f"{t1_disp:>{left_width}} {score:^{score_width}} {t2_disp:<{right_width}}"
            return formatted[:PAGE_WIDTH]

        # Otherwise just normalize whitespace and center.
        s = re.sub(r"\s+", " ", s)
        return _center(s)

    lines: List[str] = []
    lines.append(_pad("PREMIER LEAGUE"))
    lines.append(_pad("FIXTURES & RESULTS"))
    lines.append(_pad(""))
    
    data = fetch_premier_league_data()
    sep = _pad("-" * PAGE_WIDTH)
    
    # Today's Scores (completed matches) - always show this section
    lines.append(_pad("TODAY'S SCORES"))
    lines.append(sep)
    
    scores = data.get("scores", [])
    if scores:
        for score in scores:
            lines.append(_pad(_center_compact(score)))
    elif data.get("error"):
        lines.append(_pad("Error: Could not fetch scores"))
        lines.append(_pad(f"Reason: {data['error'][:PAGE_WIDTH-10]}"))
    else:
        lines.append(_pad("No matches played today"))
    
    lines.append(_pad(""))
    
    # Today's Fixtures (upcoming matches) - always show this section
    lines.append(_pad("TODAY'S FIXTURES"))
    lines.append(sep)
    
    fixtures = data.get("fixtures", [])
    if fixtures:
        for fixture in fixtures:
            lines.append(_pad(_center_compact(fixture)))
    elif data.get("error"):
        lines.append(_pad("Error: Could not fetch fixtures"))
        lines.append(_pad(f"Reason: {data['error'][:PAGE_WIDTH-10]}"))
    else:
        lines.append(_pad(_center("No fixtures scheduled")))
    
    lines.append(_pad(""))
    lines.append(_pad("Source: BBC Sport"))
    
    return lines[:PAGE_HEIGHT]


def main() -> None:
    """Update page 304 with fixtures and results."""
    root = Path(__file__).resolve().parent.parent
    pages_dir = root / "pages"
    page_file = pages_dir / "304.json"
    
    content = build_fixtures_page()
    
    page = {
        "page": "304",
        "title": "Fixtures & Results",
        "timestamp": datetime.now().isoformat() + "Z",
        "subpage": 1,
        "content": content,
    }
    
    page_file.write_text(json.dumps(page, indent=2), encoding="utf-8")
    print(f"Updated {page_file} with fixtures and results")


if __name__ == "__main__":
    main()

