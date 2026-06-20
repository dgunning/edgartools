"""
Fast unit tests for the eval harness's frontier (known-gap) accounting.

Frontier entries document coverage gaps with hand-verified ground truth but must
NOT count against the ratcheted coverage/bad_rate floors — otherwise every newly
added gap case would lower the floor and defeat the regression guard. These tests
pin that partition without touching the network.
"""
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).parent
sys.path.insert(0, str(EVAL_DIR))

from run_eval import summarize  # noqa: E402


def _r(facet, bucket, frontier=False):
    return {"facet": facet, "bucket": bucket, "frontier": frontier}


def test_summarize_excludes_frontier_by_default():
    results = [
        _r("fee_capacity", "ok"),
        _r("fee_capacity", "ok"),
        _r("fee_capacity", "null", frontier=True),   # gap — must not count
        _r("fee_capacity", "null", frontier=True),
    ]
    by_facet = summarize(results)
    assert by_facet["fee_capacity"]["n"] == 2
    assert by_facet["fee_capacity"]["ok"] == 2
    assert by_facet["fee_capacity"]["ok"] / by_facet["fee_capacity"]["n"] == 1.0


def test_summarize_frontier_only_view():
    results = [
        _r("fee_capacity", "ok"),
        _r("fee_capacity", "null", frontier=True),
        _r("fee_capacity", "deferred", frontier=True),
    ]
    fb = summarize(results, include_frontier=True)
    assert fb["fee_capacity"]["n"] == 2
    assert fb["fee_capacity"]["null"] == 1
    assert fb["fee_capacity"]["deferred"] == 1
    assert "ok" not in fb["fee_capacity"]  # the supported entry is not in this view


def test_frontier_gap_does_not_drag_ratchet():
    """A facet at 100% on supported scope stays 100% even with frontier nulls."""
    supported = [_r("fee_capacity", "ok") for _ in range(5)]
    gaps = [_r("fee_capacity", "null", frontier=True) for _ in range(10)]
    by_facet = summarize(supported + gaps)
    coverage = by_facet["fee_capacity"]["ok"] / by_facet["fee_capacity"]["n"]
    assert coverage == 1.0
