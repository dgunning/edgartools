"""Regression test for GH #1839: an F-4's income statement rendered with no period columns.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1839

NLS Pharmaceutics' F-4 carries no DocumentFiscalPeriodFocus, no period end date
and no annual-report flag, so ``_select_duration_periods`` treated it as
quarterly. Its statements are full years, which neither the 80-100 day quarter
bucket nor the YTD bucket holds, so the selector returned no candidates and the
correctly resolved income statement rendered empty. When a filing is not
declared annual and the quarterly path finds nothing, its annual periods are
now offered.

Ground truth: NLS Pharmaceutics F-4 filed 2024-12-30 (0001213900-24-113211),
R4 "Statements of Operations and Comprehensive Loss", year ended December 31,
2023: net loss (12,172,029) USD and comprehensive loss (12,279,309) USD.
"""
import pytest

from edgar import find
from edgar.xbrl.period_selector import _select_duration_periods


def _duration(start, end, days):
    return {'type': 'duration', 'start_date': start, 'end_date': end, 'days': days,
            'key': f'duration_{start}_{end}', 'label': f'{start} to {end}'}


@pytest.mark.fast
def test_undeclared_filing_with_only_annual_statements_gets_annual_periods():
    periods = [_duration('2024-03-01', '2024-03-31', 31),
               _duration('2023-01-01', '2023-12-31', 365),
               _duration('2022-01-01', '2022-12-31', 365),
               _duration('2021-01-01', '2021-12-31', 365)]
    entity_info = {'fiscal_period': None, 'document_type': 'F-4', 'annual_report': False,
                   'quarterly_report': False}
    selected = [key for key, _ in _select_duration_periods(periods, entity_info, 4, None)]
    assert selected == ['duration_2023-01-01_2023-12-31', 'duration_2022-01-01_2022-12-31',
                        'duration_2021-01-01_2021-12-31']  # was []


@pytest.mark.fast
def test_a_quarterly_filing_does_not_fall_back_to_annual_periods():
    periods = [_duration('2024-04-01', '2024-06-30', 90),
               _duration('2023-01-01', '2023-12-31', 365)]
    entity_info = {'fiscal_period': 'Q2', 'document_type': '10-Q', 'quarterly_report': True}
    selected = [key for key, _ in _select_duration_periods(periods, entity_info, 4, '2024-06-30')]
    assert selected == ['duration_2024-04-01_2024-06-30']


@pytest.mark.network
def test_nls_f4_default_income_render_has_the_annual_values():
    statement = find("0001213900-24-113211").xbrl().statements.income_statement()
    assert statement.role_or_type == "http://www.nlspharma.com/role/ConsolidatedIncomeStatement"
    df = statement.to_dataframe()
    plain = df[df["dimension"] != True]  # noqa: E712
    net_loss = plain[plain["concept"] == "us-gaap_NetIncomeLoss"].iloc[0]
    comprehensive = plain[plain["concept"] == "us-gaap_ComprehensiveIncomeNetOfTax"].iloc[0]
    assert net_loss["2023-12-31 (FY)"] == -12_172_029  # the frame had no period columns
    assert comprehensive["2023-12-31 (FY)"] == -12_279_309
    assert [c for c in df.columns if c.endswith("(FY)")] == ["2023-12-31 (FY)", "2022-12-31 (FY)",
                                                             "2021-12-31 (FY)"]
