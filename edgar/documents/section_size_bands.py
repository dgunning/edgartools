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
the ``enforce``-flagged items are kept. They now live on each ``FormSchema``
(``FormSchema.size_bands`` in ``form_schema.py`` — the single home of form
knowledge, edgartools-llmp.2); this module's logic reads them from there.
Regenerate the corpus and update the bands on the schemas when fixtures rotate.

Caveat — these bands are tuned to large-cap filers. Item 8 in particular is
enforceable only because every corpus filer inlines its financial statements; a
filer that incorporates Item 8 by reference would legitimately be small. Bands
are intentionally generous (median/5 .. median*8) so they flag only gross
anomalies, not normal variation.
"""
from __future__ import annotations

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


def band_for(form: Optional[str], item_key: Optional[str]) -> Optional[Dict[str, int]]:
    """Return the size band for a (form, item), or None if not enforced.

    A falsy ``form`` is never enforced (preserves the pre-schema behaviour where
    an unknown/None form missed the table); known forms resolve via the schema,
    whose bands are empty for forms without curated enforcement (8-K, 20-F).
    """
    if not form or not item_key:
        return None
    band = get_form_schema(form).band_for(item_key)
    return {"low": band[0], "high": band[1]} if band else None


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
