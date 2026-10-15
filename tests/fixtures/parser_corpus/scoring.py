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
from typing import Dict, List, Optional, Tuple

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


_BARE_ITEM_RE = re.compile(r"^\d+[A-Z]?$", re.IGNORECASE)


def section_item_key(section_name: str, section) -> Optional[str]:
    """The item key of a live section, whatever the pipeline named it.

    TOC sections are named ``part_i_item_1``; pattern sections can carry a
    semantic name ('business', 'mda', 'risk_factors') with the item on
    ``section.item``. Keying on the name alone skipped every semantic-named
    section, so the truth set and the self-consistency ratchet never saw them
    (edgartools-llmp.11.2).
    """
    key = item_key(section_name)
    if key is not None:
        return key
    item = getattr(section, "item", None)
    return str(item).upper() if item and _BARE_ITEM_RE.match(str(item)) else None


def canonical_section_name(section_name: str, section) -> str:
    """``part_<part>_item_<item>`` for a semantic-named section, so truth keys survive a rename."""
    if item_key(section_name) is not None:
        return section_name
    key = section_item_key(section_name, section)
    part = getattr(section, "part", None)
    if key is None or not part:
        return section_name
    return f"part_{str(part).lower()}_item_{key.lower()}"


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
        key = section_item_key(name, section)
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


# ---------------------------------------------------------------------------
# Self-consistency scores (edgartools-llmp.11)
# ---------------------------------------------------------------------------
# Two necessary conditions for a correct slice that need no ground truth:
#
#   embeds_later_heading  a later canonical item's heading appears at the start
#                         of a line after the section's own opening. STRONG: on
#                         the 2026-10-11 sweep every hit inspected was a real
#                         end-boundary defect (the next item's anchor missing or
#                         placed after its heading, two items sharing an anchor,
#                         the last item running into the exhibit index).
#   opens_on_heading      the section's own item label appears in its first
#                         300 chars. WEAK: title-only body headings ("Business",
#                         "PROPERTIES") and cross-reference-index slices
#                         legitimately fail it. Reported, never ratcheted.
#
# Only canonical items count, and only ones this section does not itself cover
# (a combined "Items 1 and 2" section may contain the Item 2 heading).

CANONICAL_ITEMS = {
    "10-K": {"1", "1A", "1B", "1C", "2", "3", "4", "5", "6", "7", "7A", "8", "9",
             "9A", "9B", "9C", "10", "11", "12", "13", "14", "15", "16"},
    "10-Q": {"1", "1A", "2", "3", "4", "5", "6"},
}

OPENING_CHARS = 300
_HEADING_LINE_MAX = 160
_INDEX_RUN_MIN = 3

_OWN_LABEL_RE = re.compile(r"ITEM\s*(\d+[A-Z]?)", re.IGNORECASE)
# "Item 2." at line start is a heading. Two things are not: "Item 2.03", an
# 8-K item reference ("the information set forth under Item 1.01 is
# incorporated by reference", inside a 10-K Item 9B), so a dotted decimal
# after the number is excluded; and "Item 7 below, we agreed to ...", a
# cross-reference that line-wrapping put at line start, so a lowercase word
# right after the number is excluded (a heading's title is capitalised),
# except "and", which joins a combined heading ("Items 1 and 2. Business").
_HEADING_LINE_RE = re.compile(
    r"^\s*(?:PART\s+[IVX]+\s*[,.\-\u2013\u2014:]?\s*)?ITEMS?\s*(\d+[A-Z]?)"
    r"(?:\s*[:\-\u2013\u2014]|\s*\.(?!\d)|\s)\s*(?:(?=and\b)|(?!(?-i:[a-z])))",
    re.IGNORECASE,
)


def opens_on_heading(text: str, own_items) -> bool:
    """True if one of ``own_items`` is labelled within the section's opening."""
    own = {k.upper() for k in own_items}
    head = text[:OPENING_CHARS]
    return any(m.group(1).upper() in own for m in _OWN_LABEL_RE.finditer(head))


def embeds_later_heading(text: str, own_items, form: str) -> List[str]:
    """Canonical items (not in ``own_items``) whose heading sits at line start
    after the opening. Sorted, de-duplicated; empty means consistent."""
    canon = CANONICAL_ITEMS.get(form, set())
    own = {k.upper() for k in own_items}
    # Group matches into runs of consecutive non-blank lines. A run of three
    # or more is an index listing (GE's cross-reference index, Mastercard's
    # per-Part contents, a pattern section that caught the TOC itself), which
    # is content, not a leaked boundary, so it is skipped.
    runs: List[List[str]] = []
    run: List[str] = []
    for line in text[OPENING_CHARS:].splitlines():
        if not line.strip():
            continue
        m = _HEADING_LINE_RE.match(line) if len(line) <= _HEADING_LINE_MAX else None
        if m:
            run.append(m.group(1).upper())
        elif run:
            runs.append(run)
            run = []
    if run:
        runs.append(run)
    found = set()
    for run in runs:
        if len(run) >= _INDEX_RUN_MIN:
            continue
        for item in run:
            if item in canon and item not in own:
                found.add(item)
    return sorted(found)


# Per-document facts recorded by measure_consistency as a side effect, so the
# overlap check needs no second parse: (path, form) -> {doc_text_len,
# section_lens, methods}. Read through document_measure().
_DOCUMENT_MEASURES: Dict[tuple, dict] = {}


def document_measure(path: str, form: str) -> dict:
    """``{doc_text_len, section_lens, methods}`` for one fixture.

    ``section_lens`` is the text length of every item section (a 10-Q's two
    Item 1s count separately), ``methods`` the set of detection methods seen.
    Parses through :func:`measure_consistency`, so the two share one parse.
    """
    measure_consistency(path, form)
    return _DOCUMENT_MEASURES[(path, form)]


def overlap_ratio_of(measure: dict) -> float:
    """Sum of item section text over document text, as :func:`overlap_ratio`."""
    return sum(measure["section_lens"]) / (measure["doc_text_len"] or 1)


@lru_cache(maxsize=None)
def measure_consistency(path: str, form: str) -> Dict[str, dict]:
    """Per-item self-consistency of one fixture through the live pipeline.

    ``path`` is absolute (the fixture may live outside ``html/``: parity_gate or
    the gitignored era corpus). Returns ``{item_key: {"embeds": [...],
    "opens": bool, "method": str, "text_len": int}}``. When an item key appears
    under several parts the embed sets are unioned and ``opens`` is any-of, so a
    10-Q's two Item 1s are one row.
    """
    html = Path(path).read_text(errors="ignore")
    doc = HTMLParser(ParserConfig(form=form, detect_sections=True)).parse(html)
    out: Dict[str, dict] = {}
    section_lens: List[int] = []
    methods = set()
    for name, section in doc.sections.items():
        key = section_item_key(name, section)
        if key is None:
            continue
        own = {key}
        for covered in (getattr(section, "covered_items", None) or []):
            ck = item_key(str(covered)) or item_key(f"item_{covered}")
            if ck:
                own.add(ck)
        try:
            text = section.text() or ""
        except Exception:  # noqa: BLE001 — a broken section measures as empty
            text = ""
        embeds = embeds_later_heading(text, own, form)
        opens = opens_on_heading(text, own)
        section_lens.append(len(text))
        methods.add(getattr(section, "detection_method", None))
        prev = out.get(key)
        if prev is None:
            out[key] = {
                "embeds": embeds, "opens": opens, "text_len": len(text),
                "method": getattr(section, "detection_method", None),
            }
        else:
            prev["embeds"] = sorted(set(prev["embeds"]) | set(embeds))
            prev["opens"] = prev["opens"] or opens
            prev["text_len"] = max(prev["text_len"], len(text))
    _DOCUMENT_MEASURES[(path, form)] = {
        "doc_text_len": len(doc.text() or ""),
        "section_lens": section_lens,
        "methods": methods,
    }
    return out


def embed_set(measured: Dict[str, dict]) -> frozenset:
    """The item keys of ``measured`` whose slice embeds a later heading."""
    return frozenset(k for k, v in measured.items() if v["embeds"])


_GATE_ROOT = _CORPUS_DIR.parent / "parity_gate"
_ERA_ROOT = _CORPUS_DIR.parent / "text_boundary_corpus"
# Held-out filings retired to development (heldout/README.md rule 3). Tracked,
# but kept out of parity_gate: the parity ratchets compare against frozen
# legacy-parser output, and these filings joined after that parser was deleted.
_RETIRED_ROOT = _CORPUS_DIR.parent / "heldout_retired"
_FORM_DIR = {"10-K": "10k", "10-Q": "10q"}


def consistency_corpus() -> List[dict]:
    """Every 10-K / 10-Q fixture available for the self-consistency ratchet.

    Four sources: every filing under the tracked ``html/<ticker>/{10k,10q}/``
    tree (not just the manifest, which is a stale snapshot), the tracked
    ``parity_gate`` slice, the tracked held-out filings retired to development
    (``heldout_retired``), and the gitignored era corpus, which exists on developer machines only. The label
    is the file stem, so a ticker directory holding two fixtures (Citi's two
    10-Ks) measures both rather than silently one. Each entry is
    ``{label, form, path, tracked}``; a caller must treat a baseline entry whose
    fixture is absent as *unmeasured*, never as fixed.
    """
    entries: List[dict] = []
    seen = set()

    def add(label: str, form: str, path: Path, tracked: bool) -> None:
        if (label, form) in seen or not path.exists():
            return
        seen.add((label, form))
        entries.append({"label": label, "form": form, "path": str(path), "tracked": tracked})

    for form, subdir in _FORM_DIR.items():
        for path in sorted(_HTML_ROOT.glob(f"*/{subdir}/*.html")):
            add(path.stem, form, path, True)
        for path in sorted(_GATE_ROOT.glob(f"{form}/*.html")):
            add(path.stem, form, path, True)
        for path in sorted(_RETIRED_ROOT.glob(f"{form}/*.html")):
            add(path.stem, form, path, True)
        for path in sorted(_ERA_ROOT.glob(f"*/{form}/*.html")):
            add(path.stem, form, path, False)
    return entries


if __name__ == "__main__":  # pragma: no cover — the report behind EMBED_BASELINE
    import time

    t0 = time.time()
    totals: Dict[str, List[int]] = {}
    rows = []
    for entry in consistency_corpus():
        measured = measure_consistency(entry["path"], entry["form"])
        embeds = embed_set(measured)
        t = totals.setdefault(entry["form"], [0, 0, 0])
        t[0] += len(measured)
        t[1] += len(embeds)
        t[2] += sum(1 for v in measured.values() if not v["opens"])
        if embeds:
            rows.append((entry["label"], entry["form"], sorted(embeds), entry["tracked"]))
    for form, (n, emb, no_open) in sorted(totals.items()):
        line = (f"{form}: {n} item sections, {emb} embed a later heading, "
                f"{no_open} do not open on their own label")
        print(line)  # noqa: T201
    print(f"({time.time() - t0:.0f}s)\n\nEMBED_BASELINE = {{")  # noqa: T201
    for label, form, items, tracked in sorted(rows):
        note = "" if tracked else "  # era corpus (gitignored)"
        print(f"    ({label!r}, {form!r}): {{{', '.join(repr(i) for i in items)}}},{note}")  # noqa: T201
    print("}")  # noqa: T201


# ---------------------------------------------------------------------------
# Boundary truth set (edgartools-llmp.11, deliverable 2)
# ---------------------------------------------------------------------------
# ``boundary_truth.json`` records, per fixture and item, the first and last
# TRUTH_CHARS characters of the correct slice, whitespace-collapsed. Unlike
# the pipeline-captured lengths in test_section_boundary_corpus.py these are
# independent: each item was read against the rendered filing (``verified``
# says how: "eye" for a boundary a person checked, "wrong" for one known to be
# wrong today, with the correct text where it could be established). The
# scorer reports start-exact and end-exact per form, which is the number the
# detector work is gated on.

TRUTH_CHARS = 80
_TRUTH_PATH = _CORPUS_DIR / "boundary_truth.json"


def collapse(text: str) -> str:
    """Whitespace-collapsed text, the form boundaries are compared in."""
    return re.sub(r"\s+", " ", text or "").strip()


def head_tail(text: str) -> Tuple[str, str]:
    c = collapse(text)
    return c[:TRUTH_CHARS], c[-TRUTH_CHARS:]


@lru_cache(maxsize=None)
def load_truth() -> dict:
    return json.loads(_TRUTH_PATH.read_text())


@lru_cache(maxsize=None)
def measure_sections(path: str, form: str) -> Dict[str, dict]:
    """``{section_name: {head, tail, text_len, method, item, part}}`` through the live pipeline."""
    html = Path(path).read_text(errors="ignore")
    doc = HTMLParser(ParserConfig(form=form, detect_sections=True)).parse(html)
    out: Dict[str, dict] = {}
    for name, section in doc.sections.items():
        if section_item_key(name, section) is None:
            continue
        name = canonical_section_name(name, section)
        if name in out:
            continue
        try:
            text = section.text() or ""
        except Exception:  # noqa: BLE001
            text = ""
        head, tail = head_tail(text)
        out[name] = {
            "head": head, "tail": tail, "text_len": len(text),
            "method": getattr(section, "detection_method", None),
            "item": getattr(section, "item", None), "part": getattr(section, "part", None),
        }
    return out


def score_truth(truth_entry: dict, live: Dict[str, dict]) -> Dict[str, dict]:
    """Score one fixture's truth items against the live sections.

    Returns ``{section_name: {start, end, found}}`` with booleans. An item whose
    truth is recorded as wrong-with-no-correct-text scores False on the side
    that is unknown; a section the pipeline no longer emits scores False on both.
    """
    result: Dict[str, dict] = {}
    for name, want in truth_entry["items"].items():
        got = live.get(name)
        if got is None:
            result[name] = {"found": False, "start": False, "end": False}
            continue
        start = want.get("start")
        end = want.get("end")
        result[name] = {
            "found": True,
            "start": start is not None and got["head"] == start,
            "end": end is not None and got["tail"] == end,
        }
    return result
