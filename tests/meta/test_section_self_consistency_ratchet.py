"""Section self-consistency ratchet (edgartools-llmp.11).

No harness scored END boundaries against anything independent: the parity
ratchet measures item *presence*, and the boundary corpus pins text lengths
captured from the pipeline itself. This file adds a label-free necessary
condition for a correct slice and pins it:

    a section must not contain a LATER canonical item's heading at line start.

Every hit on the 2026-10-11 sweep was a real end-boundary defect (the next
item's anchor missing or placed after its heading text, two items sharing one
anchor and returning identical slices, the last item running into the exhibit
index), and only 10 of the 167 suspect sections carried any guardrail warning.
The research behind this is in
``docs-internal/research/section-boundary-deterministic-ceiling.md``.

WHAT THIS GUARDS. ``EMBED_BASELINE`` is, per fixture, the set of items whose
slice embeds a later heading, measured on 2026-10-11. The assertion is
**equality** for every fixture that is present, the same discipline as
``BASELINE_GAPS`` in ``test_section_parity_ratchet.py``: a new embed on any
fixture is a regression and fails; an embed that a fix has removed must also
be removed from the baseline in the same commit, otherwise the guard would
quietly loosen the next time that fixture regressed.

TWO CORPORA, AND ONLY ONE REACHES CI. ``html/`` and ``parity_gate/`` are
tracked; ``text_boundary_corpus/`` is gitignored and exists on developer
machines only. A baseline entry whose fixture is absent is *unmeasured*, never
fixed: those are partitioned out, and ``test_the_tracked_corpus_is_present``
fails if the tracked half goes missing, so "measured nothing" cannot read as
"nothing wrong".

Deliberately NOT asserted: ``opens_on_heading``. Title-only body headings
("Business", "PROPERTIES") and cross-reference-index slices legitimately fail
it, so it is a weak signal. It is reported by
``python tests/fixtures/parser_corpus/scoring.py`` for anyone labelling the
truth set, not ratcheted.
"""
import sys

import pytest

from tests.paths import FIXTURES_DIR

sys.path.insert(0, str(FIXTURES_DIR / "parser_corpus"))
import scoring  # noqa: E402

# Offline, re-parses ~100 fixtures through the live pipeline (~150s locally,
# less on CI where the era corpus is absent). Slow lane.
pytestmark = pytest.mark.slow


# Measured 2026-10-11 on main (7338aa33): 47 of 1,276 10-K item sections and
# 3 of 179 10-Q item sections embedded a later heading, across 20 fixtures.
# Re-measured the same day after each phase-B fix (edgartools-llmp.12):
#   anchor inside its heading (section_slicer.heading_block)   47 -> 19
#   unlisted / open-ended successor bound                       19 -> 11
# and 10-Q 3 -> 2. Keyed by fixture file stem so a ticker directory holding
# two fixtures measures both.
#
# What remains, so a fix knows which entries it should clear:
#
#   shared anchor, deliberate         so Items 7 (keeps 7A, a four-line
#       cross-reference set inside MD&A's first page, by design of the
#       heading-position split) and 11/12/13 (one 2,917-char Part III stub
#       the split cannot separate: no headings). The audit's R2 class.
#   last item, no successor heading   Item 15 on ge and 0001047469-03-011363
#       runs into the exhibit / financial statement index that follows it;
#       there is no Item 16 heading to stop at.
#   filer's own header in the F-pages 0001140361-10-014238 prints "PART I.
#       FINANCIAL INFORMATION / Item 1. Financial Statements" over its
#       statements. It was an Item 15 embed until the Item 8 trailing-
#       statements rescue gave the statements to Item 8 (llmp.12), and it
#       moved with them.
#   two-row contents list             ma Item 9C holds a two-row Part III
#       listing, below the three-row index threshold.
#   cross-reference at line start     0001193125-10-073212 Item 7 quotes
#       "ITEM 1A. Risk Factors - ..."; msft 10-Q Item 6 ends on "Items 3
#       and 4 are not applicable and have been omitted."; the plain-text
#       0000845875-03-000003 Item 1 hard-wraps "Items 11 and 13. In
#       addition, the Registrant reimburses ..." onto a line of its own.
#   pattern path                      0001193125-21-101193 Item 10 (a
#       pattern section that caught part of the TOC), 0001193125-21-082408
#       10-Q.
#
# CLEARED by heading_block (anchor after the heading text or inside its last
# word): 0001104659-10-017649 (13 items), 0001140361-10-014238 (12 of 13),
# 0001354488-16-006842 (2). CLEARED by the unlisted-successor bound: Item 15
# on axp, cvx, jnj, onds and 0001193125-21-101902 (Item 16 absent from the
# TOC), cvx Item 8 (open-ended after the incorporated-financials rescue), pg
# 10-Q Part I Item 4 (Part II Item 1 absent from the TOC). CLEARED by the
# ratchet's index-run exclusion: ma Item 4, 0001193125-21-101193 Item 5.
# CLEARED by filling a partial TOC from the cross-reference index before the
# pattern pass (llmp.12.2): ge Item 1, which was the index table itself.
# CLEARED by ending a pattern item at another item's header whatever its
# heading level (llmp.12.2): 0000950153-99-001234 Items 5 and 7. CLEARED by
# building a plain-text filing's blank-line blocks as paragraphs (llmp.12.1):
# 0000927356-01-000369 Item 7, whose 'mda' ran through Items 8-14 because
# their headings sat inside one 76k-char text node. Two
# further entries (915358 Item 9B, pg 10-K Item 15) were regex false
# positives on "Item 1.01"-style references and lowercase cross-references.
EMBED_BASELINE = {
    ("0000845875-03-000003", "10-K"): {"1"},
    ("0001047469-03-011363", "10-K"): {"15"},
    ("0001140361-10-014238", "10-K"): {"8"},
    ("0001193125-10-073212", "10-K"): {"7"},
    ("0001193125-21-082408", "10-Q"): {"1"},
    ("0001193125-21-101193", "10-K"): {"10"},
    # Retired from the held-out set with its labels (llmp.12.1): TechPrecision's
    # Item 9 runs into Item 9A, a miss the held-out report already recorded.
    ("0001410578-25-001537", "10-K"): {"9"},
    ("ge-10-k-2026-01-29", "10-K"): {"15"},
    ("msft-10-q-2025-04-30", "10-Q"): {"6"},
    ("so-10-k-2026-02-19", "10-K"): {"7", "11", "12", "13"},
}

# Baseline entries whose fixture is in the gitignored era corpus. Everything
# else in EMBED_BASELINE is tracked, and if one of those is absent the checkout
# is broken, not fixed.
ERA_ONLY_FIXTURES = {
    "0000845875-03-000003", "0001047469-03-011363", "0001140361-10-014238",
    "0001193125-21-082408",
}
TRACKED_BASELINE_FIXTURES = {k for k in EMBED_BASELINE if k[0] not in ERA_ONLY_FIXTURES}


@pytest.fixture(scope="module")
def corpus():
    return {(e["label"], e["form"]): e for e in scoring.consistency_corpus()}


@pytest.fixture(scope="module")
def measured(corpus):
    """{(label, form): frozenset(items that embed a later heading)}."""
    return {
        key: scoring.embed_set(scoring.measure_consistency(e["path"], e["form"]))
        for key, e in corpus.items()
    }


def test_the_tracked_corpus_is_present(corpus):
    missing = sorted(TRACKED_BASELINE_FIXTURES - set(corpus))
    assert not missing, (
        f"tracked fixtures missing from the checkout: {missing}. The ratchet "
        f"would otherwise read them as unmeasured and prove nothing."
    )
    assert sum(e["tracked"] for e in corpus.values()) >= 70


def test_no_new_embedded_heading(measured):
    """No fixture embeds a later item heading it did not embed at baseline."""
    regressions = {}
    for key, live in measured.items():
        new = live - EMBED_BASELINE.get(key, set())
        if new:
            regressions[key] = sorted(new)
    assert not regressions, (
        "sections now embed a LATER item's heading (end-boundary regression):\n"
        + "\n".join(f"  {k[0]} {k[1]}: items {v}" for k, v in sorted(regressions.items()))
    )


def test_fixed_embeds_are_removed_from_the_baseline(measured):
    """An entry a fix has cleared must leave the baseline in the same commit.

    Absent fixtures (the gitignored era corpus on CI) are unmeasured, not fixed,
    and are skipped here.
    """
    stale = {}
    for key, baseline in EMBED_BASELINE.items():
        if key not in measured:
            continue
        gone = baseline - measured[key]
        if gone:
            stale[key] = sorted(gone)
    assert not stale, (
        "these baseline entries no longer reproduce; remove them so the ratchet "
        "tightens:\n"
        + "\n".join(f"  {k[0]} {k[1]}: items {v}" for k, v in sorted(stale.items()))
    )


# ---------------------------------------------------------------------------
# Overlap over the whole corpus (edgartools-llmp.11, deliverable 3)
# ---------------------------------------------------------------------------
# test_section_boundary_corpus.py checks the sum-of-items / document ratio on
# the nine ground-truth tickers only, so a 1.53x Citigroup slipped past the
# test whose whole job is catching overlap (edgartools-rk02). This runs it over
# every fixture the ratchet measures, from the same parse. A filing whose
# sections come from the cross-reference index is exempt: one printed page
# legitimately serves several items there, so >1.0 is the expected arithmetic
# and not a boundary defect (Citi's Items 7 and 7A both cite pages 70-129).
OVERLAP_MAX = 1.10

# Measured 2026-10-11 on fix/llmp12-unlisted-item-bound: the filings over the
# cap that are not index-detected. Both are era-corpus (gitignored) filings on
# the pattern path; a new entrant anywhere is a boundary regression.
OVERLAP_BASELINE = {
    ("0001047469-03-011363", "10-K"),   # 1.24: pattern+toc, Item 15 runs into the F-pages
    ("0001193125-21-082408", "10-Q"),   # 1.11: pattern+toc
}


@pytest.fixture(scope="module")
def overlaps(corpus):
    """{(label, form): (ratio, exempt)} for every fixture present."""
    out = {}
    for key, e in corpus.items():
        m = scoring.document_measure(e["path"], e["form"])
        out[key] = (scoring.overlap_ratio_of(m), "index" in m["methods"])
    return out


def test_no_new_section_overlap(overlaps):
    over = {key: round(r, 2) for key, (r, exempt) in overlaps.items()
            if r > OVERLAP_MAX and not exempt}
    new = {k: v for k, v in over.items() if k not in OVERLAP_BASELINE}
    assert not new, (
        f"section text sums to more than {OVERLAP_MAX}x the document on filings "
        f"that were clean (a boundary overshoot pulled a neighbour's body in): {new}"
    )
    stale = sorted(k for k in OVERLAP_BASELINE if k in overlaps and k not in over)
    assert not stale, f"these OVERLAP_BASELINE entries now measure clean; remove them: {stale}"
