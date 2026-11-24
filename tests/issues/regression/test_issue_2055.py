"""Balance-sheet validation ignored temporary (mezzanine) equity.

GitHub Issue: https://github.com/dgunning/edgartools/issues/2055

When a balance sheet has no combined Liabilities and Equity total, the
validator checks Assets = Liabilities + Equity (+ noncontrolling interest).
Temporary equity (redeemable preferred stock, shares subject to redemption,
redeemable noncontrolling interests) is in neither total, so a filer that
carries it was reported invalid although its sheet balances.

Ground truth, read from SEC's companyconcept API for each accession:

    Gladstone Capital 10-K 0001143513-26-000014, 2026-09-30:
        Assets 973,474,000 = Liabilities 453,111,000 + StockholdersEquity 469,298,000
                             + TemporaryEquityCarryingAmountAttributableToParent 51,065,000
    Remora Capital 10-Q 0001213900-26-055928, 2026-03-31:
        Assets 263,654,000 = Liabilities 66,866,000 + StockholdersEquity 193,461,000
                             + TemporaryEquityCarryingAmountAttributableToParent 3,327,000

Over the 29 filers in SEC's 2025 Q3/Q4 frames that report temporary equity but
no combined total, the fix moves 2 from invalid to valid and none the other way.
"""
import pandas as pd
import pytest

from edgar import find
from edgar.xbrl.validation import validate_balance_sheet

PERIOD = "2026-09-30"


def _frame(rows):
    """A one-period balance-sheet frame from (concept, value) pairs."""
    return pd.DataFrame(
        [{"label": concept, "concept": f"us-gaap_{concept}", PERIOD: float(value)} for concept, value in rows]
    )


GLADSTONE = [
    ("Assets", 973_474_000),
    ("Liabilities", 453_111_000),
    ("TemporaryEquityCarryingAmountAttributableToParent", 51_065_000),
    ("StockholdersEquity", 469_298_000),
]


@pytest.mark.fast
def test_temporary_equity_balances_the_component_equation():
    result = validate_balance_sheet(_frame(GLADSTONE))

    # Before the fix: invalid, Assets 973,474,000 != 453,111,000 + 469,298,000.
    assert result.status == "valid"
    check = result.metadata["equation_check"]
    assert check["temporary_equity"] == 51_065_000
    assert check["expected"] == 973_474_000


@pytest.mark.fast
def test_redeemable_nci_is_added_to_the_parents_temporary_equity():
    rows = [("Assets", 1_000), ("Liabilities", 500), ("StockholdersEquity", 400),
            ("TemporaryEquityCarryingAmountAttributableToParent", 60),
            ("RedeemableNoncontrollingInterestEquityCarryingAmount", 40)]
    result = validate_balance_sheet(_frame(rows))

    assert result.status == "valid"
    assert result.metadata["equation_check"]["temporary_equity"] == 100


@pytest.mark.fast
def test_the_inclusive_total_is_not_added_to_its_own_parts():
    rows = [("Assets", 1_000), ("Liabilities", 500), ("StockholdersEquity", 400),
            ("TemporaryEquityCarryingAmountIncludingPortionAttributableToNoncontrollingInterests", 100),
            ("TemporaryEquityCarryingAmountAttributableToParent", 60),
            ("RedeemableNoncontrollingInterestEquityCarryingAmount", 40)]
    result = validate_balance_sheet(_frame(rows))

    assert result.status == "valid"
    assert result.metadata["equation_check"]["temporary_equity"] == 100


@pytest.mark.fast
def test_combined_total_check_is_unchanged():
    """With a combined total the equation never reads the components, so nothing is double-counted."""
    rows = GLADSTONE + [("LiabilitiesAndStockholdersEquity", 973_474_000)]
    result = validate_balance_sheet(_frame(rows))

    assert result.status == "valid"
    assert "equation_check" not in result.metadata


@pytest.mark.fast
def test_a_real_imbalance_still_names_temporary_equity():
    rows = [("Assets", 1_000_000), ("Liabilities", 500_000), ("StockholdersEquity", 400_000),
            ("TemporaryEquityCarryingAmountAttributableToParent", 50_000)]
    result = validate_balance_sheet(_frame(rows))

    assert result.status == "invalid"
    [issue] = result.errors
    assert issue.message == ("Accounting equation doesn't balance: Assets (1,000,000) != Liabilities (500,000) + "
                             "Temporary Equity (50,000) + Equity (400,000)")


# Live, not a cassette: Gladstone's filing carries a large schedule of investments and the two
# recordings came to 23 MB. The fast tests above pin the same values offline.
@pytest.mark.network
@pytest.mark.parametrize(("accession", "temporary_equity"), [
    ("0001143513-26-000014", 51_065_000),   # Gladstone Capital 10-K, 2026-09-30
    ("0001213900-26-055928", 3_327_000),    # Remora Capital 10-Q, 2026-03-31
])
def test_filings_with_temporary_equity_validate(accession, temporary_equity):
    result = find(accession).xbrl().statements.balance_sheet().validate()

    assert result.status == "valid"
    assert result.metadata["equation_check"]["temporary_equity"] == temporary_equity
