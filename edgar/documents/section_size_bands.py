"""
Section content-size guardrail (edgartools-9hwf).

Silent wrong-content is the worst failure class for a data library: a section
returned at 0.95 confidence whose text is actually 668KB of the wrong item
(Goldman Sachs ``.business``) or 1.78MB of raw HTML (Citigroup), or conversely a
few hundred characters because the anchor landed on a PART header instead of the
item body. No exception, no warning — just wrong content the caller builds a
pipeline on.

This module flags those cases. For the items that are reliably substantial and
low-variance on a given form, it knows the expected content-size band. A section
whose extracted length falls outside its band gets a human-readable warning and a
reduced confidence, so callers can detect the problem (Verification Constitution
#2; design sprint Decision D4 — flag-and-return, not silent-return).

The bands are curated from the canonical fixture corpus
(``tests/fixtures/parser_corpus/size_bands.json``, issue edgartools-h44r): only
the ``enforce``-flagged items are kept. They now live on each ``FormSchema``
(``FormSchema.size_bands`` in ``form_schema.py`` — the single home of form
knowledge, edgartools-llmp.2); this module's logic reads them from there.
Regenerate the corpus and update the bands on the schemas when fixtures rotate.

Undersize has two causes, and they need different warnings (GH #927). A section
can be short because extraction failed — the anchor landed on a heading and the
body was left behind — or because the filer answered the item with a pointer:
NVIDIA's Item 8 is 207 chars of "set forth in our Consolidated Financial
Statements ... included in this Annual Report", with the statements filed under
Item 15. The second case is a faithful extraction of a cross-reference, so
telling the caller the anchor is wrong sends them to debug a parser that did its
job. :func:`is_cross_reference` separates the two on the undersize path.

Caveat — these bands are tuned to large-cap filers, and Item 8's floor assumes a
filer that inlines its financial statements. Incorporation-by-reference filers
legitimately fall below it (NVDA/NFLX/IBM/ORCL in the corpus); they are flagged
as cross-references rather than as truncated extractions. Bands are
intentionally generous (median/5 .. median*8) so they flag only gross anomalies,
not normal variation.
"""
from __future__ import annotations

import re
from typing import Dict, Optional

from edgar.documents.form_schema import get_form_schema

# The size bands themselves now live on each FormSchema (edgartools-llmp.2 / D2 —
# FormSchema is the single home of form knowledge). This module keeps the
# guardrail's evaluation logic and its public API (band_for/evaluate_size/
# ANOMALOUS_CONFIDENCE), consulting the schema for the per-form data.

# Back-compat read-only projection of the schema bands, in the legacy
# {form: {item: {"low", "high"}}} shape. The schema is the single source of
# truth; this view is derived from it (used by the corpus drift-guard test).
SIZE_BANDS: Dict[str, Dict[str, Dict[str, int]]] = {
    form: {k: {"low": low, "high": high}
           for k, low, high in get_form_schema(form).size_bands}
    for form in ("10-K", "10-Q")
}

# Confidence assigned to a section whose size is anomalous. Below the healthy
# 0.95 (so it's visibly degraded) but kept as a constant the caller can test
# against; the human-readable warning carries the detail.
ANOMALOUS_CONFIDENCE = 0.5


def band_for(form: Optional[str], item_key: Optional[str],
             part: Optional[str] = None) -> Optional[Dict[str, int]]:
    """Return the size band for a (form, part, item), or None if not enforced.

    A falsy ``form`` is never enforced (preserves the pre-schema behaviour where
    an unknown/None form missed the table); known forms resolve via the schema,
    whose bands are empty for forms without curated enforcement (8-K, 20-F).

    ``part`` matters on forms whose item numbers repeat across parts. A 10-Q has
    two Item 1s — Financial Statements in Part I, Legal Proceedings in Part II —
    and only the first is size-enforced, so a caller that cannot say which Part
    it holds gets None rather than the wrong item's band (edgartools-xhmd).
    """
    if not form or not item_key:
        return None
    band = get_form_schema(form).band_for(item_key, part=part)
    return {"low": band[0], "high": band[1]} if band else None


def _item_label(item_key: Optional[str], part: Optional[str]) -> str:
    """How an item is named in a warning: "Item 6" or "Part II Item 6"."""
    if not part:
        return f"Item {item_key}"
    return f"Part {part.upper().replace('PART', '').strip()} Item {item_key}"


def evaluate_size(form: Optional[str], item_key: Optional[str], length: int,
                  part: Optional[str] = None) -> Optional[str]:
    """Return a warning string if ``length`` is outside the band, else None.

    ``length`` of 0 or negative is treated as "unknown" and never flagged — an
    empty section is a different signal (missing, not anomalous-size) handled
    upstream by the detector's empty-section skip.

    ``part`` selects the band on forms whose items repeat across parts, and names
    the section in the warning, where "Item 1" alone is ambiguous on a 10-Q.
    """
    band = band_for(form, item_key, part=part)
    if band is None or length <= 0:
        return None
    label = _item_label(item_key, part)
    if length < band["low"]:
        return (f"{label} content is {length:,} chars, below the expected "
                f"minimum of {band['low']:,} for a {form} — the section anchor may "
                f"point at a heading rather than the item body (extraction likely truncated).")
    if length > band["high"]:
        return (f"{label} content is {length:,} chars, above the expected "
                f"maximum of {band['high']:,} for a {form} — the section boundary may "
                f"overshoot into adjacent items (extraction likely over-captured).")
    return None


def is_undersize(form: Optional[str], item_key: Optional[str], length: int,
                 part: Optional[str] = None) -> bool:
    """True when ``length`` falls below the (form, part, item) band's floor.

    Lets a caller that already has an :func:`evaluate_size` warning tell which
    side of the band tripped it without matching on the message text.
    """
    band = band_for(form, item_key, part=part)
    return band is not None and 0 < length < band["low"]


# An item body that points at content held elsewhere in the filing rather than
# carrying it. Two shapes, both common in Item 8:
#
#   "...incorporated herein by reference"                            (IBM)
#   "<deferral verb> ... <pointer target>"                           (NVDA, NFLX,
#                                                                     ORCL)
#
# The second needs both halves — a bare "included" or a bare "Item 15" is
# ordinary prose. Requiring them within one clause ([^.;] keeps the match inside
# a sentence) is what keeps this from firing on narrative text. This is only ever
# consulted for a section already below its size band, so the pattern is a
# tie-breaker between two diagnoses, not a general-purpose classifier.
_CROSS_REFERENCE_RE = re.compile(
    r"incorporated\s+(?:herein\s+)?by\s+reference"
    r"|reference\s+is\s+made\s+to"
    r"|refer\s+to\s+pages?\s+\d"
    r"|\b(?:set\s+forth|submitted|included|presented|listed|contained|appears?)\b"
    r"[^.;]{0,120}?"
    r"(?:\bItem\s*\d|\bPart\s+[IVXL]+\b|separate\s+section|Annual\s+Report"
    r"|Financial\s+Statements?\s+and\s+Notes"
    r"|financial\s+(?:table\s+of\s+contents|section)|pages?\s+\d)",
    re.IGNORECASE,
)


# A pointer is short, and in a section long enough to hold a real body the
# deferral cannot sit in the middle of one. Both bounds are calibrated against
# the fixture corpus and both are load-bearing: XOM (7,208 chars, match at
# 2,423) fails both, KO (12,718 chars, match at 81) fails only the length one.
_MAX_POINTER_CHARS = 1_500      # longest true pointer in the corpus is 268
_MAX_POINTER_OFFSET = 400       # XOM's mid-body match sits at 2,423


def is_cross_reference(text: Optional[str]) -> bool:
    """True when ``text`` reads as an incorporation-by-reference pointer.

    Examples from the fixture corpus, all Item 8 bodies under 300 chars:

        NVDA  "...is set forth in our Consolidated Financial Statements and
               Notes thereto included in this Annual Report on Form 10-K."
        NFLX  "...listed in Part IV, Item 15(a)(1) of this Annual Report..."
        IBM   "Refer to pages 46 through 121 ... incorporated herein by reference."
        ORCL  "...submitted as a separate section of this Annual Report. See
               Part IV, Item 15."

    A bare item heading ("Item 8. Financial Statements and Supplementary Data")
    carries no deferral and is not a cross-reference — that is the truncated
    extraction the size warning is meant to describe. Nor is a genuine body
    that happens to mention a deferral (XOM's complete 7,208-char Item 1) —
    the length and offset bounds keep those out.
    """
    if not text or len(text) > _MAX_POINTER_CHARS:
        return False
    match = _CROSS_REFERENCE_RE.search(text)
    return match is not None and match.start() <= _MAX_POINTER_OFFSET


def cross_reference_warning(form: Optional[str], item_key: Optional[str], length: int,
                            part: Optional[str] = None) -> str:
    """The undersize warning for a section the filer incorporated by reference."""
    return (f"{_item_label(item_key, part)} content is {length:,} chars and reads as an "
            f"incorporation by reference — the filer answered this item with a "
            f"pointer to content held elsewhere in the {form} (for Item 8, usually "
            f"under Item 15) rather than printing it under the item heading. The "
            f"extraction is faithful to the document; the returned text is the "
            f"pointer, not the item's substance.")
