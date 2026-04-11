"""
Experiment Ledger for XBRL Extraction Tracking

This module provides a SQLite-based ledger for tracking all extraction attempts,
enabling experiment reproducibility and golden master management.

Key Features:
- Record every extraction run with strategy fingerprint
- Track golden masters (3+ successful periods)
- Support cohort test results
- Query historical extraction performance

Usage:
    from edgar.xbrl.standardization.ledger import ExperimentLedger, ExtractionRun

    # Create ledger
    ledger = ExperimentLedger()

    # Record an extraction run
    run = ExtractionRun(
        ticker='JPM',
        metric='ShortTermDebt',
        fiscal_period='2024-Q4',
        form_type='10-K',
        archetype='B',
        sub_archetype='hybrid',
        strategy_name='hybrid_debt',
        strategy_fingerprint='abc123',
        extracted_value=15000000000,
        reference_value=15500000000,
    )
    ledger.record_run(run)

    # Query runs
    runs = ledger.get_runs_for_ticker('JPM')
"""

from .schema import (
    ExtractionRun,
    GoldenMaster,
    CohortTestResult,
    RegressionResult,
    RegressionReport,
    ExperimentLedger,
)

__all__ = [
    'ExtractionRun',
    'GoldenMaster',
    'CohortTestResult',
    'RegressionResult',
    'RegressionReport',
    'ExperimentLedger',
]
