"""MultiFinancials.income_statement() forwards include_quarterly.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1783

``XBRLS.statements.income_statement(include_quarterly=True)`` already surfaces a
filed discrete quarter beside the year-to-date column. ``MultiFinancials`` only
accepted ``view``, so the same keyword raised ``TypeError``. The wrapper now
takes keyword-only ``include_quarterly=False`` and passes it through. It does
not derive a quarter or fill a value the filing did not report.

Ground truth from tracked fixtures:

- Apple 10-Q for the quarter ended 2023-07-01, accession
  ``0000320193-23-000077`` (``tests/fixtures/xbrl/aapl/10q_2023``): three-month
  net sales of $81,797 million on ``duration_2023-04-02_2023-07-01`` and
  nine-month net sales of $293,787 million on ``duration_2022-09-25_2023-07-01``.
- Apple 10-K for the year ended 2023-09-30, accession
  ``0000320193-23-000106`` (``tests/fixtures/xbrl/aapl/10k_2023``): annual net
  sales of $383,285 million on ``duration_2022-09-25_2023-09-30``. That filing
  has no quarterly income-statement facts, so the opt-in must not add a quarter.
"""
import inspect
from pathlib import Path

import pytest

from edgar.financials import MultiFinancials
from edgar.xbrl import XBRL, XBRLS

pytestmark = pytest.mark.fast

AAPL_10Q = Path("tests/fixtures/xbrl/aapl/10q_2023")
AAPL_10K = Path("tests/fixtures/xbrl/aapl/10k_2023")
NET_SALES = "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax"
Q3 = "duration_2023-04-02_2023-07-01"
Q3_YTD = "duration_2022-09-25_2023-07-01"
FY2023 = "duration_2022-09-25_2023-09-30"


@pytest.fixture(scope="module")
def apple_pair():
    """Apple's FY2023 10-K and the following 10-Q, parsed once."""
    xbs = XBRLS.from_xbrl_objects([
        XBRL.from_directory(AAPL_10K),
        XBRL.from_directory(AAPL_10Q),
    ])
    return xbs, MultiFinancials(xbs)


def _net_sales(statement):
    items = statement.statement_data["statement_data"]
    item = next(row for row in items if row["concept"] == NET_SALES)
    return item["values"]


def test_include_quarterly_is_keyword_only_and_defaults_false():
    signature = inspect.signature(MultiFinancials.income_statement)
    parameters = list(signature.parameters.values())
    view, include_quarterly = parameters[1], parameters[2]
    assert view.name == "view"
    assert view.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert view.default is None
    assert include_quarterly.name == "include_quarterly"
    assert include_quarterly.kind is inspect.Parameter.KEYWORD_ONLY
    assert include_quarterly.default is False


def test_default_stays_year_to_date_and_opt_in_adds_the_filed_quarter(apple_pair):
    xbs, multi = apple_pair
    default = _net_sales(multi.income_statement())
    quarterly = _net_sales(multi.income_statement(include_quarterly=True))

    assert default == {
        FY2023: 383_285_000_000.0,
        Q3_YTD: 293_787_000_000.0,
    }
    assert quarterly == {
        FY2023: 383_285_000_000.0,
        Q3: 81_797_000_000.0,
        Q3_YTD: 293_787_000_000.0,
    }
    assert default == _net_sales(xbs.statements.income_statement())
    assert quarterly == _net_sales(xbs.statements.income_statement(include_quarterly=True))


def test_positional_view_is_preserved_with_and_without_the_option(apple_pair):
    xbs, multi = apple_pair
    positional = multi.income_statement("detailed")
    assert positional.include_dimensions is True
    assert _net_sales(positional) == _net_sales(multi.income_statement(view="detailed"))
    assert _net_sales(positional) == _net_sales(xbs.statements.income_statement(view="detailed"))

    positional_q = multi.income_statement("detailed", include_quarterly=True)
    assert positional_q.include_dimensions is True
    sales = _net_sales(positional_q)
    assert sales[Q3] == 81_797_000_000.0
    assert sales == _net_sales(multi.income_statement(view="detailed", include_quarterly=True))
    assert sales == _net_sales(xbs.statements.income_statement(view="detailed", include_quarterly=True))


def test_annual_filing_does_not_gain_an_invented_quarter():
    xbs = XBRLS.from_xbrl_objects([XBRL.from_directory(AAPL_10K)])
    multi = MultiFinancials(xbs)
    default = _net_sales(multi.income_statement())
    quarterly = _net_sales(multi.income_statement(include_quarterly=True))

    assert default == {FY2023: 383_285_000_000.0}
    assert quarterly == default
    assert quarterly == _net_sales(xbs.statements.income_statement(include_quarterly=True))
