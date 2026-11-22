"""
Regression test for GitHub issue #1842: a BDC's total investment income was
standardized as NonoperatingIncomeExpense

``us-gaap:GrossInvestmentIncomeOperating`` is an investment company's operating
total (interest + dividends + fees). ``gaap_mappings.json`` mapped it to
``NonoperatingIncomeExpense``, so ``standard_concept`` called the top line of
every BDC statement of operations nonoperating. #1915 removed the mapping; the
follow-up decision (bead edgartools-k7mi8.6) maps it to ``Revenue``, the
investment company's top line, so it is never nonoperating.

Ground truth (read from the filings):
- Golub Capital BDC 10-Q for the quarter ended 2025-03-31, accession
  0001476765-25-000040 (tracked fixture): total investment income $213,892,000
  for the quarter.
- Barings BDC 10-Q for the quarter ended 2026-06-30, accession
  0001379785-26-000030 (the filing in the issue): total investment income
  $65,202,000 for the quarter.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1842
"""

from pathlib import Path

import pandas as pd
import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.standardization.reverse_index import get_reverse_index

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "xbrl" / "gbdc"
CONCEPT = "us-gaap_GrossInvestmentIncomeOperating"


def _total_investment_income_row(statement) -> pd.Series:
    df = statement.to_dataframe(standard=True, presentation=False)
    rows = df[(df["concept"] == CONCEPT) & (df["label"] == "Total investment income")]
    assert len(rows) == 1
    return rows.iloc[0]


def test_gross_investment_income_operating_has_no_nonoperating_mapping():
    result = get_reverse_index().lookup("us-gaap:GrossInvestmentIncomeOperating")
    assert result.standard_concepts == ["Revenue"]  # edgartools-k7mi8.6; was None after #1915


def test_gbdc_total_investment_income_is_not_nonoperating():
    statement = XBRL.from_directory(FIXTURE).statements.income_statement()
    row = _total_investment_income_row(statement)
    assert row["standard_concept"] == "Revenue"
    assert row["2025-03-31 (Q2)"] == 213_892_000


@pytest.mark.network
def test_bbdc_total_investment_income_is_not_nonoperating():
    from edgar import get_by_accession_number

    xbrl = get_by_accession_number("0001379785-26-000030").xbrl()
    statement = xbrl.statements[
        "http://ir.barings.com/role/UnauditedConsolidatedStatementsofOperations"]
    row = _total_investment_income_row(statement)
    assert row["standard_concept"] == "Revenue"
    assert row["2026-06-30 (Q2)"] == 65_202_000
