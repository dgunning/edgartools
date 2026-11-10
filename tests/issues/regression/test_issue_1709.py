"""EntityFacts.time_series() omitted duration_days when no rows came back.

The method documents six columns, including duration_days. It built that
column and selected the six only inside ``if not df.empty``, so an absent
concept or ``periods=0`` returned five columns and ``df['duration_days']``
raised KeyError. A populated series was unaffected.

Ground truth is the tracked SEC company-facts fixtures. Logistic Properties
of the Americas (CIK 0001997711), ``tests/fixtures/entity/lpa_facts.json``,
is an IFRS filer: ``us-gaap:Assets`` matches nothing. Its FY2024 Form 20-F
(accession 0001997711-25-000030, filed 2025-04-02) reports 31,668,601 common
shares outstanding at 2025-04-02, an instant fact with no start and no
duration, and revenue of 43,862,372 for 2024-01-01 to 2024-12-31. The same
filing reports 0 for
``ifrs-full:AcquisitionsThroughBusinessCombinationsInvestmentProperty`` over
that year. Snowflake (CIK 0001640147),
``tests/fixtures/entity/snow_facts.json``, reports two NetIncomeLoss windows
ending 2024-07-31 on its Q2 FY2025 10-Q (accession 0001640147-24-000207):
-316,899,000 for the quarter started 2024-05-01 and -633,887,000 for the
year-to-date started 2024-02-01.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1709
"""

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from edgar.entity.parser import EntityFactsParser

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "entity"
COLUMNS = [
    "period_start",
    "period_end",
    "duration_days",
    "numeric_value",
    "fiscal_period",
    "fiscal_year",
]

# LPA FY2024 Form 20-F, accession 0001997711-25-000030.
LPA_SHARES_2025_04_02 = 31_668_601
LPA_REVENUE_FY2024 = 43_862_372
# Snowflake Q2 FY2025 10-Q, accession 0001640147-24-000207.
SNOW_NET_INCOME_QUARTER = -316_899_000
SNOW_NET_INCOME_YTD = -633_887_000


def _load(name: str):
    path = FIXTURES / name
    assert path.exists(), f"missing fixture: {path}"
    return EntityFactsParser.parse_company_facts(json.loads(path.read_text("utf-8")))


@pytest.fixture(scope="module")
def lpa():
    return _load("lpa_facts.json")


@pytest.fixture(scope="module")
def snow():
    return _load("snow_facts.json")


def _assert_empty_schema(result: pd.DataFrame) -> None:
    assert len(result) == 0
    assert result.columns.tolist() == COLUMNS, (
        f"empty time_series columns were {result.columns.tolist()}"
    )
    assert result["duration_days"].tolist() == []


@pytest.mark.fast
def test_absent_concept_and_periods_zero_keep_duration_days(lpa, snow):
    """An empty selection is zero rows, not a narrower table."""
    _assert_empty_schema(lpa.time_series("us-gaap:Assets"))
    _assert_empty_schema(
        lpa.time_series("dei:EntityCommonStockSharesOutstanding", periods=0)
    )
    _assert_empty_schema(snow.time_series("ifrs-full:Revenue"))
    _assert_empty_schema(snow.time_series("us-gaap:Assets", periods=0))


@pytest.mark.fast
def test_lpa_shares_outstanding_stays_an_instant_fact(lpa):
    """The populated control: 31,668,601 shares, with no invented duration."""
    ts = lpa.time_series("dei:EntityCommonStockSharesOutstanding")

    assert ts.columns.tolist() == COLUMNS
    rows = ts[ts["period_end"] == date(2025, 4, 2)]
    assert len(rows) == 2
    assert set(rows["numeric_value"]) == {LPA_SHARES_2025_04_02}
    assert rows["period_start"].isna().all()
    assert rows["duration_days"].isna().all()
    assert set(rows["fiscal_period"]) == {"FY"}
    assert set(rows["fiscal_year"]) == {2024}


@pytest.mark.fast
def test_lpa_revenue_keeps_its_duration_and_a_filed_zero_stays_zero(lpa):
    """A real duration and a filed zero both survive; neither is filled in."""
    revenue = lpa.time_series("ifrs-full:Revenue")
    fy2024 = revenue[
        (revenue["period_start"] == date(2024, 1, 1))
        & (revenue["period_end"] == date(2024, 12, 31))
    ]
    assert len(fy2024) == 1
    assert fy2024.iloc[0]["numeric_value"] == LPA_REVENUE_FY2024
    assert fy2024.iloc[0]["duration_days"] == 365
    assert fy2024.iloc[0]["fiscal_period"] == "FY"
    assert fy2024.iloc[0]["fiscal_year"] == 2024

    acquisitions = lpa.time_series(
        "ifrs-full:AcquisitionsThroughBusinessCombinationsInvestmentProperty"
    )
    zero = acquisitions[
        (acquisitions["period_start"] == date(2024, 1, 1))
        & (acquisitions["period_end"] == date(2024, 12, 31))
    ]
    assert len(zero) == 1
    assert zero.iloc[0]["numeric_value"] == 0
    assert zero.iloc[0]["duration_days"] == 365


@pytest.mark.fast
def test_snowflake_quarter_and_year_to_date_stay_separate(snow):
    """Two windows that end on the same day stay two rows, with their durations."""
    ts = snow.time_series("us-gaap:NetIncomeLoss", periods=100)
    window = ts[ts["period_end"] == date(2024, 7, 31)]

    assert len(window) == 2
    quarter = window[window["period_start"] == date(2024, 5, 1)].iloc[0]
    ytd = window[window["period_start"] == date(2024, 2, 1)].iloc[0]

    assert quarter["numeric_value"] == SNOW_NET_INCOME_QUARTER
    assert quarter["duration_days"] == 91
    assert quarter["fiscal_period"] == "Q2"
    assert quarter["fiscal_year"] == 2025

    assert ytd["numeric_value"] == SNOW_NET_INCOME_YTD
    assert ytd["duration_days"] == 181
    assert ytd["fiscal_period"] == "Q2"
    assert ytd["fiscal_year"] == 2025
