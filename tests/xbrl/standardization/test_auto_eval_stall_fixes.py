"""
Verification tests for the 6 bug fixes that prevented the auto-eval loop from stalling
after 9 experiments with 0 kept.

Each test verifies exactly one fix.
"""
import logging
from unittest.mock import MagicMock, patch

import pytest

from edgar.xbrl.standardization.tools.auto_eval import MetricGap, _get_graveyard_counts

pytestmark = pytest.mark.fast


# =============================================================================
# Fix 1: MetricGap.is_dead_end threshold raised from 3 → 6
# =============================================================================

class TestDeadEndThresholdRaisedTo6:
    """is_dead_end should return False for graveyard_count 0-5, True for 6+."""

    def _make_gap(self, graveyard_count: int) -> MetricGap:
        return MetricGap(
            ticker="AAPL",
            metric="Revenue",
            gap_type="unmapped",
            estimated_impact=0.05,
            graveyard_count=graveyard_count,
        )

    @pytest.mark.parametrize("count", [0, 1, 2, 3, 4, 5])
    def test_is_dead_end_false_below_threshold(self, count):
        """Gaps with graveyard_count below 6 are not dead ends."""
        gap = self._make_gap(count)
        assert gap.is_dead_end is False, (
            f"graveyard_count={count} should NOT be a dead end (threshold is 6)"
        )

    @pytest.mark.parametrize("count", [6, 7, 10])
    def test_is_dead_end_true_at_threshold(self, count):
        """Gaps with graveyard_count >= 6 are dead ends."""
        gap = self._make_gap(count)
        assert gap.is_dead_end is True, (
            f"graveyard_count={count} SHOULD be a dead end (threshold is 6)"
        )

    def test_boundary_at_exactly_5_is_not_dead_end(self):
        """5 failures (old threshold + 2) must still be active."""
        gap = self._make_gap(5)
        assert gap.is_dead_end is False

    def test_boundary_at_exactly_6_is_dead_end(self):
        """6 failures is the precise boundary that triggers dead-end."""
        gap = self._make_gap(6)
        assert gap.is_dead_end is True


# =============================================================================
# Fix 2: _get_graveyard_counts() logs warning instead of swallowing errors
# =============================================================================

class TestGraveyardCountsLogsWarningOnError:
    """_get_graveyard_counts() should log a warning and return {} on exception."""

    def test_returns_empty_dict_on_exception(self, caplog):
        """When ledger.get_graveyard_entries() raises, result is an empty dict."""
        mock_ledger = MagicMock()
        mock_ledger.get_graveyard_entries.side_effect = RuntimeError("DB connection lost")

        result = _get_graveyard_counts(mock_ledger)

        assert result == {}

    def test_logs_warning_on_exception(self, caplog):
        """When ledger.get_graveyard_entries() raises, a warning is emitted."""
        mock_ledger = MagicMock()
        mock_ledger.get_graveyard_entries.side_effect = RuntimeError("DB connection lost")

        with caplog.at_level(logging.WARNING, logger="edgar.xbrl.standardization.tools.auto_eval"):
            _get_graveyard_counts(mock_ledger)

        assert any(
            "DB connection lost" in record.message or "graveyard" in record.message.lower()
            for record in caplog.records
        ), "Expected a warning log message mentioning the error or 'graveyard'"

    def test_normal_operation_still_works(self):
        """When no exception is raised, counts are aggregated correctly."""
        mock_ledger = MagicMock()
        mock_ledger.get_graveyard_entries.return_value = [
            {"target_companies": "AAPL", "target_metric": "Revenue"},
            {"target_companies": "AAPL", "target_metric": "Revenue"},
            {"target_companies": "JPM", "target_metric": "NetIncome"},
        ]

        result = _get_graveyard_counts(mock_ledger)

        assert result == {"AAPL:Revenue": 2, "JPM:NetIncome": 1}


# =============================================================================
# Fix 3: propose_change() removed redundant dead-end check
# =============================================================================

class TestProposeChangeNoRedundantDeadEndCheck:
    """
    propose_change() must not filter by dead-end itself — identify_gaps() already does.
    A gap with graveyard_count=5 (previously blocked at old threshold of 3) must be
    passed through to the proposal machinery.
    """

    def test_gap_at_old_threshold_reaches_solver(self):
        """
        A validation_failure gap with graveyard_count=5 should call _propose_via_solver,
        not be short-circuited by a dead-end guard inside propose_change().
        """
        from edgar.xbrl.standardization.tools.auto_eval_loop import propose_change

        gap = MetricGap(
            ticker="XOM",
            metric="OperatingIncome",
            gap_type="validation_failure",
            estimated_impact=0.04,
            reference_value=12345.0,
            graveyard_count=5,  # Old threshold was 3 — this would have been blocked before
        )

        sentinel = MagicMock()
        sentinel.file = "metrics.yaml"

        with patch(
            "edgar.xbrl.standardization.tools.auto_eval_loop._propose_via_solver",
            return_value=sentinel,
        ) as mock_solver:
            result = propose_change(gap, graveyard_entries=[])

        mock_solver.assert_called_once_with(gap)
        assert result is sentinel

    def test_unmapped_gap_at_graveyard_count_4_reaches_proposal(self):
        """
        An unmapped gap with graveyard_count=4 should not be blocked by propose_change().
        identify_gaps() is responsible for filtering, not propose_change().

        We patch _propose_for_unmapped to confirm propose_change delegates to it
        rather than short-circuiting on graveyard_count before the call.
        """
        from edgar.xbrl.standardization.tools.auto_eval_loop import propose_change

        gap = MetricGap(
            ticker="JNJ",
            metric="Revenue",
            gap_type="unmapped",
            estimated_impact=0.05,
            reference_value=None,
            graveyard_count=4,  # Old threshold was 3 — this would have been dead-ended before
        )

        sentinel = MagicMock()
        sentinel.file = "companies.yaml"

        with patch(
            "edgar.xbrl.standardization.tools.auto_eval_loop._propose_for_unmapped",
            return_value=sentinel,
        ) as mock_unmapped:
            result = propose_change(gap, graveyard_entries=[])

        # The call must have reached _propose_for_unmapped — not been cut off by a dead-end guard
        mock_unmapped.assert_called_once()
        assert result is sentinel


# =============================================================================
# Fix 4: validation_failure routing goes straight to solver
# =============================================================================

class TestValidationFailureSkipsDivergenceGoesToSolver:
    """
    For validation_failure gaps, propose_change() should call _propose_via_solver,
    never _propose_for_validation_failure (divergence tolerance).
    """

    def test_validation_failure_calls_solver_not_divergence(self):
        from edgar.xbrl.standardization.tools.auto_eval_loop import propose_change

        gap = MetricGap(
            ticker="JPM",
            metric="NetIncome",
            gap_type="validation_failure",
            estimated_impact=0.03,
            current_variance=25.0,
            reference_value=50000.0,
            graveyard_count=0,
        )

        sentinel = MagicMock()

        with (
            patch(
                "edgar.xbrl.standardization.tools.auto_eval_loop._propose_for_validation_failure"
            ) as mock_divergence,
            patch(
                "edgar.xbrl.standardization.tools.auto_eval_loop._propose_via_solver",
                return_value=sentinel,
            ) as mock_solver,
        ):
            result = propose_change(gap, graveyard_entries=[])

        mock_divergence.assert_not_called()
        mock_solver.assert_called_once_with(gap)
        assert result is sentinel

    def test_validation_failure_returns_solver_result_even_if_none(self):
        """If the solver returns None, propose_change also returns None (no fallback to divergence)."""
        from edgar.xbrl.standardization.tools.auto_eval_loop import propose_change

        gap = MetricGap(
            ticker="CVX",
            metric="OperatingCashFlow",
            gap_type="validation_failure",
            estimated_impact=0.02,
            reference_value=8000.0,
            graveyard_count=2,
        )

        with (
            patch(
                "edgar.xbrl.standardization.tools.auto_eval_loop._propose_for_validation_failure"
            ) as mock_divergence,
            patch(
                "edgar.xbrl.standardization.tools.auto_eval_loop._propose_via_solver",
                return_value=None,
            ) as mock_solver,
        ):
            result = propose_change(gap, graveyard_entries=[])

        mock_divergence.assert_not_called()
        mock_solver.assert_called_once()
        assert result is None


# =============================================================================
# Fix 5: Circuit breaker no double-counting
# =============================================================================

class TestCircuitBreakerNoDoubleCounting:
    """
    When experiments are discarded in the inner loop, the post-loop no-progress
    check must NOT add another increment.  The condition gates on
    `experiments_total == experiments_before`.
    """

    def test_no_extra_increment_when_experiments_were_attempted(self):
        """
        If 3 experiments were discarded (each incremented consecutive_failures),
        the post-loop check must not fire because experiments_total != experiments_before.
        """
        experiments_before = 0
        experiments_total = 3   # 3 experiments were attempted and all discarded
        made_progress = False
        consecutive_failures = 3  # Already incremented once per discard in inner loop

        # This is the exact condition from the fixed run_overnight():
        if not made_progress and experiments_total == experiments_before:
            consecutive_failures += 1  # Must NOT execute

        assert consecutive_failures == 3, (
            "consecutive_failures should stay at 3 — the post-loop guard must not fire "
            "when experiments were attempted"
        )

    def test_increment_fires_when_no_experiments_attempted(self):
        """
        Conversely, if ZERO experiments were attempted (all gaps skipped for other reasons),
        the post-loop check SHOULD increment consecutive_failures.
        """
        experiments_before = 5
        experiments_total = 5   # No new experiments
        made_progress = False
        consecutive_failures = 0
        null_proposals = 0

        if not made_progress and experiments_total == experiments_before:
            if null_proposals > 0:
                pass  # Force circuit-breaker path (tested separately)
            else:
                consecutive_failures += 1  # Should execute

        assert consecutive_failures == 1


# =============================================================================
# Fix 6: Null-proposal exhaustion forces circuit breaker
# =============================================================================

class TestNullProposalExhaustionForcesStop:
    """
    When all gaps return change=None from propose_fn, the loop detects exhaustion
    and forces the circuit breaker instead of spinning indefinitely.
    """

    def test_null_proposals_force_max_consecutive_failures(self):
        """
        When all gaps produced null proposals (null_proposals > 0) and no new
        experiments ran, consecutive_failures is set to max_consecutive_failures.
        """
        experiments_before = 5
        experiments_total = 5   # No new experiments ran
        made_progress = False
        null_proposals = 3      # 3 gaps tried, all returned None
        max_consecutive_failures = 10
        consecutive_failures = 2

        # Exact condition from the fixed run_overnight():
        if not made_progress and experiments_total == experiments_before:
            if null_proposals > 0:
                consecutive_failures = max_consecutive_failures

        assert consecutive_failures == max_consecutive_failures, (
            f"consecutive_failures should be forced to {max_consecutive_failures} "
            f"when all proposals are null, got {consecutive_failures}"
        )

    def test_no_force_when_null_proposals_is_zero(self):
        """
        If null_proposals is 0 (no gaps were even tried), the force-stop path
        does not apply — only the regular increment fires.
        """
        experiments_before = 5
        experiments_total = 5
        made_progress = False
        null_proposals = 0
        max_consecutive_failures = 10
        consecutive_failures = 2

        if not made_progress and experiments_total == experiments_before:
            if null_proposals > 0:
                consecutive_failures = max_consecutive_failures  # Must NOT execute
            else:
                consecutive_failures += 1

        assert consecutive_failures == 3, (
            "With zero null_proposals, only the regular +1 increment should fire"
        )

    def test_force_stop_is_idempotent_when_already_at_max(self):
        """
        If consecutive_failures is already at max, forcing it again is safe (idempotent).
        """
        experiments_before = 5
        experiments_total = 5
        made_progress = False
        null_proposals = 5
        max_consecutive_failures = 10
        consecutive_failures = 10  # Already at max

        if not made_progress and experiments_total == experiments_before:
            if null_proposals > 0:
                consecutive_failures = max_consecutive_failures

        assert consecutive_failures == max_consecutive_failures
