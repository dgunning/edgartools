"""Section-boundary corpus regressions (edgartools-llmp.5).

The safety net the phased section-extraction refactor leans on. Three guards over
the canonical fixture corpus (offline — local HTML under tests/fixtures/html,
measured through the live pipeline by ``parser_corpus/scoring.py``):

1. **Ground truth** — exact per-item text lengths for a diverse, hand-verified
   set of healthy filings. Asserts specific values, not existence (Verification
   Constitution #2), across industries (tech / beverage / software / social /
   industrial / rail) and both 10-K and 10-Q.
2. **Overlap** — detected sections must not overlap or duplicate each other: the
   sum of item text stays at/under the whole-document text (the GH #871 bleed
   class — a boundary overshoot pulling a neighbour's body in).
3. **Anomaly census** — the set of size-anomalous filings must not grow beyond a
   recorded baseline, so a change that regresses a currently-healthy filing
   (across any form / detection method) turns this red.

Deliberately NOT a full golden-drift gate: ``manifest.json`` is a stale h44r-era
snapshot and current ``main`` already diverges from it with *both* fixes (jpm/gs/
xom via the rv86 + Phase work) and pre-existing regressions (edgartools-gegs).
A full regenerate-and-golden gate is future work once those regressions land; the
curated ground-truth above is the reliable subset that is stable today.
"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent / "fixtures" / "parser_corpus"))
import scoring  # noqa: E402

# Offline but multi-minute (the census re-parses the whole corpus): run in the
# slow lane, not test-fast. Explicit so conftest auto-marking doesn't tag it fast.
pytestmark = pytest.mark.slow


# ---------------------------------------------------------------------------
# 1. Ground truth — exact per-item text lengths, hand-verified, diverse.
# ---------------------------------------------------------------------------
# Values captured from the live pipeline and sanity-checked by hand (e.g. Apple's
# 10-K is famously concise — Item 1 Business ~16k, MD&A ~15k; Meta's Item 1A Risk
# Factors is enormous at ~188k). These filings are byte-stable across the whole
# section refactor, so exact assertions are both safe and maximally sensitive.
# If an intended parser change moves one, update the number in the same commit.
GROUND_TRUTH = {
    ("aapl", "10-K"): {"1": 15767, "1A": 68887, "7": 15358, "8": 59877},
    ("ko",   "10-K"): {"1": 54971, "1A": 90883, "7": 114821, "8": 234730},
    ("msft", "10-K"): {"1": 48799, "1A": 68824, "7": 49534, "8": 128086},
    ("meta", "10-K"): {"1": 40273, "1A": 188466, "7": 61019, "8": 124532},
    ("cat",  "10-K"): {"1": 39602, "1A": 53487, "7": 102423, "8": 181100},
    ("unp",  "10-K"): {"1": 27521, "1A": 32791, "7": 56358, "8": 95314},
    ("aapl", "10-Q"): {"1": 24903, "2": 19723},
    ("nvda", "10-Q"): {"1": 52671, "2": 32711},
    ("ko",   "10-Q"): {"1": 100831, "2": 77413},
}

# Filings whose detected sections size-anomalously today (oversize >300k, or an
# undersized substantial item). A mix of genuine boundary bugs and benign
# incorporation-by-reference (e.g. nvda/orcl Item 8 incorporated -> small). This
# is the *baseline*: the guard asserts the live set is a SUBSET of it, so new
# breakage fails while a fix that drops a filing from the set still passes.
# cvx 10-K was here until edgartools-gegs fixed its incorporation-by-reference
# recovery (Item 7/8 now recovered, Item 14 clamped); removed so a cvx regression
# re-trips this guard.
ANOMALY_BASELINE = {
    ("915358", "10-K"), ("bac", "10-K"),
    ("gbdc", "10-K"), ("gbdc", "10-Q"), ("gs", "10-K"), ("gs", "10-Q"),
    ("ibm", "10-K"), ("jpm", "10-K"), ("jpm", "10-Q"), ("ms", "10-K"),
    ("nflx", "10-K"), ("nvda", "10-K"), ("orcl", "10-K"), ("xom", "10-Q"),
}

OVERLAP_MAX = 1.10  # healthy filings cap at ~0.95; >1.0 means sections overlap.


def _fixture_rel(ticker: str, form: str) -> str:
    for e in scoring.load_manifest()["filings"]:
        if e["ticker"] == ticker and e["form"] == form:
            return e["fixture"]
    raise KeyError(f"{ticker} {form} not in corpus manifest")


@pytest.mark.parametrize("key", list(GROUND_TRUTH), ids=lambda k: f"{k[0]}-{k[1]}")
def test_ground_truth_item_lengths(key):
    """Exact per-item text lengths for hand-verified healthy filings."""
    ticker, form = key
    measured = scoring.measure_fixture(_fixture_rel(ticker, form), form)
    items = measured["items"]
    for item_key, expected in GROUND_TRUTH[key].items():
        assert item_key in items, f"{ticker} {form}: Item {item_key} not detected"
        actual = items[item_key]["text_len"]
        assert actual == expected, (
            f"{ticker} {form} Item {item_key}: expected {expected} chars, got {actual}. "
            f"If this is an intended parser change, update GROUND_TRUTH."
        )


@pytest.mark.parametrize("key", list(GROUND_TRUTH), ids=lambda k: f"{k[0]}-{k[1]}")
def test_no_section_overlap(key):
    """Sections must not overlap/duplicate (GH #871 bleed class)."""
    ticker, form = key
    measured = scoring.measure_fixture(_fixture_rel(ticker, form), form)
    ratio = scoring.overlap_ratio(measured)
    assert ratio <= OVERLAP_MAX, (
        f"{ticker} {form}: section text sums to {ratio:.2f}x the document — "
        f"sections overlap (a boundary overshoot pulled a neighbour's body in)."
    )


def test_anomaly_census_has_not_grown():
    """No currently-healthy filing has regressed into a size anomaly.

    Re-measures the whole corpus and asserts the size-anomalous set is a subset of
    ANOMALY_BASELINE — a new entrant means a fresh boundary regression.
    """
    live = set()
    for e in scoring.load_manifest()["filings"]:
        if "parse_error" in e:
            continue
        measured = scoring.measure_fixture(e["fixture"], e["form"])
        if scoring.auto_markers(measured, e["form"]):
            live.add((e["ticker"], e["form"]))
    new = live - ANOMALY_BASELINE
    assert not new, f"new size-anomalous filings (boundary regression): {sorted(new)}"
