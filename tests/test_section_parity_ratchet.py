"""New-vs-legacy section-extraction parity ratchet (edgartools-zqjn).

The gate for deleting ``edgar.files``/``ChunkedDocument`` (``07lk.3``) is
evidence that the new parser finds everything the legacy one finds. This test
pins that evidence so it stays true between now and the 6.0 freeze window,
instead of being re-discovered by hand — which is how the January-2026 baseline
was lost in the first place.

The measurement lives in ``tests/fixtures/parser_corpus/parity_benchmark.py``;
run it directly for the full report, per-form coverage, and the work list.

WHAT THIS GUARDS. ``BASELINE_GAPS`` is every (form, filing, item) the legacy
parser finds and the new one misses, as measured on 2026-08-05 over 115 committed
fixtures. The assertion is a **subset** check, mirroring the anomaly census in
``test_section_boundary_corpus.py``: the live gap set may shrink freely, and any
*new* gap fails. So a fix that closes ``wfc/10k`` needs no change here, while a
change that breaks a currently-clean filing turns this red.

WHY SUBSET AND NOT EQUALITY. Equality would force every parser improvement to
edit this file, which makes the guard an obstacle rather than a safety net.
Tighten the baseline deliberately, in the commit that closes a gap, so the
recorded set keeps ratcheting down toward the empty set that unblocks deletion.

Deliberately NOT asserted: the coverage percentages. They move with the corpus
and read as precision the sample size does not support. The differential is the
thing the deletion decision actually rests on.
"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent / "fixtures" / "parser_corpus"))
import parity_benchmark  # noqa: E402

# Offline, but re-parses 115 fixtures through two parsers (~140s). Slow lane.
pytestmark = pytest.mark.slow


# Measured 2026-08-05 on main. Each entry is a section the parser we plan to
# DELETE finds and the one we plan to KEEP does not.
#
# Three shapes are visible here, and they are the work list for dt1f:
#
#   1. Two systematic pattern gaps on modern 10-Ks. Item 16 (Form 10-K Summary)
#      is missed on axp/cvx/jnj and one era filing; Item 1C (Cybersecurity, new
#      in 2023) on bac/jpm/tsla. Both look like detection-pattern holes rather
#      than per-filing damage, so each is likely one fix for several filings.
#   2. Five near-total failures, where the new parser returns almost nothing on
#      a filing legacy handles: wfc/10k (10 core items including 1, 1A, 7, 8 —
#      a live bug on a modern large-bank filing) and four era fixtures. The
#      20-F outlier 0001144204-10-017467 is EDGARizer-generated filer-agent
#      HTML: 12,880 <font> tags and zero <p>, the class edgartools-mpjh tracks.
#   3. Singletons, most of them pre-2015 HTML.
BASELINE_GAPS = {
    ("8-K", "0001104659-03-004925"): ["9"],
    ("8-K", "0001437749-16-028287"): ["2"],
    ("10-K", "0000927356-01-000369"): ["7"],
    ("10-K", "0000950153-99-001234"): ["1", "10", "11", "12", "13", "14", "2",
                                       "3", "4", "5", "6", "7", "7A", "8", "9"],
    ("10-K", "0001193125-10-073212"): ["9A"],
    ("10-K", "0001193125-21-101193"): ["1", "10", "11", "1B", "5"],
    ("10-K", "0001193125-21-101902"): ["16"],
    ("10-K", "0001376474-16-000635"): ["1", "10", "11", "12", "13", "14", "15",
                                       "1A", "1B", "2", "3", "4", "5", "6", "7",
                                       "7A", "8", "9", "9A", "9B"],
    ("10-K", "axp/10k"): ["16"],
    ("10-K", "bac/10k"): ["1C"],
    ("10-K", "cvx/10k"): ["16"],
    ("10-K", "jnj/10k"): ["16"],
    ("10-K", "jpm/10k"): ["1C"],
    ("10-K", "tsla/10k"): ["1C"],
    ("10-K", "wfc/10k"): ["1", "1A", "1B", "1C", "2", "3", "7", "7A", "8", "9A"],
    ("10-Q", "0001193125-21-082408"): ["1"],
    ("10-Q", "gs/10q"): ["5", "6"],
    ("20-F", "0000928385-01-500187"): ["7"],
    ("20-F", "0001062993-16-008650"): ["11", "16", "6"],
    ("20-F", "0001144204-10-017467"): ["1", "10", "11", "12", "13", "14", "15",
                                       "16A", "16B", "16C", "16D", "16E", "16F",
                                       "16G", "2", "3", "4A", "5", "6", "7", "8",
                                       "9"],
}

# Filings where NEITHER parser finds an item — 16 of them, every one pre-2009.
# Not a parity signal (the delta is zero), but pinned so a *modern* filing
# joining them is caught: that would be a gap in both parsers at once.
BASELINE_BOTH_BLIND = 16


@pytest.fixture(scope="module")
def measured():
    corpus = parity_benchmark.build_corpus(parity_benchmark.GATE_FORMS)
    assert corpus, "fixture corpus is missing — nothing was measured"
    return [parity_benchmark.measure(entry) for entry in corpus]


def _live_gaps(measured):
    return {
        (r["form"], r["label"]): set(r["legacy_only"])
        for r in measured if r["legacy_only"]
    }


class TestTheLegacyParserFindsNothingNew:
    """The deletion gate: no section may be legacy-only that was not already."""

    def test_no_new_parity_gap_appears(self, measured):
        baseline = {k: set(v) for k, v in BASELINE_GAPS.items()}
        live = _live_gaps(measured)

        regressions = {
            key: sorted(items - baseline.get(key, set()))
            for key, items in live.items()
            if items - baseline.get(key, set())
        }
        assert not regressions, (
            "the new parser lost ground against the parser we plan to delete: "
            f"{regressions}. Each entry is an item legacy finds and new does "
            "not, on a filing where that was not previously true."
        )

    def test_closed_gaps_are_recorded(self, measured):
        """The ratchet's other half: tighten the baseline when a gap closes.

        Not a failure of the parser — a failure to bank the win. Left un-banked,
        the baseline keeps permitting a gap that no longer exists, and the guard
        silently loosens.
        """
        baseline = {k: set(v) for k, v in BASELINE_GAPS.items()}
        live = _live_gaps(measured)

        stale = {
            key: sorted(items - live.get(key, set()))
            for key, items in baseline.items()
            if items - live.get(key, set())
        }
        assert not stale, (
            f"these recorded gaps are closed — remove them from BASELINE_GAPS "
            f"in the same commit that closed them: {stale}"
        )


class TestBothParsersStillSeeTheSameCorpus:

    def test_both_blind_set_does_not_grow(self, measured):
        blind = [r for r in measured if r["both_blind"]]
        assert len(blind) <= BASELINE_BOTH_BLIND, (
            f"{len(blind)} filings now yield no items from EITHER parser, up "
            f"from {BASELINE_BOTH_BLIND}: "
            f"{[(r['form'], r['label']) for r in blind]}"
        )

    def test_neither_parser_crashes(self, measured):
        errors = [(r["form"], r["label"], r["new_error"] or r["legacy_error"])
                  for r in measured if r["new_error"] or r["legacy_error"]]
        assert not errors, f"parser raised on: {errors}"
