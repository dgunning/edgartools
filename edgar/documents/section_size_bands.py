"""
Section content-size guardrail (edgartools-9hwf).

Silent wrong-content is the worst failure class for a data library: a section
returned at 0.95 confidence whose text is actually 668KB of the wrong item
(Goldman Sachs ``.business``) or 1.78MB of raw HTML (Citigroup), or conversely a
few hundred characters because the anchor landed on a PART header instead of the
item body (Netflix/IBM/NVIDIA Item 8). No exception, no warning — just wrong
content the caller builds a pipeline on.

This module flags those cases. For the items that are reliably substantial and
low-variance on a given form, it knows the expected content-size band. A section
whose extracted length falls outside its band gets a human-readable warning and a
reduced confidence, so callers can detect the problem (Verification Constitution
#2; design sprint Decision D4 — flag-and-return, not silent-return).

The bands are curated from the canonical fixture corpus
(``tests/fixtures/parser_corpus/size_bands.json``, issue edgartools-h44r): only
the ``enforce``-flagged items appear here. Regenerate the corpus and copy the
enforced bands here when fixtures rotate — keep the two in sync.

Caveat — these bands are tuned to large-cap filers. Item 8 in particular is
enforceable only because every corpus filer inlines its financial statements; a
filer that incorporates Item 8 by reference would legitimately be small. Bands
are intentionally generous (median/5 .. median*8) so they flag only gross
anomalies, not normal variation.
"""
from __future__ import annotations

from typing import Dict, Optional

# Per (form, item) expected content-size bands, in characters. Enforced items
# only — see module docstring. Generated from the h44r corpus; do not hand-edit
# without regenerating the corpus.
SIZE_BANDS: Dict[str, Dict[str, Dict[str, int]]] = {
    "10-K": {
        "1":  {"low": 8_034,  "high": 321_384},    # Business
        "1A": {"low": 15_978, "high": 639_136},    # Risk Factors
        "1C": {"low": 1_542,  "high": 61_680},     # Cybersecurity
        "7":  {"low": 11_440, "high": 457_616},    # MD&A
        "8":  {"low": 26_136, "high": 1_045_472},  # Financial Statements (large-cap; see caveat)
        "9A": {"low": 791,    "high": 31_640},     # Controls and Procedures
        "16": {"low": 410,    "high": 16_400},     # Form 10-K Summary / other
    },
    "10-Q": {
        "1": {"low": 18_009, "high": 720_376},     # Financial Statements
        "2": {"low": 10_134, "high": 405_368},     # MD&A
        "6": {"low": 518,    "high": 20_720},      # Exhibits
    },
}

# Confidence assigned to a section whose size is anomalous. Below the healthy
# 0.95 (so it's visibly degraded) but kept as a constant the caller can test
# against; the human-readable warning carries the detail.
ANOMALOUS_CONFIDENCE = 0.5


def band_for(form: Optional[str], item_key: Optional[str]) -> Optional[Dict[str, int]]:
    """Return the size band for a (form, item), or None if not enforced."""
    if not form or not item_key:
        return None
    return SIZE_BANDS.get(form, {}).get(item_key.upper())


def evaluate_size(form: Optional[str], item_key: Optional[str], length: int) -> Optional[str]:
    """Return a warning string if ``length`` is outside the band, else None.

    ``length`` of 0 or negative is treated as "unknown" and never flagged — an
    empty section is a different signal (missing, not anomalous-size) handled
    upstream by the detector's empty-section skip.
    """
    band = band_for(form, item_key)
    if band is None or length <= 0:
        return None
    if length < band["low"]:
        return (f"Item {item_key} content is {length:,} chars, below the expected "
                f"minimum of {band['low']:,} for a {form} — the section anchor may "
                f"point at a heading rather than the item body (extraction likely truncated).")
    if length > band["high"]:
        return (f"Item {item_key} content is {length:,} chars, above the expected "
                f"maximum of {band['high']:,} for a {form} — the section boundary may "
                f"overshoot into adjacent items (extraction likely over-captured).")
    return None
