"""
Ratchet guardrail for offerings extraction quality.

Runs the Tier A eval over the frozen corpus and asserts each facet meets its
locked threshold (coverage floor, bad_rate ceiling) in thresholds.json. A change
that drops coverage or ships garbage fails here.

Network-marked: it exercises real filings. Run with the network suite, not the
fast suite. When a genuine improvement lands, raise the floor in thresholds.json
in the same commit.
"""
import json
from pathlib import Path

import pytest

EVAL_DIR = Path(__file__).parent

# How many unfetchable entries still leave a sample worth judging. The corpus is
# 44 entries; a couple of transient SEC failures should not fail the run, but a
# handful means the rates are being computed over a sample small enough to move
# on its own, and the honest report is that nothing was measured.
MAX_UNAVAILABLE = 3


def _load():
    return (json.loads((EVAL_DIR / "corpus.json").read_text()),
            json.loads((EVAL_DIR / "thresholds.json").read_text())["facets"])


@pytest.mark.network
def test_offerings_eval_meets_thresholds():
    import sys
    sys.path.insert(0, str(EVAL_DIR))
    from run_eval import run, summarize

    corpus, thresholds = _load()
    by_facet = summarize(run(corpus))

    # A filing SEC would not serve is unmeasured, not a defect. Counting fetch
    # failures as 'bad' is what made this guardrail fail under full-suite load:
    # the suite shares one rate limiter, a busy run starves these 44 fetches, and
    # a quality ratchet then reports an extraction regression that never happened.
    # They are excluded from the rates and bounded separately here, so a degraded
    # run says "could not measure" instead of either passing on a rump sample or
    # blaming the extractor.
    unavailable = sum(c["unavailable"] for c in by_facet.values())
    measured = sum(c["n"] for c in by_facet.values())
    assert unavailable <= MAX_UNAVAILABLE, (
        f"{unavailable} of {unavailable + measured} corpus entries could not be "
        f"fetched from SEC, so this run did not measure extraction quality. "
        f"Rerun on a quiet connection; if it persists, the corpus has rotted and "
        f"the accessions need rechecking."
    )

    failures = []
    for facet, limits in thresholds.items():
        c = by_facet.get(facet)
        assert c, f"no results for facet {facet}"
        n = c["n"]
        assert n, (
            f"every entry for facet {facet} was unavailable "
            f"({c['unavailable']} fetch failures), so it was not measured"
        )
        # A justified 'deferred' (indeterminate pay-as-you-go shelf) is a correct
        # resolution, so it counts toward coverage alongside 'ok'.
        coverage = (c["ok"] + c["deferred"]) / n
        # 'suspect' = a Tier B oracle flagged the value as internally inconsistent;
        # count it as bad so the guardrail trips on likely-wrong values too.
        bad_rate = (c["bad"] + c["error"] + c["suspect"]) / n
        if coverage < limits["coverage_floor"]:
            failures.append(f"{facet}: coverage {coverage:.0%} < floor {limits['coverage_floor']:.0%}")
        if bad_rate > limits["bad_rate_ceiling"]:
            failures.append(f"{facet}: bad_rate {bad_rate:.0%} > ceiling {limits['bad_rate_ceiling']:.0%}")

    assert not failures, "Offerings eval regressed:\n  " + "\n  ".join(failures)
