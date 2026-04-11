"""
Unit tests for ``get_decision_threshold()`` — the chokepoint decision threshold
helper introduced in PR #764 Sub-project A.

The helper is **unwired** in Sub-project A; Sub-project B's chokepoint will
consume it when it lands. These tests pin the env-var parsing contract so that
future wiring can trust a single, documented semantics without surprises at
merge time.

Contract under test:
    - Unset env var             → normal threshold (0.005)
    - Exactly ``"1"``           → degraded threshold (0.01)
    - Any other value           → normal threshold (strict parsing)
    - Degraded is always wider  → invariant

The parsing is intentionally strict (``os.environ.get(...) == "1"``). Any
change to this contract (e.g., accepting ``"true"`` / ``"yes"``) should update
this test file so the break is caught at the test layer, not inside the
chokepoint's fast path.
"""

import pytest

from edgar.xbrl.standardization.tools.auto_eval import (
    _DECISION_THRESHOLD_DEGRADED,
    _DECISION_THRESHOLD_NORMAL,
    get_decision_threshold,
)


class TestDecisionThreshold:
    """Pin the EDGAR_DETERMINISM_DEGRADED env-var parsing contract."""

    def test_unset_env_var_returns_normal_threshold(self, monkeypatch):
        """Default path: no env var set → normal (narrow) threshold."""
        monkeypatch.delenv("EDGAR_DETERMINISM_DEGRADED", raising=False)
        assert get_decision_threshold() == _DECISION_THRESHOLD_NORMAL
        assert get_decision_threshold() == pytest.approx(0.005)

    def test_exactly_one_returns_degraded_threshold(self, monkeypatch):
        """Documented escape hatch: EDGAR_DETERMINISM_DEGRADED=1 → degraded."""
        monkeypatch.setenv("EDGAR_DETERMINISM_DEGRADED", "1")
        assert get_decision_threshold() == _DECISION_THRESHOLD_DEGRADED
        assert get_decision_threshold() == pytest.approx(0.01)

    @pytest.mark.parametrize(
        "value",
        [
            "0",      # false-ish int — strict parser must reject
            "true",   # common bool spelling — strict parser must reject
            "TRUE",   # uppercase variant
            "yes",    # another common bool spelling
            "",       # empty string — strict parser must reject
            " 1",     # leading space — strict parser must reject (no stripping)
            "1 ",     # trailing space — strict parser must reject
            "01",     # numeric padding — strict parser must reject
            "2",      # other int — strict parser must reject
        ],
    )
    def test_any_value_other_than_exact_one_falls_through_to_normal(
        self, monkeypatch, value
    ):
        """Strict ``== "1"`` parsing: anything else returns the normal threshold.

        If this test fails, the helper's parsing contract has drifted.
        Document the new contract here AND in
        ``edgar/xbrl/standardization/tools/auto_eval.py`` so Sub-project B's
        chokepoint can rely on a single source of truth.
        """
        monkeypatch.setenv("EDGAR_DETERMINISM_DEGRADED", value)
        assert get_decision_threshold() == _DECISION_THRESHOLD_NORMAL, (
            f"EDGAR_DETERMINISM_DEGRADED={value!r} unexpectedly triggered degraded "
            f"mode. Parsing is strict '== \"1\"' by design."
        )

    def test_degraded_threshold_is_wider_than_normal(self):
        """Invariant: degraded mode must widen the gate, never narrow it.

        Degraded mode is the escape hatch for measurement noise — widening the
        acceptance window is the whole point. If this ever flips, the chokepoint
        would become *more* strict under degraded conditions, which is the
        opposite of the intended behavior.
        """
        assert _DECISION_THRESHOLD_DEGRADED > _DECISION_THRESHOLD_NORMAL
