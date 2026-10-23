"""
Regression test: EarningsRelease.income_statement picked a segment table (Mueller Water) or an
operating-metrics table (Groupon) over the statement of operations.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1781

income_statement took the INCOME_STATEMENT table with the most rows. Segment tables (one
period, a column per segment), reconciliations and metric tables are often longer than the
statement. Candidates are now ranked by ``_income_statement_rank``: revenue and net income
rows, not a reconciliation, columns are distinct periods, then rows. A scale caption row
("(in millions, except per share amounts)") is also no longer the parent of the rows below
it, which had made "Net sales" a per-share row that was left unscaled.
"""

import pandas as pd
import pytest

from edgar import find
from edgar.earnings import (
    EarningsRelease,
    FinancialTable,
    Scale,
    StatementType,
    _classify_row_type,
    _income_statement_rank,
)


def _table(labels, columns, rows):
    df = pd.DataFrame(rows, index=labels, columns=columns).astype(object)
    return FinancialTable(dataframe=df, scale=Scale.MILLIONS, statement_type=StatementType.INCOME_STATEMENT,
                          row_types=[_classify_row_type(label) for label in labels])


STATEMENT = _table(
    ["Net sales", "Operating income", "Net income", "Net income per diluted share"],
    ["Three months ended - September 30, - 2025", "Three months ended - September 30, - 2024"],
    [[380.8, 348.2], [70.0, 20.0], [52.6, 10.0], [0.33, 0.06]],
)
SEGMENTS = _table(
    ["Net sales", "Gross profit", "Operating income", "Adjusted operating income", "Net income",
     "Net income per diluted share", "Depreciation", "Amortization"],
    ["Year ended September 30, 2024 - Water Flow Solutions", "Year ended September 30, 2024 - Consolidated"],
    [[755.5, 1314.7], [1, 2], [3, 4], [5, 6], [None, 115.9], [None, 0.74], [7, 8], [9, 10]],
)


@pytest.mark.regression
def test_statement_outranks_longer_segment_table():
    assert _income_statement_rank(STATEMENT) > _income_statement_rank(SEGMENTS)
    release = EarningsRelease.__new__(EarningsRelease)
    release._tables = [SEGMENTS, STATEMENT]
    assert release.income_statement is STATEMENT
    assert release.get_key_metrics()["eps_diluted"] == pytest.approx(0.33)


@pytest.mark.regression
@pytest.mark.network
@pytest.mark.vcr
def test_issue_1781_mueller_consolidated_statement():
    # Mueller Water Products 8-K 0001350593-25-000054, EX-99.1 condensed consolidated statements
    # of operations (millions): Net sales 380.8, Net income 52.6, diluted EPS 0.33 (quarter) and
    # 1.22 (year ended September 30, 2025)
    earnings = find("0001350593-25-000054").obj().earnings
    df = earnings.income_statement.dataframe
    assert df.loc["Net income per diluted share"].tolist() == [0.33, 0.06, 1.22, 0.74]
    metrics = earnings.get_key_metrics()
    assert metrics["revenue"] == pytest.approx(380_800_000)
    assert metrics["net_income"] == pytest.approx(52_600_000)
    assert metrics["eps_diluted"] == pytest.approx(0.33)


@pytest.mark.regression
@pytest.mark.network
@pytest.mark.vcr
def test_issue_1781_groupon_q2_2025():
    # Groupon 8-K 0001490281-25-000040, EX-99.1 consolidated statement of operations (thousands):
    # Revenue 125,702; Net income 20,593; diluted EPS 0.46
    metrics = find("0001490281-25-000040").obj().earnings.get_key_metrics()
    assert metrics["revenue"] == pytest.approx(125_702_000)
    assert metrics["net_income"] == pytest.approx(20_593_000)
    assert metrics["eps_diluted"] == pytest.approx(0.46)


STATEMENT_LABELS = ["Revenues", "Cost of revenues", "Gross profit", "Selling, general and administrative",
                    "Research and development", "Operating income", "Interest expense", "Other income",
                    "Income before taxes", "Income taxes", "Net income", "Basic", "Diluted",
                    "Weighted average shares, basic", "Weighted average shares, diluted"]


def _filled(labels, columns, value):
    return _table(labels, columns, [[value] * len(columns) for _ in labels])


@pytest.mark.regression
def test_statement_with_unparsed_year_headers_beats_highlights():
    # "Three Months Ended - 2025" does not parse as a period; that is unknown, not a segment split
    statement = _filled(STATEMENT_LABELS, ["Three Months Ended - 2025", "Three Months Ended - 2024"], 10.0)
    highlights = _filled(["Revenues", "Operating income", "Net income", "Diluted EPS"],
                         ["Three Months Ended September 30, 2025", "Three Months Ended September 30, 2024"], 99.0)
    release = EarningsRelease.__new__(EarningsRelease)
    release._tables = [statement, highlights]
    assert release.income_statement is statement


@pytest.mark.regression
def test_statement_with_two_adjusted_rows_is_not_a_reconciliation():
    statement = _filled(STATEMENT_LABELS + ["Adjusted EBITDA", "Adjusted net income"],
                        ["Three Months Ended September 30, 2025", "Three Months Ended September 30, 2024"], 1.0)
    segment = _filled(["Net sales", "Operating income", "Net income"],
                      ["Three Months Ended September 30, 2025 - Segment A",
                       "Three Months Ended September 30, 2025 - Consolidated"], 1.0)
    release = EarningsRelease.__new__(EarningsRelease)
    release._tables = [statement, segment]
    assert release.income_statement is statement
