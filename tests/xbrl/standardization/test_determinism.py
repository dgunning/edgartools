"""
Determinism CI gate (Sub-project A).

The autonomous expansion pipeline is only safe if back-to-back runs with identical
config produce bit-identical EF-CQS scores. Without that guarantee, every safety
gate downstream — the chokepoint, the regression gate, the typed-action replay —
is making decisions off measurement noise.

This test runs ``compute_cqs`` twice on the fixed ``DETERMINISM_TEST_COHORT`` and
asserts that the maximum per-company EF-CQS delta is below ``DETERMINISM_THRESHOLD``.

If the assertion fails, the failure message points the operator at two options:
1. Fix the determinism bug (most common: FactQuery ordering, dict iteration order,
   FP reduction order in mean_variance / coverage_rate aggregation).
2. Set ``EDGAR_DETERMINISM_DEGRADED=1`` in the environment as the documented escape
   hatch — this widens the chokepoint decision threshold from 0.005 → 0.01.

This test joins the existing nightly regression suite via ``@pytest.mark.regression``;
``regression-tests.yml`` already filters on that marker, so no CI workflow changes
are needed.
"""

import pytest

from edgar.xbrl.standardization.tools.auto_eval import (
    DETERMINISM_TEST_COHORT,
    DETERMINISM_THRESHOLD,
    compute_cqs,
)


@pytest.mark.regression
@pytest.mark.determinism
@pytest.mark.slow
def test_extraction_is_deterministic():
    """Determinism gate: identical config must produce bit-identical EF-CQS.

    Ground-truth assertion: every ticker in DETERMINISM_TEST_COHORT must have a
    per-company EF-CQS delta below DETERMINISM_THRESHOLD across two back-to-back
    runs of compute_cqs with snapshot_mode=True (no network, no clock dependence).

    Asserts on BOTH the lenient ``ef_cqs`` (current decision gate) and the
    observation-only ``ef_cqs_strict`` (future decision gate after the Sub-
    project A cut-over). Lenient and strict share an ef_pass_count numerator
    and should co-move, but pinning both pre-cutover guarantees the strict
    field is also bit-identical — otherwise the first strict-mode run after
    the gate flip could surprise us with nondeterminism that was hidden
    behind the laundering denominator.
    """
    result_a = compute_cqs(eval_cohort=DETERMINISM_TEST_COHORT, snapshot_mode=True)
    result_b = compute_cqs(eval_cohort=DETERMINISM_TEST_COHORT, snapshot_mode=True)

    # Both runs must have evaluated the same set of companies
    assert set(result_a.company_scores.keys()) == set(result_b.company_scores.keys()), (
        f"Determinism check failed: cohort membership diverged between runs. "
        f"Run A: {sorted(result_a.company_scores.keys())}. "
        f"Run B: {sorted(result_b.company_scores.keys())}."
    )

    # Track lenient and strict deltas in parallel. Either field going
    # non-deterministic fails the gate.
    deltas = []
    for ticker in DETERMINISM_TEST_COHORT:
        ca = result_a.company_scores[ticker]
        cb = result_b.company_scores[ticker]
        lenient_delta = abs(ca.ef_cqs - cb.ef_cqs)
        strict_delta = abs(ca.ef_cqs_strict - cb.ef_cqs_strict)
        deltas.append(
            (ticker, lenient_delta, strict_delta, ca.ef_cqs, cb.ef_cqs,
             ca.ef_cqs_strict, cb.ef_cqs_strict)
        )

    max_lenient_delta = max(d[1] for d in deltas)
    max_strict_delta = max(d[2] for d in deltas)
    max_delta = max(max_lenient_delta, max_strict_delta)

    # Print observed deltas so the noise floor is captured in CI logs.
    # This output is what informs the DETERMINISM_THRESHOLD constant.
    print(f"\n[determinism] max per-company ef_cqs        delta: {max_lenient_delta:.10f}")
    print(f"[determinism] max per-company ef_cqs_strict delta: {max_strict_delta:.10f}")
    print(f"[determinism] threshold: {DETERMINISM_THRESHOLD:.10f}")
    for ticker, ld, sd, la, lb, sa, sb in sorted(deltas, key=lambda d: -(max(d[1], d[2]))):
        marker = " <-- max" if max(ld, sd) == max_delta else ""
        print(
            f"[determinism]   {ticker:<6} "
            f"ef_cqs Δ={ld:.10f} (a={la:.6f} b={lb:.6f})  "
            f"strict Δ={sd:.10f} (a={sa:.6f} b={sb:.6f}){marker}"
        )

    assert max_delta < DETERMINISM_THRESHOLD, (
        f"Determinism check failed: max per-company delta {max_delta:.6f} "
        f"exceeds threshold {DETERMINISM_THRESHOLD:.6f} "
        f"(lenient max={max_lenient_delta:.6f}, strict max={max_strict_delta:.6f}). "
        f"Back-to-back runs with identical config produced different scores. "
        f"Either fix the determinism bug (FactQuery ordering, dict iteration, "
        f"FP reduction order) OR set EDGAR_DETERMINISM_DEGRADED=1 to widen the "
        f"chokepoint decision threshold from 0.005 to 0.01. "
        f"Per-ticker deltas (ticker, lenient, strict): "
        f"{[(t, round(ld, 10), round(sd, 10)) for t, ld, sd, *_ in deltas]}"
    )
