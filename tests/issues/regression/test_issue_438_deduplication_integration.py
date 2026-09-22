"""
Integration test for Issue #438 fix - Revenue deduplication in real filings

Verifies that revenue deduplication runs on real income statements, is stable,
and never invents or multiplies rows.

GitHub Issue: https://github.com/dgunning/edgartools/issues/438

Moved here from tests/issues/reproductions/ on 2026-08-10 (bead
edgartools-07lk.24, Tier 2). It is the only coverage anywhere that runs
RevenueDeduplicator against real filing data -- test_issue_438_regression.py
next door exercises it only on synthetic dicts -- so the Tier 2 plan to delete
this tree's regression-marked files as duplicates did not apply to this one.

Rewritten 2026-08-09 (bead edgartools-07lk.24, finding 3). Every one of these
tests used to pass unconditionally:

  - test_integration_no_regression_with_nvda returned early on missing filings,
    missing financials and a missing income statement, so three of its four
    outcomes were a silent pass.
  - test_integration_with_multiple_companies wrapped the loop body in
    `except Exception: continue`. AssertionError is an Exception, so both of its
    asserts were dead — all three companies could fail and the test still passed.
  - test_deduplication_disabled_for_non_income_statements had no assertions at
    all; it printed and re-raised.

Assertions here are invariants rather than row counts, because the counts move
every time these companies file. Measured 2026-08-09 for context: NVDA 44 income
statement rows / 13 revenue rows, AAPL 50/11, MSFT 43/10, GOOGL 36/1.
"""

import pytest

from edgar import Company
from edgar.xbrl.deduplication_strategy import RevenueDeduplicator


def _latest_10k_income_statement(ticker: str):
    """Return (filing, income statement) for a ticker's most recent 10-K.

    Filters on form rather than taking .latest() off an unfiltered set: the
    newest 10-K is periodically a 10-K/A carrying a cover page and nothing else,
    which has no statements at all.
    """
    company = Company(ticker)
    filings = company.get_filings(form="10-K", amendments=False)
    assert len(filings) > 0, f"{ticker}: no 10-K filings returned"

    filing = filings.latest()
    report = filing.obj()
    assert report is not None, f"{ticker}: filing.obj() returned None for {filing.accession_number}"

    income_statement = report.income_statement
    assert income_statement is not None, (
        f"{ticker}: no income statement in {filing.accession_number}"
    )
    return filing, income_statement


def _assert_dedup_invariants(ticker: str, raw_data):
    """The three properties deduplication must have, on any input."""
    deduplicated = RevenueDeduplicator.deduplicate_statement_items(raw_data)
    stats = RevenueDeduplicator.get_deduplication_stats(raw_data, deduplicated)

    assert len(deduplicated) <= len(raw_data), (
        f"{ticker}: deduplication added rows ({len(raw_data)} -> {len(deduplicated)})"
    )
    assert stats['deduplicated_revenue_items'] <= stats['original_revenue_items'], (
        f"{ticker}: revenue row count grew "
        f"({stats['original_revenue_items']} -> {stats['deduplicated_revenue_items']})"
    )

    # Idempotence. A second pass must be a no-op, otherwise "deduplicated" is
    # not a fixed point and the result depends on how many times it ran.
    twice = RevenueDeduplicator.deduplicate_statement_items(deduplicated)
    assert len(twice) == len(deduplicated), (
        f"{ticker}: deduplication is not idempotent "
        f"({len(deduplicated)} -> {len(twice)} on a second pass)"
    )
    return stats


def test_integration_no_regression_with_nvda():
    """NVDA's income statement survives deduplication with its revenue intact."""
    _, income_statement = _latest_10k_income_statement("NVDA")
    raw_data = income_statement.get_raw_data()

    assert len(raw_data) > 10, f"NVDA income statement has only {len(raw_data)} rows"

    revenue_items = [i for i in raw_data if RevenueDeduplicator._is_revenue_concept(i)]
    assert len(revenue_items) >= 1, (
        "NVDA income statement has no revenue rows — deduplication would have "
        "nothing to act on and this test would prove nothing"
    )

    stats = _assert_dedup_invariants("NVDA", raw_data)
    assert stats['deduplicated_revenue_items'] >= 1, (
        "deduplication removed every revenue row from NVDA's income statement"
    )


def test_integration_with_multiple_companies():
    """The same invariants hold across several large filers.

    Failures are collected per company and reported together rather than
    aborting on the first, so one bad filing does not hide the other two. They
    are still failures: the old version of this loop caught Exception and
    continued, which silently disabled both of its assertions.
    """
    tickers = ["AAPL", "MSFT", "GOOGL"]
    failures = []
    exercised = []

    for ticker in tickers:
        try:
            _, income_statement = _latest_10k_income_statement(ticker)
            raw_data = income_statement.get_raw_data()
            _assert_dedup_invariants(ticker, raw_data)
            exercised.append(ticker)
        except AssertionError as e:
            # The helper messages already name the ticker; don't prefix it twice.
            failures.append(str(e))

    assert not failures, "Deduplication invariants broken:\n" + "\n".join(failures)
    assert exercised == tickers, (
        f"Expected to exercise {tickers}, actually exercised {exercised}"
    )


def test_deduplication_scope_is_the_income_statement():
    """Income statements arrive already deduplicated; balance sheets arrive raw.

    The scope guard is `if actual_statement_type == 'IncomeStatement'` in
    edgar/xbrl/xbrl.py (see the RevenueDeduplicator call site). This test pins
    the observable half of that: an income statement that comes back from the
    pipeline is a fixed point of deduplication, which is only true if the
    pipeline already applied it.

    The balance-sheet half is asserted but weak on purpose. Measured across
    NVDA, AAPL, MSFT and GOOGL on 2026-08-09, deduplication would remove zero
    rows from any of their balance sheets, so real filings cannot distinguish
    "the guard held" from "there was nothing to remove". Proving the guard
    itself needs a synthetic duplicate pair, which belongs in a unit test
    against deduplicate_statement_items rather than here.
    """
    company = Company("AAPL")
    filings = company.get_filings(form="10-K", amendments=False)
    assert len(filings) > 0, "AAPL: no 10-K filings returned"
    report = filings.latest().obj()
    assert report is not None, "AAPL: filing.obj() returned None"

    income_statement = report.income_statement
    assert income_statement is not None, "AAPL: no income statement"
    is_data = income_statement.get_raw_data()
    assert len(RevenueDeduplicator.deduplicate_statement_items(is_data)) == len(is_data), (
        "AAPL's income statement is not a fixed point of deduplication, so the "
        "pipeline did not deduplicate it before handing it over"
    )

    balance_sheet = report.balance_sheet
    assert balance_sheet is not None, "AAPL: no balance sheet"
    bs_data = balance_sheet.get_raw_data()
    assert len(bs_data) > 10, f"AAPL balance sheet has only {len(bs_data)} rows"
    assert len(RevenueDeduplicator.deduplicate_statement_items(bs_data)) == len(bs_data), (
        "deduplication would remove balance-sheet rows; if that ever becomes "
        "true, the scope guard in xbrl.py is the only thing protecting them and "
        "this test needs to assert it directly"
    )
