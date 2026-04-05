"""
Cohort Reactor - Transferability Testing Engine

This module provides the Cohort Reactor, which automatically tests strategy
changes against cohorts of similar companies to identify knowledge transfer
opportunities and prevent regressions.

Workflow:
1. Developer fixes extraction for JPM (balance_guard: true)
2. Reactor auto-tests against GSIB_Banks cohort (JPM, BAC, C, WFC, GS, MS, BK, STT)
3. Reports: IMPROVED/NEUTRAL/REGRESSED per company
4. Blocks merge if Total Variance increases

Usage:
    from edgar.xbrl.standardization.reactor import CohortReactor

    reactor = CohortReactor()

    # Test a strategy change against a cohort
    result = reactor.test_strategy_change(
        cohort_name='GSIB_Banks',
        strategy_name='hybrid_debt',
        strategy_params={'balance_guard': True},
    )

    if result.is_passing:
        print("Safe to merge!")
    else:
        print(f"Blocked: {result.regressed_count} regressions")
"""

from .cohort_reactor import (
    CohortReactor,
    CohortDefinition,
    CompanyResult,
    CohortTestSummary,
)

__all__ = [
    'CohortReactor',
    'CohortDefinition',
    'CompanyResult',
    'CohortTestSummary',
]
