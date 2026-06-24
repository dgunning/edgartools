"""Section-boundary scoring harness (edgartools-llmp.5).

Reusable measurement + scoring of detected section boundaries against the
canonical fixture corpus (``manifest.json``). This is the safety net the phased
section-extraction refactor leans on for byte-stability and the Phase 3 flip:
it re-measures every fixture through the live pipeline and scores it against the
recorded golden snapshot, so any code change that moves a boundary surfaces as a
concrete length drift rather than a silent behaviour change.

Powers ``tests/test_section_boundary_corpus.py``. The measurement mirrors
``build_corpus.py`` (the manifest generator) so the two stay consistent; regen
the manifest with ``python tests/fixtures/parser_corpus/build_corpus.py`` when a
parser change is *expected* to move sizes, and commit it alongside the code.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from edgar.documents.config import ParserConfig
from edgar.documents.parser import HTMLParser

_CORPUS_DIR = Path(__file__).resolve().parent
_HTML_ROOT = _CORPUS_DIR.parent / "html"
_MANIFEST = _CORPUS_DIR / "manifest.json"

# Mirror build_corpus.py so the harness and the manifest generator agree.
SUBSTANTIAL_ITEMS_10K = {"1": 2000, "1A": 2000, "1C": 1000, "7": 2000, "8": 2000}
SUBSTANTIAL_ITEMS_10Q = {"1": 2000, "2": 2000}
OVERSIZED_SECTION_CHARS = 300_000


def item_key(section_name: str) -> Optional[str]:
    """Collapse a section name to its bare item key ('1A', '7'), or None."""
    stripped = re.sub(r"^part_[ivx]+_", "", section_name, flags=re.IGNORECASE)
    m = re.match(r"^item[_\s]*(\d+[a-z]?)$", stripped, re.IGNORECASE)
    return m.group(1).upper() if m else None


@lru_cache(maxsize=None)
def load_manifest() -> dict:
    return json.loads(_MANIFEST.read_text())


@lru_cache(maxsize=None)
def measure_fixture(fixture_rel: str, form: str) -> dict:
    """Parse one fixture through the live pipeline and measure its sections.

    Cached so the corpus suite parses each fixture once across all tests.
    Returns ``{n_sections, doc_text_len, items: {key: {text_len, section_name}}}``.
    Keeps the largest occurrence when an item key appears under multiple parts —
    exactly as the manifest generator does.
    """
    html = (_HTML_ROOT / fixture_rel).read_text()
    doc = HTMLParser(ParserConfig(form=form, detect_sections=True)).parse(html)
    sections = doc.sections
    items: Dict[str, dict] = {}
    for name, section in sections.items():
        key = item_key(name)
        if key is None:
            continue
        try:
            text_len = len(section.text() or "")
        except Exception:  # noqa: BLE001 — a broken section measures as -1, like the manifest
            text_len = -1
        prev = items.get(key)
        if prev is None or text_len > prev["text_len"]:
            items[key] = {"text_len": text_len, "section_name": name}
    return {
        "n_sections": len(sections),
        "doc_text_len": len(doc.text() or ""),
        "items": items,
    }


def length_drift(measured: dict, manifest_entry: dict) -> List[str]:
    """Per-item drift between a live measurement and the manifest snapshot.

    Returns a human-readable list of mismatches (missing item, extra item, or a
    changed text length). Empty list == byte-stable against the golden snapshot.
    """
    drifts: List[str] = []
    live = measured["items"]
    golden = manifest_entry.get("items", {})
    for key, info in golden.items():
        if key not in live:
            drifts.append(f"item {key}: missing (was {info['text_len']})")
        elif live[key]["text_len"] != info["text_len"]:
            drifts.append(f"item {key}: {info['text_len']} -> {live[key]['text_len']}")
    for key in live:
        if key not in golden:
            drifts.append(f"item {key}: new ({live[key]['text_len']})")
    return drifts


def overlap_ratio(measured: dict) -> float:
    """Sum of item text lengths over the whole-document text length.

    A cheap, method-agnostic overlap signal: items partition the body (plus
    un-item'd front matter), so a healthy filing sits at or below ~1.0. A ratio
    well above 1.0 means sections duplicate/overlap each other (the #871 bleed
    class — a boundary overshoot pulling a neighbour's body in).
    """
    doc_len = measured["doc_text_len"] or 1
    total = sum(i["text_len"] for i in measured["items"].values() if i["text_len"] > 0)
    return total / doc_len


def auto_markers(measured: dict, form: str) -> List[str]:
    """Recompute the size-anomaly markers build_corpus.py derives (oversize/undersize).

    Excludes the documented-bug markers (those are filing-specific and recorded in
    the manifest); this is just the size-band auto-detection, used to assert that a
    filing the manifest marked healthy has not regressed into an anomaly.
    """
    markers: List[str] = []
    floors = SUBSTANTIAL_ITEMS_10K if form == "10-K" else SUBSTANTIAL_ITEMS_10Q
    for key, info in measured["items"].items():
        if info["text_len"] > OVERSIZED_SECTION_CHARS:
            markers.append(f"oversized:item_{key}")
        floor = floors.get(key)
        if floor is not None and 0 <= info["text_len"] < floor:
            markers.append(f"undersized:item_{key}")
    return markers
