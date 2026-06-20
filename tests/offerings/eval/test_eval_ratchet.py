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

    failures = []
    for facet, limits in thresholds.items():
        c = by_facet.get(facet)
        assert c, f"no results for facet {facet}"
        n = c["n"]
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
