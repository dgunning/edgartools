"""
Regression test for GitHub issue #1783: MultiFinancials.income_statement() had no include_quarterly

The stitch under it (``XBRLS.statements.income_statement``) has accepted
``include_quarterly`` since GH #780, but ``MultiFinancials.income_statement()``
took only ``view``, so ``include_quarterly=True`` raised ``TypeError`` and the
discrete quarter of a 10-Q was reachable only through ``multi.xbs``.
``cash_flow_statement()`` had the same gap against the same stitch.

Ground truth, from the tracked fixtures (read offline):
- Apple 10-Q for the quarter ended 2023-07-01, accession 0000320193-23-000077:
  net sales $81,797M for the quarter, $293,787M for the nine months.
- Apple 10-K for FY2023, accession 0000320193-23-000106: net sales $383,285M.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1783
"""

from pathlib import Path

import pytest

from edgar import MultiFinancials
from edgar.xbrl import XBRL, XBRLS

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "xbrl" / "aapl"
REVENUE = "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax"
META = {"label", "concept", "standard_concept", "preferred_sign"}


@pytest.fixture(scope="module")
def multi() -> MultiFinancials:
    return MultiFinancials(XBRLS([XBRL.from_directory(FIXTURES / "10k_2023"),
                                  XBRL.from_directory(FIXTURES / "10q_2023")]))


def _revenue(statement) -> dict:
    df = statement.to_dataframe()
    row = df[df["concept"] == REVENUE].iloc[0]
    return {c: row[c] for c in df.columns if c not in META}


def test_include_quarterly_surfaces_the_filed_quarter(multi):
    assert _revenue(multi.income_statement(include_quarterly=True)) == {
        "2023-09-30": 383_285_000_000,
        "Q3 Jul 1, 2023": 81_797_000_000,
        "Q3 YTD Jul 1, 2023": 293_787_000_000,
    }


def test_default_stays_year_to_date(multi):
    assert _revenue(multi.income_statement()) == {
        "2023-09-30": 383_285_000_000,
        "2023-07-01": 293_787_000_000,
    }


def test_cash_flow_statement_takes_it_too(multi):
    columns = [c for c in multi.cash_flow_statement(include_quarterly=True).to_dataframe().columns
               if c not in META]
    assert "Q3 YTD Jul 1, 2023" in columns


def test_include_quarterly_is_keyword_only(multi):
    with pytest.raises(TypeError):
        multi.income_statement(None, True)
