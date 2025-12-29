import json
import os
from dataclasses import dataclass
from typing import List


PAGE_WIDTH = 50
# Keep the frame small enough for a typical 80x24 terminal.
# (We reserve the very last row for the viewer status line.)
PAGE_HEIGHT = 23


@dataclass
class Page:
    page: str
    title: str
    timestamp: str
    subpage: int
    content: List[str]

    @property
    def page_id(self) -> str:
        if self.subpage and self.subpage != 1:
            return f"{self.page}.{self.subpage}"
        return self.page


def load_page_from_file(path: str) -> Page:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return Page(
        page=str(data.get("page", "000")),
        title=str(data.get("title", "")),
        timestamp=str(data.get("timestamp", "")),
        subpage=int(data.get("subpage", 1)),
        content=[str(line) for line in data.get("content", [])],
    )


def wrap_line(text: str, width: int) -> List[str]:
    lines: List[str] = []
    while text:
        lines.append(text[:width])
        text = text[width:]
    if not lines:
        lines.append("")
    return lines


def pad_or_trim(line: str, width: int) -> str:
    line = line[:width]
    return line.ljust(width)


def format_menu_like_line(text: str, width: int = PAGE_WIDTH) -> List[str]:
    """
    Optional helper to make menu-style lines look more like classic Ceefax.

    If a content line contains a single '|' separator, we treat it as:
        "LABEL TEXT | PAGE"
    and right-align the PAGE number at the right-hand side of the row.

    Example JSON line:
        "NEWS HEADLINES | 101"

    becomes something like:
        "NEWS HEADLINES................... 101"
    with the page number aligned.

    Two-column mode:
        If a content line contains '||', it is treated as:
            "LEFT CELL || RIGHT CELL"
        Each cell may optionally be "LABEL | PAGE". Cells are formatted into two
        equal-width columns with a fixed gap (Teletext-style).
    """
    def format_cell(cell_text: str, cell_width: int) -> str:
        cell_text = (cell_text or "").strip()
        if not cell_text:
            return " " * cell_width

        if "|" not in cell_text:
            return pad_or_trim(cell_text, cell_width)

        left, right = [p.strip() for p in cell_text.split("|", 1)]
        page_code = right[:3]
        page_width = 3
        label_width = max(0, cell_width - 1 - page_width)  # 1 space before page
        label = left[:label_width]
        # Teletext-y dotted leaders to the page number.
        dots = "." * max(0, label_width - len(label))
        return f"{label}{dots} {page_code.rjust(page_width)}"[:cell_width].ljust(cell_width)

    if "||" in text:
        left_raw, right_raw = (text.split("||", 1) + [""])[:2]
        gap = 2
        col_width = max(1, (width - gap) // 2)
        right_width = max(1, width - gap - col_width)
        left_col = format_cell(left_raw, col_width)
        right_col = format_cell(right_raw, right_width)
        return [left_col + (" " * gap) + right_col]

    if "|" not in text:
        return wrap_line(text, width)

    parts = [p.strip() for p in text.split("|")]
    if len(parts) != 2:
        # Fallback to normal wrapping if the format isn't exactly "label | page"
        return wrap_line(text, width)

    label, page_code = parts

    label_width = width - 3 - 3  # label + 3 spaces + 3-digit page
    page_width = 3

    label = label[:label_width]
    page_code = page_code[:page_width]

    formatted = f"{label.ljust(label_width)}   {page_code.rjust(page_width)}"
    return [formatted]


def compile_page_to_matrix(page: Page) -> List[str]:
    """
    Return a list of PAGE_HEIGHT strings, each PAGE_WIDTH chars.
    Row 0: title and page number.
    Row 1: timestamp.
    Rows 2..: content.
    """
    rows: List[str] = []

    # Row 0: title + page id
    header = f"{page.page_id} {page.title}"
    rows.append(pad_or_trim(header, PAGE_WIDTH))

    # Row 1: timestamp
    rows.append(pad_or_trim(page.timestamp, PAGE_WIDTH))

    def is_rule(line: str) -> bool:
        s = (line or "").strip()
        return bool(s) and set(s) == {"-"} and len(s) >= 10

    # Remove blank line(s) directly under horizontal rules ("-----") so content
    # shifts up consistently across pages.
    cleaned_content: List[str] = []
    i = 0
    while i < len(page.content):
        line = page.content[i]
        cleaned_content.append(line)
        if is_rule(line):
            j = i + 1
            while j < len(page.content) and not (page.content[j] or "").strip():
                j += 1
            i = j
            continue
        i += 1

    # Remove blank padding *before* content starts so pages don't render with
    # empty rows ahead of the first real line.
    # (Keep page 000 exempt because it intentionally uses leading blanks for layout.)
    if page.page != "000":
        while cleaned_content and not (cleaned_content[0] or "").strip():
            cleaned_content.pop(0)

    # Ensure pages are uniform: if a page has no rule line at all, inject one
    # just after the first non-empty content line (or at the top if empty).
    #
    # Exempt the start page (000) which intentionally has a custom layout/art.
    if page.page != "000" and not any(is_rule(x) for x in cleaned_content):
        injected = False
        for idx, ln in enumerate(cleaned_content):
            if (ln or "").strip():
                cleaned_content.insert(idx + 1, "-" * PAGE_WIDTH)
                injected = True
                break
        if not injected:
            cleaned_content.insert(0, "-" * PAGE_WIDTH)

    # Content rows
    content_rows: List[str] = []
    for original_line in cleaned_content:
        for wrapped in format_menu_like_line(original_line, PAGE_WIDTH):
            content_rows.append(pad_or_trim(wrapped, PAGE_WIDTH))

    # Fill up to PAGE_HEIGHT with content or blanks
    remaining_rows = PAGE_HEIGHT - len(rows)
    content_rows = content_rows[:remaining_rows]
    rows.extend(content_rows)

    while len(rows) < PAGE_HEIGHT:
        rows.append(" " * PAGE_WIDTH)

    return rows


def matrix_to_bytes(matrix: List[str], *, encoding: str = "ascii") -> bytes:
    """Convert matrix of text rows to bytes separated by newlines."""
    text = "\n".join(matrix)
    return text.encode(encoding, errors="replace")


def compile_page_to_frame(page: Page) -> bytes:
    """
    High-level helper: Page -> raw bytes frame.
    """
    matrix = compile_page_to_matrix(page)
    # Default to ASCII for maximum decoder compatibility, but allow Unicode
    # on the start page where block-drawing characters are desired.
    encoding = "utf-8" if page.page == "000" else "ascii"
    return matrix_to_bytes(matrix, encoding=encoding)


def load_all_pages(directory: str) -> List[Page]:
    pages: List[Page] = []
    for name in sorted(os.listdir(directory)):
        if not name.lower().endswith(".json"):
            continue
        path = os.path.join(directory, name)
        try:
            page = load_page_from_file(path)
            pages.append(page)
        except Exception as exc:
            print(f"Error loading page {path}: {exc}")
    # Sort by numeric page, then subpage
    pages.sort(key=lambda p: (int(p.page), p.subpage))
    return pages


