"""Regression test for GitHub Issue #1696.

``detect_splits`` grouped split-ratio facts by (year, ratio) and dated each
split by ``min(..., key=_split_fact_priority)``. Two 10-Q/10-K instants tie on
that priority, so the first-listed date won. Alphabet tags its 2022 twenty-for-
one split on the announcement (2022-02-01) and the effective date
(2022-07-15); dated by the announcement, the pre-split 10-K and 10-Q filed in
between counted as already restated and were never adjusted. Among facts of
the same kind the latest date now wins.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1696
"""
from datetime import date

import pytest

from edgar.entity.models import FinancialFact
from edgar.entity.parser import EntityFactsParser
from edgar.httprequests import download_json
from edgar.ttm import apply_split_adjustments, detect_splits

pytestmark = pytest.mark.regression

RATIO = "us-gaap:StockholdersEquityNoteStockSplitConversionRatio1"


def _split_fact(instant, form, filed):
    return FinancialFact(concept=RATIO, taxonomy="us-gaap", label="Split ratio", value=20,
                         numeric_value=20.0, unit="pure", period_start=None, period_end=instant,
                         period_type="instant", fiscal_year=2022, fiscal_period="Q3",
                         filing_date=filed, form_type=form)


def _eps(value, start, end, filed):
    return FinancialFact(concept="us-gaap:EarningsPerShareDiluted", taxonomy="us-gaap", label="EPS",
                         value=value, numeric_value=value, unit="USD per share",
                         period_start=start, period_end=end, period_type="duration",
                         fiscal_year=end.year, fiscal_period="FY", filing_date=filed, form_type="10-K")


@pytest.mark.parametrize("order", ["announcement first", "effective first"])
def test_split_tagged_on_two_dates_is_dated_by_the_later_one(order):
    announced = _split_fact(date(2022, 2, 1), "10-Q", date(2022, 10, 26))
    effective = _split_fact(date(2022, 7, 15), "10-Q", date(2022, 10, 26))
    facts = [announced, effective] if order == "announcement first" else [effective, announced]
    assert detect_splits(facts) == [{"date": date(2022, 7, 15), "ratio": 20.0}]


def test_pre_split_fact_filed_between_announcement_and_effective_date_is_adjusted():
    splits = detect_splits([_split_fact(date(2022, 2, 1), "10-Q", date(2022, 4, 27)),
                            _split_fact(date(2022, 7, 15), "10-Q", date(2022, 10, 26))])
    eps = _eps(112.2, date(2021, 1, 1), date(2021, 12, 31), date(2022, 2, 2))
    [adjusted] = apply_split_adjustments([eps], splits)
    # Before the fix: 112.2, treated as already restated.
    assert adjusted.numeric_value == pytest.approx(5.61)


# Alphabet company facts. 10-Q 0001652044-22-000090 tags the split ratio 20 at
# 2022-02-01 and 2022-07-15. FY2021 diluted EPS 112.20 (10-K 0001652044-22-000019,
# filed 2022-02-02); Q1 2022 diluted EPS 24.62 (10-Q 0001652044-22-000029, filed
# 2022-04-27). Both precede the split taking effect.
GOOGL_FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK0001652044.json"


@pytest.mark.vcr
def test_alphabet_pre_split_eps_is_restated_to_the_post_split_basis():
    facts = EntityFactsParser.parse_company_facts(download_json(GOOGL_FACTS))
    assert [s for s in detect_splits(list(facts)) if s["date"].year == 2022] == [
        {"date": date(2022, 7, 15), "ratio": 20.0}]

    adjusted = {(f.period_start, f.period_end, f.accession): f.numeric_value
                for f in facts._get_split_adjusted_facts()
                if f.concept.endswith("EarningsPerShareDiluted")}
    # Before the fix: 112.2 and 24.62, left on the pre-split basis.
    assert adjusted[(date(2021, 1, 1), date(2021, 12, 31), "0001652044-22-000019")] == pytest.approx(5.61)
    assert adjusted[(date(2022, 1, 1), date(2022, 3, 31), "0001652044-22-000029")] == pytest.approx(1.231)
