#!/usr/bin/env python
"""New-vs-legacy FULL-DOCUMENT markdown parity (edgartools-zqjn, GH #886).

The companion to ``parity_benchmark.py``. That one asks whether the new parser
finds the same *sections* as the legacy one; this one asks whether it renders
the same *document*. They gate different deletions and cannot answer for each
other — a parser can locate every item and still lose half the prose inside them.

WHAT IT GATES. ``Filing.markdown()`` is the last public rendering method still on
the legacy parser: ``_filings.py:1746`` goes ``html() -> get_clean_html ->
edgar.files.markdown.to_markdown``, while ``text()``/``view()``/``parse()`` moved
to ``edgar.documents`` long ago. Two things follow from that split:

  1. Images are silently dropped from ``Filing.markdown()`` (GH #886, ``n45i``).
     The new parser renders them — fixed on main in ``a2093248`` — so rerouting
     fixes it for free.
  2. Rerouting is a visible behaviour change, not a drop-in. A spot measurement
     on NVDA's FY2026 10-K had legacy at 429,312 chars and new at 343,760, about
     20% shorter, with table pipes falling 7,849 -> 5,123 and headings rising
     185 -> 233.

Shorter is the whole problem. It is either compaction (whitespace, padding and
redundant table scaffolding the new renderer does not emit) or content loss, and
**a character count cannot tell you which**. Neither can a diff: the two
renderers disagree about formatting on almost every line, so a diff of a real
10-K is 100% noise. So this harness does not measure size. It measures what
survives:

    number_recall   fraction of legacy's DISTINCT numeric values also in new
                    <-- THE GATE. Compaction cannot move it: no reformatting
                        makes a figure disappear.
    word_recall     fraction of legacy's word OCCURRENCES also in new, as a
                    multiset. ADVISORY ONLY — see below.

WHY NUMBERS GATE AND WORDS DO NOT. Numbers are high-cardinality and barely
repeat, so a dropped table takes its figures out of the document entirely and
the metric moves. The exhibit index is the worked example: losing it removes
10.11-10.26, which appear nowhere else, and number_recall drops immediately.

Words fail in both available flavours, which is worth stating so nobody
"fixes" this by switching them:

  * As a MULTISET they are too noisy. Legacy repeats ``Three Months Ended
    June 30`` above every chunk of a split table; the new renderer emits it
    once. That is compaction, and it shows up as hundreds of missing
    occurrences of ``ended``/``months``/``three``. It dominates the residual on
    every 10-Q in the corpus.
  * As a SET they are too blunt. Losing ABBV's entire exhibit index does not
    change the word set at all, because ``exhibit``, ``incorporated`` and
    ``reference`` all occur elsewhere in the filing.

So word_recall is reported, and a shortfall is worth reading, but it is not
allowed to fail the gate on its own. Its real job is covering the one thing
numbers cannot see: prose dropped from a passage that contained no figures.
Treat a word-only shortfall as "go and look", not as "not ready".

Structure counts (headings, table rows, images) are reported alongside but are
NOT part of the gate: they are expected to differ, and differ in the new
parser's favour. They are there to explain the size delta, not to score it.

READING THE NUMBERS — three traps this harness is built to avoid.

1. *The legacy fallback is not markdown.* When ``get_clean_html`` cannot root the
   HTML, ``Filing.markdown()`` falls back to ``text_to_markdown``, which wraps
   raw text in a ``<pre>`` block (``_markdown.py:107``). Scoring that against
   real markdown would manufacture a huge fake delta in whichever direction the
   fallback happens to run. Those filings are reported as ``legacy_degraded`` and
   excluded from the rates — and they are a finding in their own right, because
   they are filings where the thing we are trying to keep already produces
   nothing worth keeping.

2. *Formatting is not content* — and this trap is not hypothetical, it was the
   entire first result. Both renderers have habits that a naive token scan reads
   as content loss: the new one escapes markdown punctuation (``$0\\.24``), and
   the legacy one leaks raw ``<div align='center'>`` tags into its output. On
   AAPL's FY2024 10-K that alone produced 63 phantom missing numbers and a
   phantom 3.4% word shortfall, in a filing with no real loss at all. A third
   showed up across the corpus: legacy runs words together across tag boundaries
   (``endedmarch``, ``thethreemonthsendedjune``), which reads as prose the new
   renderer dropped when it is prose legacy invented. ``comparable`` and
   ``glued`` below neutralise all three, and the unadjusted word rate stays in
   the report beside the adjusted one so the correction can be audited rather
   than trusted. Read both docstrings before changing a recall number.

3. *A recall number alone is not actionable.* 0.97 is meaningless until you know
   whether the missing 3% is page numbers from a table of contents or line items
   from a balance sheet. Every shortfall therefore carries a sample of the
   actually-missing tokens, so the report can be adjudicated by eye rather than
   believed.

USAGE
    python tests/fixtures/parser_corpus/markdown_parity.py
    python tests/fixtures/parser_corpus/markdown_parity.py --form 10-K --limit 5
    python tests/fixtures/parser_corpus/markdown_parity.py --json out.json

The corpus is shared with ``parity_benchmark.py`` (``build_corpus``), so the same
caveat applies: ``text_boundary_corpus`` is gitignored, a CI run therefore
measures fewer fixtures than a local one, and a filing that is not present is
UNMEASURED, never passing.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import warnings
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_CORPUS_DIR = Path(__file__).resolve().parent
FIXTURES = _CORPUS_DIR.parent
_REPO_ROOT = FIXTURES.parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_CORPUS_DIR))

# The legacy parser warns on every construction by design.
warnings.filterwarnings("ignore")

from parity_benchmark import GATE_FORMS, build_corpus  # noqa: E402

from edgar.documents.config import ParserConfig  # noqa: E402
from edgar.documents.parser import HTMLParser  # noqa: E402
from edgar.files.html_documents import get_clean_html  # noqa: E402
from edgar.files.markdown import to_markdown  # noqa: E402

# The gate. Numbers only — see the module docstring for why words are advisory.
NUMBER_RECALL_GATE = 1.00
# Not a gate. The threshold below which a word shortfall is worth reading, which
# is a different thing from a threshold that blocks the reroute.
WORD_REVIEW_THRESHOLD = 0.98


# ---------------------------------------------------------------------------
# Rendering — each pipeline exactly as Filing.markdown() would reach it.
# ---------------------------------------------------------------------------

def render_legacy(html: str) -> Tuple[Optional[str], bool, Optional[str]]:
    """Render via the legacy pipeline. Returns (markdown, degraded, error).

    Mirrors ``Filing.markdown()`` (``_filings.py:1756-1766``) rather than calling
    it, because that method needs a live ``Filing`` and this harness is offline.
    ``degraded`` marks the ``<pre>``-wrapped fallback, which is not markdown and
    must not be scored — see trap 1 in the module docstring.
    """
    try:
        clean = get_clean_html(html)
        if not clean:
            return None, True, None
        md = to_markdown(clean)
        if not md:
            return None, True, None
        return md, False, None
    except Exception as exc:  # noqa: BLE001 — a crash is a result, not a stop
        return None, False, f"{type(exc).__name__}: {exc}"[:200]


def render_new(html: str, form: str) -> Tuple[Optional[str], Optional[str]]:
    """Render via the new pipeline: ``HTMLParser.parse(...).to_markdown()``."""
    try:
        doc = HTMLParser(ParserConfig(form=form)).parse(html)
        return doc.to_markdown(), None
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"[:200]


# ---------------------------------------------------------------------------
# Normalisation — the part that decides whether the numbers mean anything.
# ---------------------------------------------------------------------------

_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
_WORD_RE = re.compile(r"[a-z]{2,}")
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+\S", re.MULTILINE)
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)

_ESCAPE_RE = re.compile(r"\\([^\w\s])")
_HTML_TAG_RE = re.compile(r"<[^>]{1,200}>")


def comparable(md: str) -> str:
    """Strip each renderer's formatting habits so only content is compared.

    Both sides need this, and for opposite reasons — see trap 2. Measured on
    AAPL's FY2024 10-K, where the raw texts disagree on 63 numbers and neither
    disagreement is real:

    *The new renderer escapes markdown punctuation.* It emits ``$0\\.24``,
    ``2024\\.`` and ``10\\-K``. A naive number scan reads ``0\\.24`` as the two
    tokens ``0`` and ``24`` and reports the dividend as missing, when the
    sentence is rendered in full. Every one of those 63 was this.

    *The legacy renderer leaks raw HTML.* It emits literal
    ``<div align='center'>`` into its markdown, 146 times in that one filing,
    so ``div``/``align``/``center`` look like words the new parser dropped. It
    is the new parser that is right, and scoring it down for that would invert
    the finding.

    Neither transformation can hide a genuine loss: unescaping only rejoins
    tokens the new side already has, and tag-stripping only removes text the
    legacy side should never have emitted.
    """
    return _HTML_TAG_RE.sub(" ", _ESCAPE_RE.sub(r"\1", md))


def _canonical_number(token: str) -> str:
    """``3.050`` and ``3.05`` are the same rate; ``1,234`` and ``1234`` the same total.

    Compared by value rather than spelling, because the new renderer drops
    trailing zeros — it writes AAPL's ``3.050% Notes due 2029`` as ``3.05%``.
    That is a formatting choice with no effect on meaning, and comparing the
    strings scored every such coupon as a lost figure.

    Done by trimming rather than via ``float``, so a 20-digit share count is not
    quietly rounded by the very check meant to detect lost digits.
    """
    t = token.replace(",", "")
    if "." in t:
        t = t.rstrip("0").rstrip(".")
    return t or "0"


def numbers(md: str) -> set:
    """Distinct numeric values.

    A set, not a multiset: the same figure legitimately repeats (a total restated
    in a note, a year in every header), and renderers differ on how often
    boilerplate is emitted. Presence is the question — whether the document still
    contains the figure at all.
    """
    return {_canonical_number(m.group(0)) for m in _NUMBER_RE.finditer(md)}


def words(md: str) -> Counter:
    """Bare alphabetic tokens as a multiset.

    A multiset here precisely because prose does not legitimately vanish: if
    legacy renders a paragraph twice and new renders it once, that is a real
    difference and a set would hide it.
    """
    return Counter(_WORD_RE.findall(md.lower()))


def structure(md: str) -> Dict[str, int]:
    """Counts that explain a size delta without being part of the gate."""
    rows = _TABLE_ROW_RE.findall(md)
    return {
        "chars": len(md),
        "headings": len(_HEADING_RE.findall(md)),
        "table_rows": len(rows),
        "table_cells": sum(r.count("|") - 1 for r in rows),
        "images": len(_IMAGE_RE.findall(md)),
    }


def glued(token: str, vocabulary: frozenset) -> bool:
    """Is this legacy token two or more new-side words run together?

    The third contaminant, found the same way as the other two — by reading the
    shortfall samples instead of the totals. Legacy loses whitespace across tag
    boundaries and emits ``endedmarch``, ``percentagechange``,
    ``thethreemonthsendedjune``. The new renderer spaces them correctly, so every
    one of those reads as a word it dropped, when it is a word legacy invented.

    Note the direction: this is the *legacy* half of the word-boundary bug family
    (``edgartools-vfwp``), not the new parser's. Both parsers have had it.

    Split greedily against words the new side actually has, requiring at least
    two pieces of 3+ characters. Kept deliberately narrow: it only excuses a
    token that is fully explained by words already present, so genuinely lost
    prose cannot hide here — and the unadjusted rate stays in the report next to
    the adjusted one so the adjustment itself can be audited.
    """
    if len(token) < 6:
        return False
    pieces, i, n = 0, 0, len(token)
    while i < n:
        for j in range(n, i + 2, -1):
            if token[i:j] in vocabulary:
                pieces += 1
                i = j
                break
        else:
            return False
    return pieces >= 2


def _recall(legacy, new) -> float:
    """Fraction of legacy retained in new. Vacuously 1.0 if legacy had none."""
    if isinstance(legacy, Counter):
        total = sum(legacy.values())
        if not total:
            return 1.0
        return sum(min(c, new[t]) for t, c in legacy.items()) / total
    if not legacy:
        return 1.0
    return len(legacy & new) / len(legacy)


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------

def measure_markdown(entry: dict) -> dict:
    """Render one fixture both ways and return the content differential."""
    form = entry["form"]
    html = entry["path"].read_text(errors="ignore")

    legacy_md, degraded, legacy_error = render_legacy(html)
    new_md, new_error = render_new(html, form)

    row = {
        "form": form,
        "era": entry["era"],
        "label": entry["label"],
        "size": len(html),
        "legacy_degraded": degraded,
        "legacy_error": legacy_error,
        "new_error": new_error,
        "scored": bool(legacy_md and new_md),
    }

    if not row["scored"]:
        row.update({
            "legacy": structure(legacy_md) if legacy_md else None,
            "new": structure(new_md) if new_md else None,
            "number_recall": None,
            "word_recall": None,
            "word_recall_raw": None,
            "glued_tokens": 0,
            "missing_numbers": [],
            "missing_words": [],
            "missing_number_total": 0,
            "missing_word_total": 0,
        })
        return row

    legacy_cmp, new_cmp = comparable(legacy_md), comparable(new_md)
    legacy_nums, new_nums = numbers(legacy_cmp), numbers(new_cmp)
    legacy_words, new_words = words(legacy_cmp), words(new_cmp)
    missing_nums = legacy_nums - new_nums
    missing_words = {w: c - new_words[w] for w, c in legacy_words.items()
                     if c > new_words[w]}

    # Discount legacy's own glued tokens, and report both rates so the size of
    # the adjustment is visible rather than assumed.
    vocabulary = frozenset(new_words)
    glue = {w: c for w, c in missing_words.items() if glued(w, vocabulary)}
    real_missing = {w: c for w, c in missing_words.items() if w not in glue}
    legacy_total = sum(legacy_words.values())
    word_recall = _recall(legacy_words, new_words)
    word_recall_adj = (
        1.0 if not legacy_total
        else 1.0 - sum(real_missing.values()) / legacy_total
    )

    row.update({
        "legacy": structure(legacy_md),
        "new": structure(new_md),
        "number_recall": _recall(legacy_nums, new_nums),
        "word_recall_raw": word_recall,
        "word_recall": word_recall_adj,
        "glued_tokens": sum(glue.values()),
        # Samples, not the full sets: this is adjudication material (trap 3),
        # and a 10-K can drop thousands of tokens when it drops anything.
        "missing_numbers": sorted(missing_nums)[:15],
        "missing_words": [w for w, _ in Counter(real_missing).most_common(15)],
        "missing_number_total": len(missing_nums),
        "missing_word_total": sum(real_missing.values()),
    })
    return row


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _pct(x: Optional[float]) -> str:
    return "—" if x is None else f"{x:.1%}"


def report(results: List[dict]) -> None:
    by_form: Dict[str, List[dict]] = defaultdict(list)
    for r in results:
        by_form[r["form"]].append(r)

    print("\n" + "=" * 78)
    print("FULL-DOCUMENT MARKDOWN PARITY — new HTMLParser vs legacy to_markdown")
    print("=" * 78)

    print("\n## Content recall (the reroute gate)\n")
    print("Compaction leaves both columns at 100%. Anything below is content the")
    print("legacy renderer emits and the new one does not.\n")
    hdr = (f"{'form':7}{'scored':>8}{'numbers':>10}{'words':>9}{'(raw)':>9}"
           f"{'clean':>8}{'degraded':>10}{'errors':>8}")
    print(hdr)
    print("-" * len(hdr))
    for form in GATE_FORMS:
        rs = by_form.get(form)
        if not rs:
            continue
        scored = [r for r in rs if r["scored"]]
        clean = sum(1 for r in scored
                    if r["number_recall"] >= NUMBER_RECALL_GATE)
        degraded = sum(1 for r in rs if r["legacy_degraded"])
        errors = sum(1 for r in rs if r["new_error"] or r["legacy_error"])
        n_rec = (min(r["number_recall"] for r in scored) if scored else None)
        w_rec = (min(r["word_recall"] for r in scored) if scored else None)
        w_raw = (min(r["word_recall_raw"] for r in scored) if scored else None)
        print(f"{form:7}{len(scored):>8}{_pct(n_rec):>10}{_pct(w_rec):>9}"
              f"{_pct(w_raw):>9}{clean:>8}{degraded:>10}{errors:>8}")
    print("\n(numbers/words columns are the WORST filing in the form, not the mean —")
    print(" a mean over a corpus hides the one filing that would regress a user.)")
    glue_total = sum(r.get("glued_tokens", 0) for r in results if r["scored"])
    print(f"\n(words vs (raw): (raw) is before discounting {glue_total} tokens that")
    print(" LEGACY glued together — 'endedmarch', 'thethreemonthsendedjune'. The new")
    print(" renderer spaces them correctly and was being charged for it. See glued().)")

    print("\n## Size delta — descriptive only, NOT the gate\n")
    hdr2 = (f"{'form':7}{'chars new/legacy':>19}{'rows':>10}"
            f"{'headings':>11}{'images':>16}")
    print(hdr2)
    print("-" * len(hdr2))
    for form in GATE_FORMS:
        scored = [r for r in by_form.get(form, []) if r["scored"]]
        if not scored:
            continue
        lc = sum(r["legacy"]["chars"] for r in scored)
        nc = sum(r["new"]["chars"] for r in scored)
        lr = sum(r["legacy"]["table_rows"] for r in scored)
        nr = sum(r["new"]["table_rows"] for r in scored)
        lh = sum(r["legacy"]["headings"] for r in scored)
        nh = sum(r["new"]["headings"] for r in scored)
        li = sum(r["legacy"]["images"] for r in scored)
        ni = sum(r["new"]["images"] for r in scored)
        ratio = f"{nc / lc:.2f}x" if lc else "—"
        print(f"{form:7}{ratio:>19}{f'{nr}/{lr}':>10}"
              f"{f'{nh}/{lh}':>11}{f'{ni}/{li}':>16}")
    print("\n(images: legacy renders none at all — that is GH #886, and it is the")
    print(" reason this reroute is worth doing rather than merely tidy.)")

    print("\n## Shortfalls — the work list\n")
    print("Each line is a filing where rerouting Filing.markdown() would today")
    print("lose content. The sample says WHAT was lost, so you can tell a table")
    print("of contents' page numbers from a balance sheet's line items.\n")
    any_gap = False
    for form in GATE_FORMS:
        rs = [r for r in by_form.get(form, [])
              if r["scored"] and (r["number_recall"] < NUMBER_RECALL_GATE
                                  or r["word_recall"] < WORD_REVIEW_THRESHOLD)]
        if not rs:
            continue
        any_gap = True
        print(f"  {form} — {len(rs)} filings below gate")
        for r in sorted(rs, key=lambda x: x["number_recall"]):
            print(f"      [{r['era']}] {r['label']:<34} "
                  f"num {r['number_recall']:.1%} ({r['missing_number_total']} lost)  "
                  f"word {r['word_recall']:.1%} ({r['missing_word_total']} lost)")
            if r["missing_numbers"]:
                print(f"          numbers: {', '.join(r['missing_numbers'][:10])}")
            if r["missing_words"]:
                print(f"          words:   {', '.join(r['missing_words'][:10])}")
    if not any_gap:
        print("  (none — every filing clears both gates)")

    degraded = [r for r in results if r["legacy_degraded"]]
    print("\n## Legacy-degraded filings\n")
    if degraded:
        print(f"  {len(degraded)} filings where the LEGACY pipeline produced no")
        print("  markdown at all and Filing.markdown() would fall back to a <pre>")
        print("  block of raw text. Excluded from the rates. These are an argument")
        print("  FOR the reroute, not against it — check whether the new parser")
        print("  rendered them properly:\n")
        for r in degraded:
            new_chars = r["new"]["chars"] if r["new"] else 0
            verdict = "new OK" if new_chars > 1000 else "new ALSO empty"
            print(f"      [{r['form']} {r['era']}] {r['label']:<34} "
                  f"new={new_chars} chars  ({verdict})")
    else:
        print("  (none)")

    errors = [r for r in results if r["new_error"] or r["legacy_error"]]
    print("\n## Renderer errors\n")
    if errors:
        for r in errors:
            who = "new" if r["new_error"] else "legacy"
            print(f"  [{r['form']} {r['label']}] {who}: "
                  f"{r['new_error'] or r['legacy_error']}")
    else:
        print("  (none)")

    scored_all = [r for r in results if r["scored"]]
    if scored_all:
        clean = sum(1 for r in scored_all
                    if r["number_recall"] >= NUMBER_RECALL_GATE)
        print("\n## Verdict\n")
        print(f"  {clean}/{len(scored_all)} scored filings retain every number "
              f"legacy renders.")
        if clean == len(scored_all):
            print("  Filing.markdown() can be rerouted: the size delta is compaction.")
        else:
            print("  NOT ready to reroute — see the work list above.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--form", action="append", choices=GATE_FORMS,
                    help="limit to one or more forms (repeatable)")
    ap.add_argument("--limit", type=int,
                    help="measure at most N fixtures per form (for a quick look)")
    ap.add_argument("--json", type=Path, help="write the per-filing results here")
    args = ap.parse_args()

    forms = args.form or GATE_FORMS
    corpus = build_corpus(forms)
    if args.limit:
        per_form: Dict[str, int] = defaultdict(int)
        kept = []
        for entry in corpus:
            if per_form[entry["form"]] < args.limit:
                per_form[entry["form"]] += 1
                kept.append(entry)
        corpus = kept
    if not corpus:
        print("No fixtures found — is the fixture corpus present?", file=sys.stderr)
        return 1

    print(f"Rendering {len(corpus)} fixtures twice each (offline)...",
          file=sys.stderr)
    results = []
    started = time.perf_counter()
    for i, entry in enumerate(corpus, 1):
        print(f"  [{i}/{len(corpus)}] {entry['form']:<5} {entry['label']}",
              file=sys.stderr)
        results.append(measure_markdown(entry))
    elapsed = time.perf_counter() - started

    report(results)
    print(f"\n({len(corpus)} fixtures in {elapsed:.1f}s)")

    if args.json:
        args.json.write_text(json.dumps(results, indent=2))
        print(f"Per-filing results written to {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
