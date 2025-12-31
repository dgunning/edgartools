import re
from typing import List, Optional

__all__ = ["extract_item_with_boundaries"]


def extract_item_with_boundaries(
    full_html: str,
    item_start: str,
    item_end_list: List[str],
) -> Optional[str]:
    """
    Extract item content from HTML using regex boundary detection.

    This is a fallback extraction method when document-based section
    detection is unavailable. Uses regex patterns to find item start
    and end boundaries.
    """
    start_pat = re.compile(
        rf"(?:>|\n)\s*{item_start.replace(' ', r'\s+')}\.?",
        re.IGNORECASE,
    )

    end_pat_str = "|".join([i.replace(" ", r"\s+") for i in item_end_list])
    end_pat = re.compile(
        rf"(?:>|\n)\s*(?:{end_pat_str})",
        re.IGNORECASE,
    )

    starts = [m for m in start_pat.finditer(full_html)]
    if not starts:
        return None

    candidates = []
    for start_match in starts:
        start_pos = start_match.start()
        tag_start = full_html.rfind("<", 0, start_pos)
        if tag_start != -1:
            start_pos = tag_start

        end_match = end_pat.search(full_html, pos=start_match.end())
        if end_match:
            end_pos = end_match.start()
            tag_end = full_html.rfind("<", start_match.end(), end_pos)
            if tag_end != -1:
                end_pos = tag_end
            content = full_html[start_pos:end_pos]
            candidates.append(content)

    if not candidates:
        return None

    return max(candidates, key=len)
