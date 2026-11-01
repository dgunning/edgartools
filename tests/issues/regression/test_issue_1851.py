"""
EntityFacts pivot classifies durations by days, so 13-week quarters keep their own columns.

``FactQuery._format_period_label`` counted the calendar months a period touched. Apple's
13-week fiscal quarter from 2024-12-29 to 2025-03-29 touches four months and was labelled
``6M 2025``; the 26-week six-month YTD became ``9M 2025`` and the 39-week nine-month YTD
``10M 2025``. Q2 and Q3 then shared the ``6M 2025`` column and ``pivot_table(aggfunc='first')``
dropped Q3's net income with only a generic warning. Facts that still share a label
(two instants of one fiscal year) now get a dated column instead of being dropped.

Ground truth: Apple Inc. (CIK 320193) ``us-gaap:NetIncomeLoss`` from SEC company facts,
matching the Condensed Consolidated Statements of Operations in
10-Q 0000320193-25-000057 (period ended 2025-03-29) and
10-Q 0000320193-25-000073 (period ended 2025-06-28):

    2024-12-29 .. 2025-03-29  three months   24,780,000,000
    2024-09-29 .. 2025-03-29  six months     61,110,000,000
    2025-03-30 .. 2025-06-28  three months   23,434,000,000
    2024-09-29 .. 2025-06-28  nine months    84,544,000,000

GitHub Issue: https://github.com/dgunning/edgartools/issues/1851
"""

import json
from datetime import date
from pathlib import Path

import pytest

from edgar.entity.models import FinancialFact
from edgar.entity.parser import EntityFactsParser
from edgar.entity.query import FactQuery

Q2_ACCESSION = '0000320193-25-000057'
Q3_ACCESSION = '0000320193-25-000073'
LPA_FIXTURE = Path(__file__).resolve().parents[2] / 'fixtures' / 'entity' / 'lpa_facts.json'


def _net_income(start, end, value, fiscal_period, accession, filed):
    return FinancialFact(
        concept='us-gaap:NetIncomeLoss',
        taxonomy='us-gaap',
        label='Net Income (Loss) Attributable to Parent',
        value=value,
        numeric_value=float(value),
        unit='USD',
        period_start=start,
        period_end=end,
        period_type='duration',
        fiscal_year=2025,
        fiscal_period=fiscal_period,
        filing_date=filed,
        form_type='10-Q',
        accession=accession,
        statement_type='IncomeStatement',
    )


@pytest.fixture
def apple_fy2025_net_income():
    return [
        _net_income(date(2024, 12, 29), date(2025, 3, 29), 24_780_000_000, 'Q2', Q2_ACCESSION, date(2025, 5, 2)),
        _net_income(date(2024, 9, 29), date(2025, 3, 29), 61_110_000_000, 'Q2', Q2_ACCESSION, date(2025, 5, 2)),
        _net_income(date(2025, 3, 30), date(2025, 6, 28), 23_434_000_000, 'Q3', Q3_ACCESSION, date(2025, 8, 1)),
        _net_income(date(2024, 9, 29), date(2025, 6, 28), 84_544_000_000, 'Q3', Q3_ACCESSION, date(2025, 8, 1)),
    ]


@pytest.mark.fast
def test_thirteen_week_quarters_keep_their_own_columns(apple_fy2025_net_income):
    statement = FactQuery(apple_fy2025_net_income, {}).pivot_by_period(return_statement=True)
    row = statement.data.loc['Net Income (Loss) Attributable to Parent']

    assert len(statement.data.columns) == 4
    assert row['Q2 2025'] == 23_434_000_000   # 2025-03-30 .. 2025-06-28
    assert row['Q1 2025'] == 24_780_000_000   # 2024-12-29 .. 2025-03-29
    assert row['6M 2025'] == 61_110_000_000
    assert row['9M 2025'] == 84_544_000_000
    assert sorted(statement.period_lengths) == ['3M', '6M', '9M']


@pytest.mark.fast
def test_a_durations_dates_outrank_its_fy_tag(apple_fy2025_net_income):
    # SEC company facts tag every fact in a 10-K with fiscal_period 'FY', quarters
    # included. The label used to trust that tag over the dates.
    q2, _, q3, _ = apple_fy2025_net_income
    q2.fiscal_period = 'FY'
    q3.fiscal_period = 'FY'

    row = FactQuery([q2, q3], {}).pivot_by_period(return_statement=False).iloc[0]

    assert row['Q1 2025'] == 24_780_000_000
    assert row['Q2 2025'] == 23_434_000_000


@pytest.mark.fast
def test_two_dates_under_one_label_both_keep_a_cell():
    """LPA's 20-F (0001997711-25-000030) reports cash at the 2024-03-26 business
    combination and at the 2024-12-31 year end, both tagged FY 2024. One of them used
    to be dropped; the year end keeps 'FY 2024' and the other gets a dated column."""
    payload = json.loads(LPA_FIXTURE.read_text('utf-8'))
    facts = EntityFactsParser.parse_company_facts(payload)

    pivot = facts.query().pivot_by_period(return_statement=False)

    assert pivot.loc['CashAndCashEquivalents', 'FY 2024'] == 28_827_347
    assert pivot.loc['CashAndCashEquivalents', 'FY 2024 (2024-03-26)'] == 1_121_150
