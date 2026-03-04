"""
Tests for PipelineOrchestrator.

Verifies:
- add_companies and reset_company
- run_batch with mocked state handlers
- get_status and get_summary
- CLI formatting helpers
- State machine routing (which handler is called per state)
"""

import pytest
from unittest.mock import patch, MagicMock

from edgar.xbrl.standardization.ledger.schema import ExperimentLedger
from edgar.xbrl.standardization.tools.pipeline_orchestrator import (
    PipelineOrchestrator,
    _format_status,
    _format_summary,
)


@pytest.fixture
def ledger():
    return ExperimentLedger(db_path=':memory:')


@pytest.fixture
def pipeline(ledger):
    return PipelineOrchestrator(ledger=ledger)


# =========================================================================
# ADD / RESET
# =========================================================================

class TestAddAndReset:

    def test_add_companies(self, pipeline, ledger):
        results = pipeline.add_companies(['AAPL', 'GOOG'])
        assert results == {'AAPL': 'added', 'GOOG': 'added'}
        assert ledger.get_pipeline_state('AAPL')['state'] == 'PENDING'
        assert ledger.get_pipeline_state('GOOG')['state'] == 'PENDING'

    def test_add_existing_company(self, pipeline):
        pipeline.add_companies(['AAPL'])
        results = pipeline.add_companies(['AAPL'])
        assert results == {'AAPL': 'already_exists'}

    def test_reset_company(self, pipeline, ledger):
        pipeline.add_companies(['AAPL'])
        ledger.advance_pipeline('AAPL', 'ONBOARDING')
        ledger.advance_pipeline('AAPL', 'FAILED', last_error='test')

        msg = pipeline.reset_company('AAPL')
        assert 'reset from FAILED to PENDING' in msg
        assert ledger.get_pipeline_state('AAPL')['state'] == 'PENDING'

    def test_reset_nonexistent(self, pipeline):
        msg = pipeline.reset_company('ZZZZ')
        assert 'not in pipeline' in msg


# =========================================================================
# RUN BATCH — DRY RUN
# =========================================================================

class TestRunBatchDryRun:

    def test_dry_run_pending(self, pipeline):
        pipeline.add_companies(['AAPL'])
        result = pipeline.run_batch(['AAPL'], dry_run=True)
        assert result['results']['AAPL']['dry_run'] is True
        assert result['results']['AAPL']['action'] == 'would_onboard'

    def test_dry_run_analyzing(self, pipeline, ledger):
        pipeline.add_companies(['AAPL'])
        ledger.advance_pipeline('AAPL', 'ONBOARDING')
        ledger.advance_pipeline('AAPL', 'ANALYZING', pass_rate=85.0, gaps_count=2)

        result = pipeline.run_batch(['AAPL'], dry_run=True)
        assert result['results']['AAPL']['action'] == 'would_analyze'

    def test_dry_run_skips_terminal(self, pipeline, ledger):
        pipeline.add_companies(['AAPL'])
        ledger.advance_pipeline('AAPL', 'ONBOARDING')
        ledger.advance_pipeline('AAPL', 'ANALYZING')
        ledger.advance_pipeline('AAPL', 'VALIDATING')
        ledger.advance_pipeline('AAPL', 'PROMOTING')
        ledger.advance_pipeline('AAPL', 'POPULATING')
        ledger.advance_pipeline('AAPL', 'COMPLETE')

        result = pipeline.run_batch(['AAPL'], dry_run=True)
        assert result['results']['AAPL']['skipped'] is True

    def test_not_in_pipeline(self, pipeline):
        result = pipeline.run_batch(['ZZZZ'])
        assert 'error' in result['results']['ZZZZ']


# =========================================================================
# RUN BATCH — STATE FILTERING
# =========================================================================

class TestRunBatchFiltering:

    def test_target_state_filter(self, pipeline, ledger):
        pipeline.add_companies(['AAPL', 'GOOG'])
        ledger.advance_pipeline('AAPL', 'ONBOARDING')
        ledger.advance_pipeline('AAPL', 'ANALYZING', pass_rate=85.0, gaps_count=2)
        # GOOG stays in PENDING

        result = pipeline.run_batch(['AAPL', 'GOOG'], dry_run=True, target_state='ANALYZING')
        assert result['results']['AAPL']['action'] == 'would_analyze'
        assert result['results']['GOOG']['skipped'] is True


# =========================================================================
# ANALYZING HANDLER
# =========================================================================

class TestAnalyzingHandler:

    def test_high_pass_rate_skips_to_validating(self, pipeline, ledger):
        pipeline.add_companies(['AAPL'])
        ledger.advance_pipeline('AAPL', 'ONBOARDING')
        ledger.advance_pipeline('AAPL', 'ANALYZING', pass_rate=95.0, gaps_count=0)

        result = pipeline._handle_analyzing('AAPL')
        assert result['state'] == 'VALIDATING'
        assert ledger.get_pipeline_state('AAPL')['state'] == 'VALIDATING'

    def test_medium_pass_rate_goes_to_resolving(self, pipeline, ledger):
        pipeline.add_companies(['AAPL'])
        ledger.advance_pipeline('AAPL', 'ONBOARDING')
        ledger.advance_pipeline('AAPL', 'ANALYZING', pass_rate=75.0, gaps_count=5)

        result = pipeline._handle_analyzing('AAPL')
        assert result['state'] == 'RESOLVING'
        assert ledger.get_pipeline_state('AAPL')['state'] == 'RESOLVING'

    def test_low_pass_rate_fails(self, pipeline, ledger):
        pipeline.add_companies(['AAPL'])
        ledger.advance_pipeline('AAPL', 'ONBOARDING')
        ledger.advance_pipeline('AAPL', 'ANALYZING', pass_rate=40.0, gaps_count=10)

        result = pipeline._handle_analyzing('AAPL')
        assert result['state'] == 'FAILED'
        assert ledger.get_pipeline_state('AAPL')['state'] == 'FAILED'


# =========================================================================
# STATUS / SUMMARY
# =========================================================================

class TestStatusAndSummary:

    def test_get_status_all(self, pipeline):
        pipeline.add_companies(['AAPL', 'GOOG', 'MSFT'])
        status = pipeline.get_status()
        assert len(status) == 3

    def test_get_status_by_ticker(self, pipeline):
        pipeline.add_companies(['AAPL', 'GOOG'])
        status = pipeline.get_status(ticker='AAPL')
        assert len(status) == 1
        assert status[0]['ticker'] == 'AAPL'

    def test_get_status_by_state(self, pipeline, ledger):
        pipeline.add_companies(['AAPL', 'GOOG'])
        ledger.advance_pipeline('AAPL', 'ONBOARDING')

        status = pipeline.get_status(state='PENDING')
        assert len(status) == 1
        assert status[0]['ticker'] == 'GOOG'

    def test_get_summary(self, pipeline, ledger):
        pipeline.add_companies(['AAPL', 'GOOG'])
        ledger.advance_pipeline('AAPL', 'ONBOARDING')

        summary = pipeline.get_summary()
        assert summary['total_companies'] == 2
        assert summary['pipeline_summary']['PENDING'] == 1
        assert summary['pipeline_summary']['ONBOARDING'] == 1

    def test_empty_summary(self, pipeline):
        summary = pipeline.get_summary()
        assert summary['total_companies'] == 0


# =========================================================================
# FORMATTING
# =========================================================================

class TestFormatting:

    def test_format_status_empty(self):
        assert _format_status([]) == 'No companies in pipeline.'

    def test_format_status_with_data(self):
        companies = [
            {
                'ticker': 'AAPL', 'state': 'COMPLETE', 'pass_rate': 95.2,
                'gaps_count': 0, 'golden_masters_count': 18, 'filings_populated': 14,
                'retry_count': 0, 'max_retries': 3, 'last_error': None,
            },
            {
                'ticker': 'GOOG', 'state': 'FAILED', 'pass_rate': 41.0,
                'gaps_count': 8, 'golden_masters_count': None, 'filings_populated': None,
                'retry_count': 3, 'max_retries': 3, 'last_error': 'Pass rate too low',
            },
        ]
        output = _format_status(companies)
        assert 'AAPL' in output
        assert 'COMPLETE' in output
        assert 'GOOG' in output
        assert 'FAILED' in output

    def test_format_summary(self):
        summary = {
            'pipeline_summary': {'COMPLETE': 5, 'FAILED': 1, 'PENDING': 0},
            'total_companies': 6,
            'complete': 5,
            'failed': 1,
            'golden_masters': 50,
            'recent_activity': [
                {'ticker': 'AAPL', 'state': 'COMPLETE', 'last_state_change': '2026-03-04T12:00:00', 'pass_rate': 95.0}
            ],
            'failed_companies': [
                {'ticker': 'MCD', 'last_error': 'Pass rate too low (41.0%)'}
            ],
        }
        output = _format_summary(summary)
        assert 'PIPELINE STATUS' in output
        assert 'Total companies: 6' in output
        assert 'Golden Masters: 50' in output
        assert 'RECENT ACTIVITY' in output
        assert 'FAILED COMPANIES' in output
        assert 'MCD' in output
