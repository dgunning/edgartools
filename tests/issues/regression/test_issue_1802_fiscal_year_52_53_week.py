"""52/53-week filers got the wrong fiscal year, and EntityFacts dropped a year.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1802

XBRL: ``_fiscal_year_for_date`` compared each date with this filing's exact
year-end day and moved anything later into the next fiscal year. A 52/53-week
year-end day moves every year, so a prior year that closed a day later in the
month was labelled a year ahead. Sprouts' FY2021 10-K (year end ``--01-02``)
labelled the years ending 2022-01-02 and 2021-01-03 both 2022, so
``by_fiscal_year(2021)`` found nothing. Apple, Intel and Costco comparatives had
the same drift. The parser now uses the EntityFacts rule
(``edgar.dates.calculate_fiscal_year_for_label``), which compares the month only
and treats a year end in the first week of a month as the previous month's year.

EntityFacts: annual periods were grouped by calendar year, so a filer that
closes two fiscal years in one calendar year (SFM: 2023-01-01 and 2023-12-31)
kept only one. They are now grouped by the fiscal year they close. For that to
work, ``detect_fiscal_year_end`` has to count a year end in the first week of a
month as the previous month: Krispy Kreme's year ends mostly fall on 1-3
January, so it detected a January year end and labelled its December years a
year ahead.

Ground truth, read from the filings' XBRL:
- SFM 10-K 0000950170-22-001976: DocumentFiscalYearFocus 2021,
  CurrentFiscalYearEndDate --01-02, FY2021 (ends 2022-01-02) ProfitLoss
  244,157,000.
- SFM FY2022 (ends 2023-01-01) NetIncomeLoss 261,164,000 (companyfacts).
- AAPL 10-K 0000320193-26-000026: --09-26, prior years end 2025-09-27 and
  2024-09-28.
- COST 10-K 0000909832-26-000093: --08-30, prior years end 2025-08-31 and
  2024-09-01.
- INTC 10-K 0000050863-26-000011: --12-27, prior year ends 2024-12-28.
- CAKE 10-K 0001104659-24-027565: --01-02, year ends 2024-01-02. The company
  calls that fiscal 2023, although its DEI fiscal year says 2024.
"""
from datetime import date

import pytest

from edgar import Company, find
from edgar.dates import fiscal_year_end_month
from edgar.xbrl.parsers.instance import _fiscal_year_for_date


@pytest.mark.parametrize("period_end, fy_end, expected", [
    # SFM, --01-02
    (date(2022, 1, 2), (1, 2), 2021),
    (date(2021, 1, 3), (1, 2), 2020),
    (date(2019, 12, 29), (1, 2), 2019),
    (date(2022, 4, 3), (1, 2), 2022),     # Q1 of FY2022
    # CAKE, --01-02
    (date(2024, 1, 2), (1, 2), 2023),
    (date(2023, 1, 3), (1, 2), 2022),
    # AAPL, --09-26
    (date(2026, 9, 26), (9, 26), 2026),
    (date(2025, 9, 27), (9, 26), 2025),
    (date(2024, 9, 28), (9, 26), 2024),
    (date(2025, 12, 27), (9, 26), 2026),  # Q1 of FY2026
    # COST, --08-30
    (date(2025, 8, 31), (8, 30), 2025),
    (date(2024, 9, 1), (8, 30), 2024),
    # INTC, --12-27
    (date(2024, 12, 28), (12, 27), 2024),
    # Unchanged: NVDA (January), MSFT (June), a calendar-year filer
    (date(2026, 1, 25), (1, 25), 2026),
    (date(2025, 10, 26), (1, 25), 2026),
    (date(2025, 6, 30), (6, 30), 2025),
    (date(2025, 9, 30), (6, 30), 2026),
    (date(2025, 12, 31), (12, 31), 2025),
])
def test_fiscal_year_compares_the_month_not_the_day(period_end, fy_end, expected):
    assert _fiscal_year_for_date(period_end, *fy_end) == expected


@pytest.mark.parametrize("month, day, expected", [
    (1, 2, 12),    # SFM, CAKE, DNUT: a December year that closed on 2 January
    (1, 1, 12),
    (9, 3, 8),     # COST: an August year that closed on 3 September
    (2, 1, 1),     # HD: a January year that closed on 1 February
    (1, 8, 1),     # past the first week: its own month
    (9, 26, 9),    # AAPL
    (12, 31, 12),
])
def test_a_first_week_year_end_belongs_to_the_previous_month(month, day, expected):
    assert fiscal_year_end_month(month, day) == expected


@pytest.mark.vcr
def test_sfm_fy2021_10k_labels_each_year_once():
    xbrl = find("0000950170-22-001976").xbrl()

    annual = {p["end_date"]: p["fiscal_year"] for p in xbrl.reporting_periods
              if p["type"] == "duration" and p.get("fiscal_period") == "FY"}
    assert annual["2022-01-02"] == 2021
    assert annual["2021-01-03"] == 2020
    assert annual["2019-12-29"] == 2019

    facts = xbrl.facts.query().by_fiscal_year(2021).by_concept("ProfitLoss").to_dataframe()
    facts = facts[~facts.is_dimensioned & (facts.fiscal_period == "FY")]
    assert facts[["period_end", "numeric_value"]].drop_duplicates().values.tolist() == [
        ["2022-01-02", 244157000.0]
    ]


@pytest.mark.vcr
def test_sfm_entity_facts_keeps_both_years_closed_in_2023():
    df = Company("SFM").income_statement(periods=7, annual=True).to_dataframe()

    assert "FY 2022" in df.columns
    net_income = df[df["label"] == "Net Income (Loss) Attributable to Parent"]
    assert net_income["FY 2022"].iloc[0] == 261164000
    assert net_income["FY 2021"].iloc[0] == 244157000
