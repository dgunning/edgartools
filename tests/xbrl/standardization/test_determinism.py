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
    """
    result_a = compute_cqs(eval_cohort=DETERMINISM_TEST_COHORT, snapshot_mode=True)
    result_b = compute_cqs(eval_cohort=DETERMINISM_TEST_COHORT, snapshot_mode=True)

    # Both runs must have evaluated the same set of companies
    assert set(result_a.company_scores.keys()) == set(result_b.company_scores.keys()), (
        f"Determinism check failed: cohort membership diverged between runs. "
        f"Run A: {sorted(result_a.company_scores.keys())}. "
        f"Run B: {sorted(result_b.company_scores.keys())}."
    )

    deltas = []
    for ticker in DETERMINISM_TEST_COHORT:
        a = result_a.company_scores[ticker].ef_cqs
        b = result_b.company_scores[ticker].ef_cqs
        deltas.append((ticker, abs(a - b), a, b))

    max_delta = max(d[1] for d in deltas)

    # Print observed deltas so the noise floor is captured in CI logs.
    # This output is what informs the DETERMINISM_THRESHOLD constant.
    print(f"\n[determinism] max per-company EF-CQS delta: {max_delta:.10f}")
    print(f"[determinism] threshold: {DETERMINISM_THRESHOLD:.10f}")
    for ticker, delta, a, b in sorted(deltas, key=lambda d: -d[1]):
        marker = " <-- max" if delta == max_delta else ""
        print(f"[determinism]   {ticker:<6} delta={delta:.10f}  a={a:.6f}  b={b:.6f}{marker}")

    assert max_delta < DETERMINISM_THRESHOLD, (
        f"Determinism check failed: max per-company EF-CQS delta {max_delta:.6f} "
        f"exceeds threshold {DETERMINISM_THRESHOLD:.6f}. "
        f"Back-to-back runs with identical config produced different scores. "
        f"Either fix the determinism bug (FactQuery ordering, dict iteration, "
        f"FP reduction order) OR set EDGAR_DETERMINISM_DEGRADED=1 to widen the "
        f"chokepoint decision threshold from 0.005 to 0.01. "
        f"Per-ticker deltas: {[(t, round(d, 10)) for t, d, _, _ in deltas]}"
    )
