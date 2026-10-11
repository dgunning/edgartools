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


# Measured 2026-10-11 on main (7338aa33). 47 of 1,276 10-K item sections and
# 3 of 179 10-Q item sections embed a later heading. Keyed by fixture file
# stem so a ticker directory holding two fixtures measures both.
#
# Mechanisms, so a fix knows which entries it should clear:
#
#   anchor AFTER the heading text   0001104659-10-017649, 0001140361-10-014238
#       (2010, Bowne-style). The <a name> is the last child of the <h2>, after
#       "ITEM 2. PROPERTIES.", so every slice starts after its own heading and
#       ends after the next one. Same family as GH #1369 (anchor nested in
#       the heading), different position.
#   shared anchor, identical slices  so Items 11/12/13 (one 2,917-char slice
#       embedding Item 10), so Item 7 embedding 7A. The audit's R2 class.
#   missing end anchor, run-on       ma Item 4 (5,502 chars, embeds 5-9C: ran
#       into Part III), ma Item 9C, 0001193125-21-101193 Items 5 and 10.
#   last item swallows what follows  Item 15 embedding Item 16 on axp, cvx,
#       jnj, onds, pg, 0001193125-21-101902; ge and 0001047469-03-011363 Item
#       15 embedding the whole exhibit / cross-reference index.
#   incorporation by reference       cvx Item 8 (embeds 15, 16), the shape
#       edgartools-gegs recovered; the end still overruns.
#   pattern path, pre-2002           0000950153-99-001234 Item 5.
#   10-Q                             msft Item 6 (Part II) embedding a Part I
#       Item 3 heading; pg Item 4 embedding Item 1; 0001193125-21-082408.
EMBED_BASELINE = {
    ("0000950153-99-001234", "10-K"): {"5"},
    ("0001047469-03-011363", "10-K"): {"15"},
    ("0001104659-10-017649", "10-K"): {"1", "1A", "2", "3", "7", "7A", "8", "9A",
                                       "10", "11", "12", "13", "14"},
    ("0001140361-10-014238", "10-K"): {"1", "2", "3", "5", "7", "9A", "10", "11",
                                       "12", "13", "14", "15"},
    ("0001193125-10-073212", "10-K"): {"7"},
    ("0001193125-21-082408", "10-Q"): {"1"},
    ("0001193125-21-101193", "10-K"): {"5", "10"},
    ("0001193125-21-101902", "10-K"): {"15"},
    ("0001354488-16-006842", "10-K"): {"1", "1A"},
    ("915358-10-k-2025-08-27", "10-K"): {"9B"},
    ("axp-10-k-2025-02-07", "10-K"): {"15"},
    ("cvx-10-k-2025-02-21", "10-K"): {"8", "15"},
    ("ge-10-k-2026-01-29", "10-K"): {"15"},
    ("jnj-10-k-2025-02-13", "10-K"): {"15"},
    ("ma-10-k-2025-02-12", "10-K"): {"4", "9C"},
    ("msft-10-q-2025-04-30", "10-Q"): {"6"},
    ("onds-10-k-2026-03-30", "10-K"): {"15"},
    ("pg-10-k-2025-08-04", "10-K"): {"15"},
    ("pg-10-q-2025-04-24", "10-Q"): {"4"},
    ("so-10-k-2026-02-19", "10-K"): {"7", "11", "12", "13"},
}

# Baseline entries whose fixture is in the gitignored era corpus. Everything
# else in EMBED_BASELINE is tracked, and if one of those is absent the checkout
# is broken, not fixed.
ERA_ONLY_FIXTURES = {
    "0001047469-03-011363", "0001104659-10-017649", "0001140361-10-014238",
    "0001193125-21-082408", "0001193125-21-101902", "0001354488-16-006842",
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
