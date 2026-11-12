"""The balance-sheet equation check mishandled operands that are zero.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1210

Two zero-handling defects in ``validate_balance_sheet``, reported in synfonia's
#1210 design ("Source meaning and rendering"):

* zero total assets forced the relative difference to 0, so the percentage
  tolerance always passed and assets of 0 against liabilities and equity of
  1,000,000,000 reported no imbalance;
* the equity selector was an ``or`` chain, so a reported total equity of 0 was
  discarded: it fell through to parent equity (a false imbalance of 50 below)
  or, with no parent row, to INCOMPLETE_DATA.

These are arithmetic edge cases, so the frames are small and synthetic rather
than taken from a filing. No tracked fixture balance sheet reports a zero
total; over the 28 tracked balance sheets at all three levels the outcome is
unchanged (see the PR).
"""
import pandas as pd
import pytest

from edgar.xbrl.validation import validate_balance_sheet

pytestmark = pytest.mark.fast

PERIOD = "2024-12-31"


def _frame(rows):
    """A one-period standardized balance-sheet frame from (concept, value) pairs."""
    return pd.DataFrame(
        [{"label": concept, "concept": f"us-gaap_{concept}", PERIOD: float(value)} for concept, value in rows]
    )


def test_zero_assets_against_nonzero_liabilities_and_equity_is_an_imbalance():
    df = _frame([("Assets", 0), ("LiabilitiesAndStockholdersEquity", 1_000_000_000)])
    result = validate_balance_sheet(df)
    assert result.is_valid is False
    [issue] = result.errors
    assert issue.code == "EQUATION_IMBALANCE"
    assert issue.details["difference"] == 1_000_000_000
    assert result.metadata["liab_equity_check"]["difference_pct"] == 1_000_000_000


def test_zero_assets_in_component_equation_is_an_imbalance():
    df = _frame([("Assets", 0), ("Liabilities", 600), ("StockholdersEquity", 400)])
    result = validate_balance_sheet(df)
    assert [i.code for i in result.errors] == ["EQUATION_IMBALANCE"]
    assert result.metadata["equation_check"]["difference"] == 1000


def test_zero_assets_balanced_by_zero_is_valid():
    df = _frame([("Assets", 0), ("LiabilitiesAndStockholdersEquity", 0)])
    result = validate_balance_sheet(df)
    assert result.is_valid is True
    assert result.issues == []
    assert result.metadata["liab_equity_check"]["difference_pct"] == 0


def test_zero_total_equity_is_used_not_parent_equity():
    # Assets 500 = liabilities 500 + total equity 0 (parent -50 + NCI 50).
    df = _frame([
        ("Assets", 500),
        ("Liabilities", 500),
        ("StockholdersEquity", -50),
        ("MinorityInterest", 50),
        ("StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest", 0),
    ])
    result = validate_balance_sheet(df)
    assert result.is_valid is True
    assert [i.code for i in result.issues] == []
    check = result.metadata["equation_check"]
    assert check["equity"] == 0
    assert check["nci"] is None
    assert check["expected"] == 500
    assert check["difference"] == 0


def test_zero_total_equity_without_parent_row_is_evaluated():
    df = _frame([
        ("Assets", 500),
        ("Liabilities", 500),
        ("StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest", 0),
    ])
    result = validate_balance_sheet(df)
    assert "INCOMPLETE_DATA" not in [i.code for i in result.issues]
    assert result.metadata["equation_check"]["equity"] == 0
    assert result.metadata["equation_check"]["difference"] == 0


def test_nonzero_cases_keep_their_outcome():
    # Parent equity plus NCI is still used when no total-equity row exists.
    df = _frame([("Assets", 500), ("Liabilities", 300), ("StockholdersEquity", 150), ("MinorityInterest", 50)])
    result = validate_balance_sheet(df)
    assert result.is_valid is True
    assert result.metadata["equation_check"]["expected"] == 500
    # A 0.05% gap on large assets stays inside the percentage tolerance.
    df = _frame([("Assets", 2_000_000), ("LiabilitiesAndStockholdersEquity", 2_001_000)])
    result = validate_balance_sheet(df)
    assert result.is_valid is True
    assert [i.code for i in result.issues] == ["ROUNDING_ADJUSTMENT"]
