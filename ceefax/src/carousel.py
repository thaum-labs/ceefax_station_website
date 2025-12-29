import time
from typing import Iterable, List, Tuple

from .compiler import Page, compile_page_to_frame


def build_carousel(pages: List[Page]) -> Iterable[Tuple[Page, bytes]]:
    """
    Infinite generator that cycles through pages and yields (Page, frame_bytes).
    """
    compiled = [(p, compile_page_to_frame(p)) for p in pages]
    if not compiled:
        raise RuntimeError("No pages loaded for carousel")
    while True:
        for page, frame in compiled:
            yield page, frame


def run_carousel(
    pages: List[Page],
    transmit_callback,
    page_duration_ms: int,
    loop_delay_ms: int,
):
    """
    Run the carousel, calling transmit_callback(page, frame_bytes) for each page.
    Blocks forever.
    """
    carousel = build_carousel(pages)
    for page, frame in carousel:
        transmit_callback(page, frame)
        # For continuous streaming (e.g. stdout audio), callers can set
        # page_duration_ms to 0 to avoid inserting extra silent gaps.
        if page_duration_ms > 0:
            time.sleep(page_duration_ms / 1000.0)
        # loop_delay_ms can be used later to pause between full loops if needed.


