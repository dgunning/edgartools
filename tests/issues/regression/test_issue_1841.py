"""Regression test for GH #1841: AEON's operations statement defaulted to the predecessor only.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1841

The quarterly selector anchors on the shortest duration (60+ days) ending on the
report date. AEON's 10-Q/A has August 1 - September 30, 2023 (61 days), which
its operations statement presents through a single income tax fact, so that
became the anchor and was then dropped as sparse. The successor period July 23 -
September 30, 2023 (70 days) was neither the anchor nor in the 80-100 day
bucket, so it was never a candidate, and the default frame held only the
predecessor January 1 - July 21. Report-date anchors are now chosen among those
the statement presents in earnest (at least half the rows of its densest
anchor); the predecessor stays as its own column.

Ground truth: AEON Biopharma 10-Q/A Q3 2023 (0001837607-24-000014), R4
"Condensed Consolidated Statements of Operations and Comprehensive Loss":
successor July 23 - September 30, 2023 operating income 64,286 and loss and
comprehensive loss line 50,289 (USD thousands), basic weighted average shares
37,159,600; predecessor January 1 - July 21, 2023 operating loss (29,644),
basic weighted average shares 138,848,177.
"""
import pytest

from edgar import find
from edgar.financials import Financials
from edgar.xbrl.period_selector import _select_quarterly_periods

R4 = "http://www.aeonbiopharma.com/role/StatementCondensedConsolidatedStatementsOfOperationsAndComprehensiveLoss"
SUCCESSOR = 'duration_2023-07-23_2023-09-30'
SPARSE = 'duration_2023-08-01_2023-09-30'


def _duration(start, end, days):
    return {'type': 'duration', 'start_date': start, 'end_date': end, 'days': days,
            'key': f'duration_{start}_{end}', 'label': f'{start} to {end}'}


PERIODS = [_duration('2023-07-23', '2023-09-30', 70), _duration('2023-08-01', '2023-09-30', 61),
           _duration('2023-01-01', '2023-07-21', 202)]


@pytest.mark.fast
def test_anchor_is_the_report_date_period_the_statement_presents():
    rows = [{'values': {SUCCESSOR: 1.0, 'duration_2023-01-01_2023-07-21': 2.0}} for _ in range(40)]
    rows.append({'values': {SPARSE: 0.0}})
    keys = [key for key, _ in _select_quarterly_periods(PERIODS, 4, '2023-09-30', rows)]
    assert keys[0] == SUCCESSOR  # was the 61-day period with one fact
    assert 'duration_2023-01-01_2023-07-21' in keys


@pytest.mark.fast
def test_without_statement_rows_the_shortest_anchor_still_leads():
    keys = [key for key, _ in _select_quarterly_periods(PERIODS, 4, '2023-09-30')]
    assert keys[0] == SPARSE


@pytest.mark.network
def test_aeon_default_frame_shows_the_successor_and_the_predecessor():
    xbrl = find("0001837607-24-000014").xbrl()
    df = xbrl.statements[R4].to_dataframe(standard=False, presentation=False)
    plain = df[df["dimension"] != True]  # noqa: E712

    def row(concept):
        return plain[plain["concept"] == concept].iloc[0]

    assert [c for c in df.columns if c.startswith("2023")] == ["2023-09-30", "2023-07-21 (YTD)"]
    assert row("us-gaap_OperatingIncomeLoss")["2023-09-30"] == 64_286_000  # successor, Jul 23 - Sep 30
    assert row("us-gaap_OperatingIncomeLoss")["2023-07-21 (YTD)"] == -29_644_000  # predecessor
    assert row("aeon_LossAndComprehensiveLoss")["2023-09-30"] == 50_289_000
    assert row("us-gaap_WeightedAverageNumberOfSharesOutstandingBasic")["2023-09-30"] == 37_159_600
    assert row("us-gaap_WeightedAverageNumberOfSharesOutstandingBasic")["2023-07-21 (YTD)"] == 138_848_177

    statement = xbrl.statements[R4].render()
    assert [p.key for p in statement.periods] == [SUCCESSOR, 'duration_2023-01-01_2023-07-21']
    assert Financials(xbrl).get_shares_outstanding_basic() == 37_159_600
