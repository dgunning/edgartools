"""
Build the canonical parser fixture corpus manifest and size bands.

This generator scans the local HTML fixtures under ``tests/fixtures/html/``,
parses each through the section-detection pipeline, and emits two artifacts:

  - ``manifest.json``   — one entry per fixture: ticker, form, filing date,
                          detected filing agent, per-item text lengths + table
                          counts, and known-bad markers.
  - ``size_bands.json`` — per (form, item) expected content-size bands, derived
                          from the *healthy* filings only (known-bad filings are
                          excluded so their absurd sizes don't poison the band).

The size bands are the bridge to the silent-failure guardrail (edgartools-9hwf):
content that falls below ``low`` (anchor landed on a PART header, not the item
body) or above ``high`` (boundary overshoot — e.g. Citi's 1.78MB Item, GS's
668KB ``.business``) is wrong and should be flagged rather than returned at 0.95
confidence.

Run (one-time / on refresh):
    python tests/fixtures/parser_corpus/build_corpus.py

Refresh cadence: regenerate when fixtures are added/rotated, or quarterly.
See README.md.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from statistics import median
from typing import Dict, List, Optional

from edgar.documents.agents import detect_filing_agent
from edgar.documents.config import ParserConfig
from edgar.documents.parser import HTMLParser

HTML_ROOT = Path("tests/fixtures/html")
CORPUS_DIR = Path("tests/fixtures/parser_corpus")

# Items that are *reliably* substantial on a large-cap 10-K — never a few
# hundred chars unless the anchor landed on the heading instead of the body.
# These get an undersize floor (below it ⇒ known-bad). Items NOT listed (1B,
# 4, 6, 9, 9B, 9C, ...) are commonly legitimate "None"/"Not applicable" and
# get no floor. Item 8 is included because every filer in this large-cap
# corpus inlines its statements; on a broader corpus Item 8 is bimodal
# (incorporation-by-reference) and the floor would not apply — see README.
SUBSTANTIAL_ITEMS_10K = {"1": 2000, "1A": 2000, "1C": 1000, "7": 2000, "8": 2000}
SUBSTANTIAL_ITEMS_10Q = {"1": 2000, "2": 2000}  # Part I statements, MD&A

# A single item this large is almost always a boundary overshoot, not real
# content (the largest legitimate Item in this corpus is ~285KB).
OVERSIZED_SECTION_CHARS = 300_000

# Documented known-bad filings (bug edgartools-sldz / #821). These are excluded
# from size-band derivation and asserted as known failures by the benchmark.
DOCUMENTED_KNOWN_BAD = {
    ("gs", "10-K"): ["part_misclassification", "oversized_business_section"],
    ("c", "10-K"): ["raw_html_leak", "oversized_section"],
    ("jpm", "10-K"): ["legacy_fallback_required"],
}


def _form_from_path(path: Path) -> Optional[str]:
    if "/10k/" in path.as_posix():
        return "10-K"
    if "/10q/" in path.as_posix():
        return "10-Q"
    return None


def _date_from_name(name: str) -> Optional[str]:
    m = re.search(r"(\d{4}-\d{2}-\d{2})", name)
    return m.group(1) if m else None


def _item_key(section_name: str) -> Optional[str]:
    """Collapse a section name to its bare item key ('1A', '7'), or None."""
    stripped = re.sub(r"^part_[ivx]+_", "", section_name, flags=re.IGNORECASE)
    m = re.match(r"^item[_\s]*(\d+[a-z]?)$", stripped, re.IGNORECASE)
    return m.group(1).upper() if m else None


def measure_fixture(path: Path) -> Optional[dict]:
    """Parse one fixture and return its manifest entry, or None if unparseable."""
    form = _form_from_path(path)
    if form is None:
        return None
    ticker = path.parts[path.parts.index("html") + 1]
    html = path.read_text()

    agent = detect_filing_agent(html)
    try:
        doc = HTMLParser(ParserConfig(form=form, detect_sections=True)).parse(html)
        sections = doc.sections
    except Exception as e:  # noqa: BLE001 — record the failure, don't abort the run
        return {
            "ticker": ticker, "form": form, "date": _date_from_name(path.name),
            "fixture": path.relative_to(HTML_ROOT).as_posix(),
            "agent": agent, "parse_error": str(e), "items": {}, "known_bad": ["parse_error"],
        }

    # Per-item text length + table count, keyed by bare item key.
    items: Dict[str, dict] = {}
    for name, section in sections.items():
        key = _item_key(name)
        if key is None:
            continue
        try:
            text_len = len(section.text() or "")
        except Exception:  # noqa: BLE001
            text_len = -1
        try:
            n_tables = len(section.tables())
        except Exception:  # noqa: BLE001
            n_tables = -1
        # Keep the largest occurrence if an item key appears under multiple parts.
        prev = items.get(key)
        if prev is None or text_len > prev["text_len"]:
            items[key] = {"text_len": text_len, "n_tables": n_tables, "section_name": name}

    known_bad = list(DOCUMENTED_KNOWN_BAD.get((ticker, form), []))

    # Auto-detect anomalies on top of the documented markers.
    floors = SUBSTANTIAL_ITEMS_10K if form == "10-K" else SUBSTANTIAL_ITEMS_10Q
    for key, info in items.items():
        if info["text_len"] > OVERSIZED_SECTION_CHARS and "oversized_section" not in known_bad \
                and "oversized_business_section" not in known_bad:
            known_bad.append(f"oversized:item_{key}")
        floor = floors.get(key)
        if floor is not None and 0 <= info["text_len"] < floor:
            known_bad.append(f"undersized:item_{key}")

    return {
        "ticker": ticker, "form": form, "date": _date_from_name(path.name),
        "fixture": path.relative_to(HTML_ROOT).as_posix(),
        "agent": agent,
        "n_sections": len(sections),
        "items": items,
        "known_bad": known_bad,
    }


def derive_size_bands(entries: List[dict]) -> dict:
    """Per (form, item) bands from healthy filings (known_bad excluded)."""
    buckets: Dict[str, Dict[str, List[int]]] = {}
    for e in entries:
        if e.get("known_bad"):
            continue  # healthy only
        form = e["form"]
        for key, info in e.get("items", {}).items():
            if info["text_len"] <= 0:
                continue
            buckets.setdefault(form, {}).setdefault(key, []).append(info["text_len"])

    bands: Dict[str, dict] = {}
    for form, by_item in buckets.items():
        bands[form] = {}
        for key, lengths in by_item.items():
            lengths.sort()
            lo, hi, mid, n = lengths[0], lengths[-1], int(median(lengths)), len(lengths)
            # Median-relative thresholds are robust to the occasional broken
            # section that slips into the healthy set (a 250-char Item 8 won't
            # gut the floor the way `min // 2` would):
            #  - low_flag = p50 // 5: a section under 1/5 the median is
            #    suspicious (anchor landed on the heading, not the body).
            #  - high_flag = p50 * 8: a section over 8x the median is a
            #    boundary overshoot (GS 668KB / Citi 1.78MB are >>8x typical).
            # `enforce` gates the guardrail (9hwf) to items that are reliably
            # substantial AND low-variance: even the smallest healthy instance
            # must be sizeable. Keying on `min` (not the median) excludes
            # high-variance items whose median is large but which have a
            # legitimate small instance — Exhibits (Item 15, e.g. HubSpot at
            # ~1.1KB) and market-risk (Item 7A) vary too much to floor.
            enforce = n >= 8 and lo >= 1000
            bands[form][key] = {
                "n": n, "min": lo, "p50": mid, "max": hi,
                "low_flag": mid // 5,
                "high_flag": mid * 8,
                "enforce": enforce,
            }
    return bands


def main() -> None:
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    fixtures = sorted(HTML_ROOT.rglob("*.html"))
    print(f"Scanning {len(fixtures)} fixtures...")

    entries: List[dict] = []
    for path in fixtures:
        entry = measure_fixture(path)
        if entry is None:
            continue
        flags = ",".join(entry["known_bad"]) or "ok"
        print(f"  {entry['ticker']:6} {entry['form']:5} agent={str(entry['agent']):14} "
              f"sections={entry.get('n_sections', '?'):>3}  [{flags}]")
        entries.append(entry)

    manifest = {
        "description": "Canonical parser fixture corpus (edgartools-h44r).",
        "fixture_root": HTML_ROOT.as_posix(),
        "n_filings": len(entries),
        "filings": entries,
    }
    (CORPUS_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    bands = derive_size_bands(entries)
    (CORPUS_DIR / "size_bands.json").write_text(json.dumps(
        {"description": "Per (form, item) content-size bands from healthy filings "
                        "(edgartools-h44r; consumed by edgartools-9hwf).",
         "bands": bands}, indent=2) + "\n")

    n_bad = sum(1 for e in entries if e["known_bad"])
    print(f"\nWrote manifest.json ({len(entries)} filings, {n_bad} known-bad) "
          f"and size_bands.json to {CORPUS_DIR}/")


if __name__ == "__main__":
    main()
