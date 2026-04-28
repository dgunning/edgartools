"""
Regression test for Issue #792.

facts.time_series(concept) returned a DataFrame without period_start, so two
facts that shared (period_end, fiscal_period, fiscal_year) but differed in
period_start (e.g., a 3-month discrete quarter vs. a 6-month YTD half-year)
became indistinguishable. Reporter @HristoRaykov surfaced this with AGNC's
NetIncomeLossAvailableToCommonStockholdersBasic for period_end 2025-06-30,
where Q2 (-178M, period_start=2025-04-01) and H1 YTD (-163M,
period_start=2025-01-01) collapsed onto rows that looked identical except
for numeric_value.

The fix surfaces period_start and a derived duration_days column.
"""

from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import pytest

from edgar.entity.entity_facts import EntityFacts
from edgar.entity.models import DataQuality, FinancialFact


def _make_fact(period_start: date, period_end: date, value: float,
               fiscal_period: str = 'Q2', fiscal_year: int = 2025) -> FinancialFact:
    return FinancialFact(
        concept='us-gaap:NetIncomeLossAvailableToCommonStockholdersBasic',
        taxonomy='us-gaap',
        label='Net Income Available to Common Stockholders',
        value=value,
        numeric_value=value,
        unit='USD',
        scale=1,
        period_start=period_start,
        period_end=period_end,
        period_type='duration',
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        filing_date=date(2025, 8, 1),
        accession='0000000000-25-000001',
        form_type='10-Q',
        data_quality=DataQuality.HIGH,
    )


@pytest.mark.fast
def test_time_series_includes_period_start_column():
    """time_series() must surface period_start so duration-overlapping facts are distinguishable."""
    facts_list = [
        _make_fact(date(2025, 4, 1), date(2025, 6, 30), -178_000_000.0),  # 3-month Q2
        _make_fact(date(2025, 1, 1), date(2025, 6, 30), -163_000_000.0),  # 6-month YTD H1
    ]
    ef = EntityFacts(cik=12345, name='Mock Co', facts=facts_list)

    ts = ef.time_series('NetIncomeLossAvailableToCommonStockholdersBasic')

    assert 'period_start' in ts.columns, "time_series must include period_start (Issue #792)"
    assert 'period_end' in ts.columns
    assert 'duration_days' in ts.columns


@pytest.mark.fast
def test_time_series_distinguishes_3m_from_ytd_for_same_period_end():
    """The exact AGNC scenario from Issue #792: two facts share period_end but differ by period_start."""
    facts_list = [
        _make_fact(date(2025, 4, 1), date(2025, 6, 30), -178_000_000.0),  # 3-month Q2
        _make_fact(date(2025, 1, 1), date(2025, 6, 30), -163_000_000.0),  # 6-month YTD H1
    ]
    ef = EntityFacts(cik=12345, name='Mock Co', facts=facts_list)

    ts = ef.time_series('NetIncomeLossAvailableToCommonStockholdersBasic')
    same_end = ts[ts['period_end'] == date(2025, 6, 30)]

    assert len(same_end) == 2, "both facts must be present"
    assert same_end['period_start'].nunique() == 2, "period_start must distinguish the two facts"

    # Confirm specific rows are recoverable by period_start
    q2_3m = same_end[same_end['period_start'] == date(2025, 4, 1)]
    ytd_h1 = same_end[same_end['period_start'] == date(2025, 1, 1)]
    assert len(q2_3m) == 1 and q2_3m.iloc[0]['numeric_value'] == -178_000_000.0
    assert len(ytd_h1) == 1 and ytd_h1.iloc[0]['numeric_value'] == -163_000_000.0


@pytest.mark.fast
def test_time_series_duration_days_reflects_window_length():
    """duration_days must compute correctly so users can filter by period length."""
    facts_list = [
        _make_fact(date(2025, 4, 1), date(2025, 6, 30), -178_000_000.0),  # ~90 days (Q2)
        _make_fact(date(2025, 1, 1), date(2025, 6, 30), -163_000_000.0),  # 180 days (H1)
    ]
    ef = EntityFacts(cik=12345, name='Mock Co', facts=facts_list)

    ts = ef.time_series('NetIncomeLossAvailableToCommonStockholdersBasic')

    q2_3m = ts[ts['period_start'] == date(2025, 4, 1)].iloc[0]
    ytd_h1 = ts[ts['period_start'] == date(2025, 1, 1)].iloc[0]

    assert q2_3m['duration_days'] == 90, f"3-month period should be 90 days, got {q2_3m['duration_days']}"
    assert ytd_h1['duration_days'] == 180, f"6-month period should be 180 days, got {ytd_h1['duration_days']}"


@pytest.mark.fast
def test_time_series_returns_empty_dataframe_for_unknown_concept():
    """Empty result must remain a DataFrame; the column-reordering branch must not break it."""
    ef = EntityFacts(cik=12345, name='Mock Co', facts=[])

    ts = ef.time_series('SomeNonexistentConcept')

    assert isinstance(ts, pd.DataFrame)
    assert ts.empty
