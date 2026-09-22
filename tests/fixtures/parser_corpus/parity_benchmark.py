#!/usr/bin/env python
"""New-vs-legacy section-extraction parity benchmark (edgartools-zqjn).

Rebuilt 2026-08-05, after the original was lost with the January-2026 baseline
(New 64.7% / Legacy 74.0% / -9.2%) it produced — leaving every section-extraction
fix since then unmeasured against the parser we plan to delete.

WHY IT LIVES HERE AND NOT IN ``tests/manual/``. The original was written to
``tests/manual/benchmark_section_extraction.py``, and **``tests/manual/`` is
gitignored** (``.gitignore`` line 58). That is the whole reason it vanished: it
could never have been committed from that path, and ``git add`` would have
refused it silently. Both ``zqjn`` and ``dt1f`` still name the old path, so
anyone following those references lands on a directory git will not track. This
file sits next to ``scoring.py`` and ``build_corpus.py`` instead — tracked,
purpose-built for corpus measurement, and beside the fixtures it measures. Do
not move it back.

WHAT IT ANSWERS. Removing ``edgar.files`` (``07lk.3``) means deleting
``ChunkedDocument``, and three consumers still lean on it: ``EightK.items`` uses
it as a Strategy-2 backfill, ``TenK``/``TenQ`` fall back to it, and ``TwentyF``
*prefers* it as the primary path. The gate for deleting it is evidence that the
new parser finds everything the legacy one finds. That is a differential
question, not a score question, so the differential is the primary output:

    both        found by new and legacy      (safe)
    new_only    found by new alone           (new parser wins)
    legacy_only found by legacy alone        <-- THE WORK LIST. Must reach zero
                                                 per form before that form's
                                                 fallback can be deleted.

The ``legacy_only`` set per form is the deliverable ``dt1f`` needs.

WHY OFFLINE. The original benchmark fetched 96 filings by accession, which made
it slow, rate-limited, and non-reproducible once a filing moved. This one reads
committed fixtures only, so it is deterministic and runnable in CI. The corpus is
also *era-stratified* through ``text_boundary_corpus`` (1996-2026 in five bands),
which matters here: the claim that legacy wins on old filer-agent HTML (``mpjh``
/ GH #870) is exactly the kind of thing a modern-only corpus cannot see.

READING THE NUMBERS — two traps this harness is built to avoid.

1. *8-K item granularity.* Legacy cannot express 8-K subitems: it reports Item
   8.01 as ``'Item 8'`` and Item 5.02 as ``'Item 5'``, while the new parser
   reports ``item_801`` / ``item_502``. Comparing those as strings would score a
   legacy *limitation* as a new-parser miss. Coverage is therefore compared at
   the coarsest granularity both parsers can express (the major number), and the
   subitem precision the new parser adds is reported separately rather than
   folded into the score.

2. *Filings where both find nothing.* Pre-2002 8-Ks are frequently plain-text
   bodies with no item structure at all; both parsers correctly return nothing.
   Counting those as a shared failure would drag both scores toward zero and hide
   the actual delta, so they are reported as ``both_blind`` and excluded from the
   per-form coverage rates.

USAGE
    python tests/fixtures/parser_corpus/parity_benchmark.py
    python tests/fixtures/parser_corpus/parity_benchmark.py --form 8-K --form 20-F
    python tests/fixtures/parser_corpus/parity_benchmark.py --json out.json

``tests/test_section_parity_ratchet.py`` imports ``measure``/``build_corpus``
from here and pins the result, so a regression fails a test rather than waiting
for someone to re-run the benchmark by hand.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import warnings
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set

# Anchored on this file's own directory, the way scoring.py does it, so the
# paths survive the file being moved again.
_CORPUS_DIR = Path(__file__).resolve().parent
FIXTURES = _CORPUS_DIR.parent
_REPO_ROOT = FIXTURES.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

# The legacy parser warns on every construction by design (it is deprecated and
# this benchmark exists to retire it). Silence it so the report stays readable.
warnings.filterwarnings("ignore")

from edgar.documents.config import ParserConfig  # noqa: E402
from edgar.documents.form_schema import get_form_schema  # noqa: E402
from edgar.documents.parser import HTMLParser  # noqa: E402
from edgar.files.htmltools import ChunkedDocument  # noqa: E402

HTML_CORPUS = FIXTURES / "html"
ERA_CORPUS = FIXTURES / "text_boundary_corpus"

# The tracked slice of the gate forms. ERA_CORPUS holds every 8-K and 20-F we
# measure but is gitignored (91 MB), so without this directory CI would guard
# 10-K and 10-Q and nothing else — leaving the two forms that actually gate the
# deletion unguarded, which is the opposite of this harness's purpose. Six
# filings, 2.8 MB: the four with known gaps plus one clean modern filing per
# form, so both a regression and a repair are visible in CI.
GATE_CORPUS = FIXTURES / "parity_gate"

# Forms that gate the deletion, in the order they block it. 10-K is included as
# the control: it was already at parity in January and a regression there would
# invalidate the rest of the run.
GATE_FORMS = ["8-K", "20-F", "10-Q", "10-K"]

# Canonical item lists, used only for the secondary coverage-vs-expected rate.
# 8-K is deliberately absent: an 8-K reports only the items it has, so there is
# no denominator and a percentage would be meaningless. The differential is the
# metric that works for every form.
EXPECTED_ITEMS: Dict[str, List[str]] = {
    "10-K": ["1", "1A", "1B", "1C", "2", "3", "4", "5", "6", "7", "7A", "8", "9",
             "9A", "9B", "9C", "10", "11", "12", "13", "14", "15", "16"],
    "10-Q": ["1", "1A", "2", "3", "4", "5", "6"],
    "20-F": ["1", "2", "3", "4", "4A", "5", "6", "7", "8", "9", "10", "11", "12",
             "13", "14", "15", "16A", "16B", "16C", "16D", "16E", "16F", "16G",
             "16H", "17", "18", "19"],
}

# Sections the new parser emits that are not items and must not enter the
# comparison (legacy has no equivalent concept).
NON_ITEM_SECTIONS = {"signatures", "cover", "cover_page", "exhibits", "toc"}


# ---------------------------------------------------------------------------
# Normalisation — the part that decides whether the numbers mean anything.
# ---------------------------------------------------------------------------

_NEW_ITEM_RE = re.compile(r"^(?:part_[ivx]+_)?item[_\s]*(\d+)([a-z]?)$", re.IGNORECASE)
_LEGACY_ITEM_RE = re.compile(r"^item\s*(\d+)(?:\.(\d+))?\s*([a-z]?)$", re.IGNORECASE)


def normalise_new(section_name: str, form: str) -> Optional[str]:
    """Map a new-parser section name to a canonical item key.

    ``part_ii_item_7a`` -> ``7A``. For 8-K the parser packs the subitem into the
    digits (``item_801`` is Item 8.01); we return the major number only, because
    that is the granularity legacy can also express. ``subitem_of`` below
    recovers the precision for the separate precision report.

    TWO KEY VOCABULARIES, AND MISSING ONE OF THEM COSTS REAL FILINGS. The parser
    names 10-K sections structurally (``part_ii_item_7``) or by friendly name
    (``mda``) depending on which detection strategy fired, and both are live on
    this corpus — ten friendly names appear across the 10-K fixtures. This
    function originally matched the structural form only, and silently returned
    None for the rest, which scored a *naming convention* as a parser miss.

    It cost `wfc/10k` ten items: its sections come back as ``business``,
    ``risk_factors``, ``mda`` and so on, all of them correct and all of them
    reachable through ``TenK.items`` and ``tenk['Item 1']``. The benchmark
    reported a near-total failure on a filing the parser handles perfectly, and
    that reading reached ``BASELINE_GAPS`` and the ratchet's prose, where it sat
    for a week as "a live bug on a modern large-bank filing".

    The friendly names are resolved through ``FormSchema.item_for_section_key``
    rather than a second table here, so the benchmark and the library cannot
    drift about what a section key means. The schema does not know the
    structural spellings, so the two are complements: the regex handles
    ``item_1``/``part_i_item_1``, the schema handles ``mda``, and together they
    cover every key the corpus produces. What neither resolves is genuinely not
    an item — ``signatures``, ``part_iv_signatures``, ``part_i``.
    """
    if section_name.lower() in NON_ITEM_SECTIONS:
        return None

    m = _NEW_ITEM_RE.match(section_name)
    if m:
        digits, suffix = m.group(1), m.group(2)
        if form == "8-K":
            # 8-K majors are single-digit (1-9), so a 3-digit group is major+minor.
            return digits[0] if len(digits) == 3 else digits
        return f"{digits}{suffix}".upper()

    # Friendly names ('mda', 'risk_factors'), via the library's own mapping.
    item = get_form_schema(form).item_for_section_key(section_name)
    if not item:
        return None
    if form == "8-K":
        return item.split(".")[0]
    return item.upper()


def subitem_of(section_name: str, form: str) -> Optional[str]:
    """The full 8-K subitem (``item_801`` -> ``8.01``), or None."""
    if form != "8-K":
        return None
    m = _NEW_ITEM_RE.match(section_name)
    if not m or len(m.group(1)) != 3:
        return None
    d = m.group(1)
    return f"{d[0]}.{d[1:]}"


def normalise_legacy(item_name: str, form: str) -> Optional[str]:
    """Map a legacy ``list_items()`` entry to the same canonical item key.

    ``'Item 7A'`` -> ``7A``. Legacy occasionally emits a decimal for 8-K; take
    the major number so both sides land on the same granularity.
    """
    m = _LEGACY_ITEM_RE.match(item_name.strip())
    if not m:
        return None
    major, _minor, suffix = m.group(1), m.group(2), m.group(3)
    if form == "8-K":
        return major
    return f"{major}{suffix}".upper()


# ---------------------------------------------------------------------------
# Corpus
# ---------------------------------------------------------------------------

def build_corpus(forms: List[str]) -> List[dict]:
    """Every *available* fixture for the requested forms, with provenance.

    Two sources with different shapes: the modern per-ticker tree (10-K/10-Q
    only, 2024-2025) and the era-stratified tree (all four gate forms, 1996-2026,
    three filings per era). Era is carried through to the report because the
    old-HTML bands are where legacy is claimed to win.

    Available, not committed — the distinction matters. ``html`` and
    ``parity_gate`` are tracked and present everywhere; ``text_boundary_corpus``
    is gitignored (91 MB) and present on developer machines only, so a CI run
    measures a smaller corpus than a local one. Callers must treat a filing that
    is not here as *unmeasured*, never as passing: the ratchet's first CI run
    read twelve missing fixtures as twelve fixed gaps.

    A filing present in both ``parity_gate`` and the era tree is measured once,
    from the tracked copy, so the two never disagree about what was checked.
    """
    entries: List[dict] = []
    seen: Set[tuple] = set()
    dir_for_form = {"10-K": "10k", "10-Q": "10q"}

    def add(form: str, path: Path, era: str, label: str) -> None:
        if (form, label) in seen:
            return
        seen.add((form, label))
        entries.append({"form": form, "path": path, "era": era, "label": label})

    for form in forms:
        subdir = dir_for_form.get(form)
        if subdir:
            for path in sorted(HTML_CORPUS.glob(f"*/{subdir}/*.html")):
                add(form, path, "modern", f"{path.parent.parent.name}/{subdir}")
        # Tracked gate-form slice first, so it wins the de-duplication and CI
        # and local runs measure the same file for these six.
        for path in sorted(GATE_CORPUS.glob(f"{form}/*.html")):
            add(form, path, "gate", path.stem)
        for path in sorted(ERA_CORPUS.glob(f"*/{form}/*.html")):
            add(form, path, path.parent.parent.name, path.stem)
    return entries


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------

def measure(entry: dict) -> dict:
    """Run both parsers over one fixture and return the per-filing differential.

    A parser that raises is recorded as an error with an empty item set rather
    than aborting the run: a crash on one filing is itself a finding, and on a
    100-fixture corpus it must not cost the other 99.
    """
    form = entry["form"]
    html = entry["path"].read_text(errors="ignore")

    new_items: Set[str] = set()
    new_subitems: Set[str] = set()
    new_error = None
    try:
        doc = HTMLParser(ParserConfig(form=form, detect_sections=True)).parse(html)
        for name in doc.sections:
            key = normalise_new(name, form)
            if key:
                new_items.add(key)
            sub = subitem_of(name, form)
            if sub:
                new_subitems.add(sub)
    except Exception as exc:  # noqa: BLE001 — a crash is a result, not a stop
        new_error = f"{type(exc).__name__}: {exc}"[:200]

    legacy_items: Set[str] = set()
    legacy_error = None
    try:
        for name in ChunkedDocument(html).list_items():
            key = normalise_legacy(name, form)
            if key:
                legacy_items.add(key)
    except Exception as exc:  # noqa: BLE001
        legacy_error = f"{type(exc).__name__}: {exc}"[:200]

    return {
        "form": form,
        "era": entry["era"],
        "label": entry["label"],
        "size": len(html),
        "new": sorted(new_items),
        "legacy": sorted(legacy_items),
        "new_subitems": sorted(new_subitems),
        "both": sorted(new_items & legacy_items),
        "new_only": sorted(new_items - legacy_items),
        "legacy_only": sorted(legacy_items - new_items),
        "both_blind": not new_items and not legacy_items,
        "new_error": new_error,
        "legacy_error": legacy_error,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _rate(found: int, expected: int) -> str:
    return f"{found / expected:.1%}" if expected else "—"


def report(results: List[dict]) -> None:
    by_form: Dict[str, List[dict]] = defaultdict(list)
    for r in results:
        by_form[r["form"]].append(r)

    print("\n" + "=" * 78)
    print("SECTION-EXTRACTION PARITY — new HTMLParser vs legacy ChunkedDocument")
    print("=" * 78)

    print("\n## Differential (the deletion gate)\n")
    hdr = (f"{'form':7}{'filings':>8}{'blind':>7}{'both':>7}{'new_only':>10}"
           f"{'legacy_only':>13}{'new tot':>9}{'legacy tot':>12}")
    print(hdr)
    print("-" * len(hdr))
    for form in GATE_FORMS:
        rs = by_form.get(form)
        if not rs:
            continue
        blind = sum(r["both_blind"] for r in rs)
        both = sum(len(r["both"]) for r in rs)
        new_only = sum(len(r["new_only"]) for r in rs)
        legacy_only = sum(len(r["legacy_only"]) for r in rs)
        print(f"{form:7}{len(rs):>8}{blind:>7}{both:>7}{new_only:>10}"
              f"{legacy_only:>13}{both + new_only:>9}{both + legacy_only:>12}")

    print("\n## Coverage vs the canonical item list\n")
    print("Filings where BOTH parsers found nothing are excluded — see the module")
    print("docstring. 8-K has no canonical list, so it has no rate.\n")
    hdr2 = f"{'form':7}{'scored':>8}{'new':>9}{'legacy':>9}{'delta':>9}"
    print(hdr2)
    print("-" * len(hdr2))
    for form in GATE_FORMS:
        rs = [r for r in by_form.get(form, []) if not r["both_blind"]]
        expected = EXPECTED_ITEMS.get(form)
        if not rs or not expected:
            if rs:
                print(f"{form:7}{len(rs):>8}{'—':>9}{'—':>9}{'—':>9}")
            continue
        denom = len(rs) * len(expected)
        exp = set(expected)
        new_hits = sum(len(set(r["new"]) & exp) for r in rs)
        legacy_hits = sum(len(set(r["legacy"]) & exp) for r in rs)
        delta = (new_hits - legacy_hits) / denom
        print(f"{form:7}{len(rs):>8}{_rate(new_hits, denom):>9}"
              f"{_rate(legacy_hits, denom):>9}{delta:>+9.1%}")

    print("\n## legacy_only — the work list for dt1f\n")
    print("Every entry here is a section the parser we plan to DELETE finds and")
    print("the one we plan to KEEP does not. Each form's list must reach zero")
    print("before that form's chunked_document fallback can be removed.\n")
    any_gap = False
    for form in GATE_FORMS:
        rs = [r for r in by_form.get(form, []) if r["legacy_only"]]
        if not rs:
            continue
        any_gap = True
        total = sum(len(r["legacy_only"]) for r in rs)
        print(f"  {form} — {total} missed across {len(rs)} filings")
        for r in rs:
            print(f"      [{r['era']}] {r['label']:<34} missing {r['legacy_only']}")
    if not any_gap:
        print("  (none — every item legacy finds, the new parser also finds)")

    print("\n## 8-K subitem precision\n")
    eight = by_form.get("8-K", [])
    if eight:
        with_sub = [r for r in eight if r["new_subitems"]]
        n_sub = sum(len(r["new_subitems"]) for r in with_sub)
        print(f"  Legacy reports 8-K items at major-number granularity only")
        print(f"  ('Item 8', never 'Item 8.01'). The new parser resolved")
        print(f"  {n_sub} subitems across {len(with_sub)} filings — a capability")
        print(f"  legacy does not have, and not visible in the scores above.")

    errors = [r for r in results if r["new_error"] or r["legacy_error"]]
    if errors:
        print("\n## Parser errors\n")
        for r in errors:
            who = "new" if r["new_error"] else "legacy"
            print(f"  [{r['form']} {r['label']}] {who}: {r['new_error'] or r['legacy_error']}")

    print("\n## Both-blind filings\n")
    blind = [r for r in results if r["both_blind"]]
    if blind:
        by_era: Dict[str, int] = defaultdict(int)
        for r in blind:
            by_era[f"{r['form']} {r['era']}"] += 1
        print(f"  {len(blind)} filings where NEITHER parser found an item:")
        for k in sorted(by_era):
            print(f"      {k}: {by_era[k]}")
        print("  Excluded from the coverage rates. Worth an eyeball — some are")
        print("  genuinely item-less (pre-2002 plain-text bodies), but a modern")
        print("  filing in this list is a real gap in both parsers.")
    else:
        print("  (none)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--form", action="append", choices=GATE_FORMS,
                    help="limit to one or more forms (repeatable)")
    ap.add_argument("--json", type=Path, help="write the per-filing results here")
    args = ap.parse_args()

    forms = args.form or GATE_FORMS
    corpus = build_corpus(forms)
    if not corpus:
        print("No fixtures found — is the fixture corpus present?", file=sys.stderr)
        return 1

    print(f"Measuring {len(corpus)} fixtures across {len(forms)} forms "
          f"(both parsers, offline)...", file=sys.stderr)
    results = []
    started = time.perf_counter()
    for i, entry in enumerate(corpus, 1):
        print(f"  [{i}/{len(corpus)}] {entry['form']:<5} {entry['label']}",
              file=sys.stderr)
        results.append(measure(entry))
    elapsed = time.perf_counter() - started

    report(results)
    print(f"\n({len(corpus)} fixtures in {elapsed:.1f}s)")

    if args.json:
        args.json.write_text(json.dumps(results, indent=2))
        print(f"Per-filing results written to {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
