"""
Update page 602 with daily quiz question from API.
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


def fetch_quiz_question() -> Dict:
    """
    Fetch a random quiz question from Open Trivia Database.
    """
    try:
        url = "https://opentdb.com/api.php?amount=1&type=multiple"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("response_code") == 0 and data.get("results"):
            question_data = data["results"][0]
            question = question_data.get("question", "")
            # Decode HTML entities
            import html
            question = html.unescape(question)
            correct_answer = html.unescape(question_data.get("correct_answer", ""))
            incorrect_answers = [html.unescape(ans) for ans in question_data.get("incorrect_answers", [])]
            
            # Combine all answers and shuffle
            all_answers = [correct_answer] + incorrect_answers
            import random
            random.shuffle(all_answers)
            
            # Map to letters
            answer_map = {}
            for i, ans in enumerate(all_answers):
                letter = chr(65 + i)  # A, B, C, D
                answer_map[letter] = ans
                if ans == correct_answer:
                    correct_letter = letter
            
            return {
                "question": question,
                "answers": answer_map,
                "correct": correct_letter,
                "explanation": f"The answer is {correct_letter}) {correct_answer}"
            }
        else:
            raise ValueError("API returned invalid response code or no results")
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"Failed to fetch quiz question from API: {str(e)}")


def build_quiz_page() -> List[str]:
    """Build daily quiz page."""
    lines: List[str] = []
    lines.append(_pad("DAILY QUIZ"))
    lines.append(_pad(""))
    lines.append(_pad("QUESTION OF THE DAY"))
    sep = _pad("-" * PAGE_WIDTH)
    lines.append(sep)
    lines.append(_pad(""))
    
    try:
        quiz = fetch_quiz_question()
        
        # Word wrap question
        question = quiz.get("question", "")
        words = question.split()
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
        
        # Show answers
        answers = quiz.get("answers", {})
        for letter in sorted(answers.keys()):
            answer_text = f"{letter}) {answers[letter]}"
            lines.append(_pad(answer_text))
        
        lines.append(_pad(""))
        lines.append(_pad("ANSWER"))
        lines.append(sep)
        lines.append(_pad(""))
        
        explanation = quiz.get("explanation", "")
        # Word wrap explanation
        words = explanation.split()
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
        lines.append(_pad("Source: Open Trivia Database"))
    except Exception as e:  # noqa: BLE001
        lines.append(_pad("Error: Could not fetch quiz"))
        lines.append(_pad("question"))
        lines.append(_pad(""))
        error_msg = str(e)[:PAGE_WIDTH]
        lines.append(_pad(error_msg))
        lines.append(_pad(""))
        lines.append(_pad("Open Trivia Database may be"))
        lines.append(_pad("temporarily unavailable."))
    
    return lines[:PAGE_HEIGHT]


def main() -> None:
    """Update page 602 with daily quiz."""
    root = Path(__file__).resolve().parent.parent
    pages_dir = root / "pages"
    page_file = pages_dir / "602.json"
    
    content = build_quiz_page()
    
    page = {
        "page": "602",
        "title": "Daily Quiz",
        "timestamp": datetime.now().isoformat() + "Z",
        "subpage": 1,
        "content": content,
    }
    
    page_file.write_text(json.dumps(page, indent=2), encoding="utf-8")
    print(f"Updated {page_file} with daily quiz")


if __name__ == "__main__":
    main()

