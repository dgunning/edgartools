"""
Tests for the pipeline_state table in ExperimentLedger.

Verifies:
- State transitions follow the allowed graph
- retry_count increments on ANALYZING retries
- max_retries enforcement (3 retries → FAILED)
- Idempotent add_pipeline_company
- reset_pipeline clears state
- Batch queries and summary
"""

import pytest

from edgar.xbrl.standardization.ledger.schema import ExperimentLedger


@pytest.fixture
def ledger():
    """In-memory ledger for fast tests."""
    return ExperimentLedger(db_path=':memory:')


# =========================================================================
# ADD / GET
# =========================================================================

class TestAddAndGet:

    def test_add_pipeline_company(self, ledger):
        ledger.add_pipeline_company('AAPL', 'Apple Inc.')
        state = ledger.get_pipeline_state('AAPL')
        assert state is not None
        assert state['ticker'] == 'AAPL'
        assert state['company_name'] == 'Apple Inc.'
        assert state['state'] == 'PENDING'
        assert state['retry_count'] == 0

    def test_add_is_idempotent(self, ledger):
        ledger.add_pipeline_company('AAPL', 'Apple Inc.')
        ledger.add_pipeline_company('AAPL', 'Apple Inc. v2')
        state = ledger.get_pipeline_state('AAPL')
        # INSERT OR IGNORE: first insert wins
        assert state['company_name'] == 'Apple Inc.'

    def test_get_nonexistent_returns_none(self, ledger):
        assert ledger.get_pipeline_state('ZZZZ') is None

    def test_ticker_is_uppercased(self, ledger):
        ledger.add_pipeline_company('aapl')
        state = ledger.get_pipeline_state('aapl')
        assert state['ticker'] == 'AAPL'


# =========================================================================
# STATE TRANSITIONS
# =========================================================================

class TestStateTransitions:

    def test_pending_to_onboarding(self, ledger):
        ledger.add_pipeline_company('AAPL')
        ledger.advance_pipeline('AAPL', 'ONBOARDING')
        assert ledger.get_pipeline_state('AAPL')['state'] == 'ONBOARDING'

    def test_full_happy_path(self, ledger):
        """Test the complete PENDING → COMPLETE path."""
        ledger.add_pipeline_company('AAPL')

        for state in ['ONBOARDING', 'ANALYZING', 'VALIDATING', 'PROMOTING', 'POPULATING', 'COMPLETE']:
            ledger.advance_pipeline('AAPL', state)
            assert ledger.get_pipeline_state('AAPL')['state'] == state

    def test_invalid_transition_raises(self, ledger):
        ledger.add_pipeline_company('AAPL')
        # Can't go PENDING → COMPLETE
        with pytest.raises(ValueError, match='Invalid transition'):
            ledger.advance_pipeline('AAPL', 'COMPLETE')

    def test_cannot_skip_states(self, ledger):
        ledger.add_pipeline_company('AAPL')
        # Can't go PENDING → PROMOTING
        with pytest.raises(ValueError, match='Invalid transition'):
            ledger.advance_pipeline('AAPL', 'PROMOTING')

    def test_nonexistent_ticker_raises(self, ledger):
        with pytest.raises(ValueError, match='not in pipeline'):
            ledger.advance_pipeline('ZZZZ', 'ONBOARDING')

    def test_any_state_can_go_to_failed(self, ledger):
        """Test that most active states can transition to FAILED."""
        states_that_can_fail = [
            'ONBOARDING', 'ANALYZING', 'RESOLVING',
            'VALIDATING', 'PROMOTING', 'POPULATING',
        ]
        for i, state in enumerate(states_that_can_fail):
            ticker = f'T{i}'
            ledger.add_pipeline_company(ticker)
            # Walk to the target state
            path_to_state = {
                'ONBOARDING': ['ONBOARDING'],
                'ANALYZING': ['ONBOARDING', 'ANALYZING'],
                'RESOLVING': ['ONBOARDING', 'ANALYZING', 'RESOLVING'],
                'VALIDATING': ['ONBOARDING', 'ANALYZING', 'VALIDATING'],
                'PROMOTING': ['ONBOARDING', 'ANALYZING', 'VALIDATING', 'PROMOTING'],
                'POPULATING': ['ONBOARDING', 'ANALYZING', 'VALIDATING', 'PROMOTING', 'POPULATING'],
            }
            for s in path_to_state[state]:
                ledger.advance_pipeline(ticker, s)
            # Now fail
            ledger.advance_pipeline(ticker, 'FAILED', last_error='test error')
            assert ledger.get_pipeline_state(ticker)['state'] == 'FAILED'

    def test_complete_is_terminal(self, ledger):
        """COMPLETE has no outgoing transitions."""
        ledger.add_pipeline_company('AAPL')
        for s in ['ONBOARDING', 'ANALYZING', 'VALIDATING', 'PROMOTING', 'POPULATING', 'COMPLETE']:
            ledger.advance_pipeline('AAPL', s)
        with pytest.raises(ValueError, match='Invalid transition'):
            ledger.advance_pipeline('AAPL', 'PENDING')

    def test_failed_is_terminal(self, ledger):
        """FAILED has no outgoing transitions."""
        ledger.add_pipeline_company('AAPL')
        ledger.advance_pipeline('AAPL', 'ONBOARDING')
        ledger.advance_pipeline('AAPL', 'FAILED')
        with pytest.raises(ValueError, match='Invalid transition'):
            ledger.advance_pipeline('AAPL', 'PENDING')


# =========================================================================
# RETRY LOGIC
# =========================================================================

class TestRetryLogic:

    def test_retry_increments_on_resolving_to_analyzing(self, ledger):
        ledger.add_pipeline_company('AAPL')
        ledger.advance_pipeline('AAPL', 'ONBOARDING')
        ledger.advance_pipeline('AAPL', 'ANALYZING')
        ledger.advance_pipeline('AAPL', 'RESOLVING')

        # First retry: RESOLVING → ANALYZING
        ledger.advance_pipeline('AAPL', 'ANALYZING')
        state = ledger.get_pipeline_state('AAPL')
        assert state['retry_count'] == 1
        assert state['state'] == 'ANALYZING'

    def test_retry_increments_on_validating_to_analyzing(self, ledger):
        ledger.add_pipeline_company('AAPL')
        ledger.advance_pipeline('AAPL', 'ONBOARDING')
        ledger.advance_pipeline('AAPL', 'ANALYZING')
        ledger.advance_pipeline('AAPL', 'VALIDATING')

        # Regression: VALIDATING → ANALYZING
        ledger.advance_pipeline('AAPL', 'ANALYZING')
        state = ledger.get_pipeline_state('AAPL')
        assert state['retry_count'] == 1

    def test_max_retries_forces_failed(self, ledger):
        """After 3 retries, ANALYZING → RESOLVING → ANALYZING forces FAILED."""
        ledger.add_pipeline_company('AAPL')
        ledger.advance_pipeline('AAPL', 'ONBOARDING')
        ledger.advance_pipeline('AAPL', 'ANALYZING')

        for i in range(3):
            ledger.advance_pipeline('AAPL', 'RESOLVING')
            ledger.advance_pipeline('AAPL', 'ANALYZING')

        # retry_count is now 3
        state = ledger.get_pipeline_state('AAPL')
        assert state['retry_count'] == 3

        # One more retry should force FAILED
        ledger.advance_pipeline('AAPL', 'RESOLVING')
        ledger.advance_pipeline('AAPL', 'ANALYZING')  # This should become FAILED

        state = ledger.get_pipeline_state('AAPL')
        assert state['state'] == 'FAILED'
        assert 'Max retries' in (state.get('last_error') or '')


# =========================================================================
# METADATA AND KWARGS
# =========================================================================

class TestMetadata:

    def test_advance_with_kwargs(self, ledger):
        ledger.add_pipeline_company('AAPL')
        ledger.advance_pipeline('AAPL', 'ONBOARDING')
        ledger.advance_pipeline(
            'AAPL', 'ANALYZING',
            pass_rate=85.5,
            gaps_count=3,
        )
        state = ledger.get_pipeline_state('AAPL')
        assert state['pass_rate'] == 85.5
        assert state['gaps_count'] == 3

    def test_metadata_merges(self, ledger):
        ledger.add_pipeline_company('AAPL')
        ledger.advance_pipeline('AAPL', 'ONBOARDING', metadata={'key1': 'value1'})
        state = ledger.get_pipeline_state('AAPL')
        assert state['metadata']['key1'] == 'value1'

        ledger.advance_pipeline('AAPL', 'ANALYZING', metadata={'key2': 'value2'})
        state = ledger.get_pipeline_state('AAPL')
        assert state['metadata']['key1'] == 'value1'
        assert state['metadata']['key2'] == 'value2'

    def test_last_error_recorded(self, ledger):
        ledger.add_pipeline_company('AAPL')
        ledger.advance_pipeline('AAPL', 'ONBOARDING')
        ledger.advance_pipeline('AAPL', 'FAILED', last_error='Something broke')
        state = ledger.get_pipeline_state('AAPL')
        assert state['last_error'] == 'Something broke'


# =========================================================================
# BATCH / SUMMARY QUERIES
# =========================================================================

class TestBatchAndSummary:

    def test_get_pipeline_batch(self, ledger):
        for t in ['AAPL', 'GOOG', 'MSFT']:
            ledger.add_pipeline_company(t)
        # All should be PENDING
        batch = ledger.get_pipeline_batch('PENDING')
        assert len(batch) == 3
        tickers = {b['ticker'] for b in batch}
        assert tickers == {'AAPL', 'GOOG', 'MSFT'}

    def test_get_pipeline_batch_filters(self, ledger):
        ledger.add_pipeline_company('AAPL')
        ledger.add_pipeline_company('GOOG')
        ledger.advance_pipeline('AAPL', 'ONBOARDING')

        pending = ledger.get_pipeline_batch('PENDING')
        assert len(pending) == 1
        assert pending[0]['ticker'] == 'GOOG'

    def test_get_pipeline_summary(self, ledger):
        ledger.add_pipeline_company('AAPL')
        ledger.add_pipeline_company('GOOG')
        ledger.advance_pipeline('AAPL', 'ONBOARDING')

        summary = ledger.get_pipeline_summary()
        assert summary.get('PENDING', 0) == 1
        assert summary.get('ONBOARDING', 0) == 1

    def test_empty_summary(self, ledger):
        summary = ledger.get_pipeline_summary()
        assert summary == {}


# =========================================================================
# RESET
# =========================================================================

class TestReset:

    def test_reset_clears_state(self, ledger):
        ledger.add_pipeline_company('AAPL')
        ledger.advance_pipeline('AAPL', 'ONBOARDING')
        ledger.advance_pipeline('AAPL', 'FAILED', last_error='oops')

        ledger.reset_pipeline('AAPL')
        state = ledger.get_pipeline_state('AAPL')
        assert state['state'] == 'PENDING'
        assert state['retry_count'] == 0
        assert state['last_error'] is None

    def test_reset_allows_reprocessing(self, ledger):
        ledger.add_pipeline_company('AAPL')
        ledger.advance_pipeline('AAPL', 'ONBOARDING')
        ledger.advance_pipeline('AAPL', 'FAILED')

        ledger.reset_pipeline('AAPL')
        # Should be able to advance again
        ledger.advance_pipeline('AAPL', 'ONBOARDING')
        assert ledger.get_pipeline_state('AAPL')['state'] == 'ONBOARDING'


# =========================================================================
# RECENT ACTIVITY
# =========================================================================

class TestRecentActivity:

    def test_recent_activity_tracks_transitions(self, ledger):
        ledger.add_pipeline_company('AAPL')
        ledger.advance_pipeline('AAPL', 'ONBOARDING')
        ledger.advance_pipeline('AAPL', 'ANALYZING', pass_rate=90.0)

        activity = ledger.get_pipeline_recent_activity(limit=5)
        assert len(activity) >= 1
        assert activity[0]['ticker'] == 'AAPL'
        assert activity[0]['state'] == 'ANALYZING'
