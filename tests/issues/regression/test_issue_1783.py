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
  nine-month net sales of $293,787 million on ``duration_2022-09-25_2023-07-01``,
  both filed at decimals ``-6``.
- Apple 10-K for the year ended 2023-09-30, accession
  ``0000320193-23-000106`` (``tests/fixtures/xbrl/aapl/10k_2023``): annual net
  sales of $383,285 million on ``duration_2022-09-25_2023-09-30``. That filing
  has no separate quarterly duration, so the opt-in must not add one.
"""
import inspect
from pathlib import Path

import pandas as pd
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
    """The 10-K then the 10-Q, the order the period assertions below pin."""
    xbs = XBRLS.from_xbrl_objects([
        XBRL.from_directory(AAPL_10K),
        XBRL.from_directory(AAPL_10Q),
    ])
    return xbs, MultiFinancials(xbs)


def _net_sales_item(statement):
    items = statement.statement_data["statement_data"]
    return next(item for item in items if item["concept"] == NET_SALES)


def _period_columns(frame):
    skip = {"label", "concept", "standard_concept", "preferred_sign"}
    return [column for column in frame.columns if column not in skip]


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
    default = multi.income_statement()
    direct_default = xbs.statements.income_statement()

    assert default.statement_data["periods"] == [
        (FY2023, "FY Sep 30, 2023"),
        (Q3_YTD, "Q3 YTD Jul 1, 2023"),
    ]
    default_sales = _net_sales_item(default)
    assert default_sales["values"] == {
        FY2023: 383_285_000_000.0,
        Q3_YTD: 293_787_000_000.0,
    }
    assert default_sales["decimals"] == {FY2023: -6, Q3_YTD: -6}
    default_frame = default.to_dataframe()
    assert _period_columns(default_frame) == ["2023-09-30", "2023-07-01"]
    assert default_frame.loc[default_frame.concept == NET_SALES, "2023-07-01"].iloc[0] == 293_787_000_000
    pd.testing.assert_frame_equal(default_frame, direct_default.to_dataframe())

    quarterly = multi.income_statement(include_quarterly=True)
    direct_quarterly = xbs.statements.income_statement(include_quarterly=True)
    assert quarterly.statement_data["periods"] == [
        (FY2023, "FY Sep 30, 2023"),
        (Q3, "Q3 Jul 1, 2023"),
        (Q3_YTD, "Q3 YTD Jul 1, 2023"),
    ]
    quarterly_sales = _net_sales_item(quarterly)
    assert quarterly_sales["values"] == {
        FY2023: 383_285_000_000.0,
        Q3: 81_797_000_000.0,
        Q3_YTD: 293_787_000_000.0,
    }
    assert quarterly_sales["decimals"] == {FY2023: -6, Q3: -6, Q3_YTD: -6}
    quarterly_frame = quarterly.to_dataframe()
    row = quarterly_frame.loc[quarterly_frame.concept == NET_SALES].iloc[0]
    assert _period_columns(quarterly_frame) == ["2023-09-30", "Q3 Jul 1, 2023", "Q3 YTD Jul 1, 2023"]
    assert row["2023-09-30"] == 383_285_000_000
    assert row["Q3 Jul 1, 2023"] == 81_797_000_000
    assert row["Q3 YTD Jul 1, 2023"] == 293_787_000_000
    pd.testing.assert_frame_equal(quarterly_frame, direct_quarterly.to_dataframe())

    # The opt-in must not stick to the shared XBRLS cache.
    again = multi.income_statement()
    assert again.statement_data["periods"] == default.statement_data["periods"]
    pd.testing.assert_frame_equal(again.to_dataframe(), default_frame)


def test_positional_view_is_preserved_with_and_without_the_option(apple_pair):
    xbs, multi = apple_pair
    positional = multi.income_statement("detailed")
    keyword = multi.income_statement(view="detailed")
    direct = xbs.statements.income_statement(view="detailed")
    pd.testing.assert_frame_equal(positional.to_dataframe(), keyword.to_dataframe())
    pd.testing.assert_frame_equal(positional.to_dataframe(), direct.to_dataframe())

    positional_q = multi.income_statement("detailed", include_quarterly=True)
    keyword_q = multi.income_statement(view="detailed", include_quarterly=True)
    direct_q = xbs.statements.income_statement(view="detailed", include_quarterly=True)
    pd.testing.assert_frame_equal(positional_q.to_dataframe(), keyword_q.to_dataframe())
    pd.testing.assert_frame_equal(positional_q.to_dataframe(), direct_q.to_dataframe())
    row = positional_q.to_dataframe()
    sales = row.loc[row.concept == NET_SALES].iloc[0]
    assert sales["Q3 Jul 1, 2023"] == 81_797_000_000


def test_annual_filing_does_not_gain_an_invented_quarter():
    xbs = XBRLS.from_xbrl_objects([XBRL.from_directory(AAPL_10K)])
    multi = MultiFinancials(xbs)
    default = multi.income_statement()
    quarterly = multi.income_statement(include_quarterly=True)

    assert default.statement_data["periods"] == [(FY2023, "FY Sep 30, 2023")]
    assert quarterly.statement_data["periods"] == [(FY2023, "FY Sep 30, 2023")]
    sales = _net_sales_item(quarterly)
    assert sales["values"] == {FY2023: 383_285_000_000.0}
    assert sales["decimals"] == {FY2023: -6}
    pd.testing.assert_frame_equal(
        quarterly.to_dataframe(),
        xbs.statements.income_statement(include_quarterly=True).to_dataframe(),
    )
