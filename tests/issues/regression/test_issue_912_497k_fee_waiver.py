"""
Regression test for GH #912 / edgartools-c0f0.

`Prospectus497K` reported the *net* expense ratio in `fee_waiver` and left
`net_expenses` empty for every 497K whose fee table uses the standard SEC
wording "Total Annual Fund Operating Expenses After Fee Waiver and
Reimbursement". The elif chain in `_extract_operating_expenses` tested
'fee waiver' in the label before the net-expense branch, so the net row
matched the waiver branch, overwrote the real waiver value, and made the
net_expenses branch unreachable.

Ground truth is hand-verified from the fee table of the filing named in the
issue: https://www.sec.gov/Archives/edgar/data/1314414/000158064224004234/

    Management Fees                                                    0.65%
    Distribution and Service (12b-1) Fees                              0.00%
    Other Expenses (1)                                                 0.32%
    Acquired Fund Fees and Expenses (1)(2)                             0.29%
    Total Annual Fund Operating Expenses                               1.26%
    Fee Waiver and Reimbursement (3)                                 (0.19)%
    Total Annual Fund Operating Expenses after Fee Waiver ...          1.07%
"""
from decimal import Decimal

import pytest

from edgar import find
from edgar.funds._497k_tables import _extract_operating_expenses
from edgar.funds.prospectus497k import Prospectus497K

# The 497K named in GH #912: Ocean Park High Income ETF, series S000085658.
OCEAN_PARK_ACCESSION = "0001580642-24-004234"


def _ocean_park_class(prospectus: Prospectus497K):
    """The real share class, ignoring any phantom classes (see edgartools-5owe)."""
    for share_class in prospectus.share_classes:
        if share_class.total_annual_expenses is not None:
            return share_class
    raise AssertionError("no share class carried operating-expense data")


class TestFeeWaiverIsNotTheNetRatio:
    """The waiver and the net ratio land in their own fields."""

    @pytest.fixture(scope="class")
    def prospectus(self):
        prospectus = find(OCEAN_PARK_ACCESSION).obj()
        assert isinstance(prospectus, Prospectus497K)
        return prospectus

    @pytest.mark.network
    @pytest.mark.vcr
    def test_waiver_and_net_are_distinct_values(self, prospectus):
        share_class = _ocean_park_class(prospectus)

        # Before the fix: fee_waiver == Decimal("1.07"), net_expenses is None.
        assert share_class.total_annual_expenses == Decimal("1.26")
        assert share_class.fee_waiver == Decimal("-0.19")
        assert share_class.net_expenses == Decimal("1.07")

    @pytest.mark.network
    @pytest.mark.vcr
    def test_waiver_reconciles_total_to_net(self, prospectus):
        share_class = _ocean_park_class(prospectus)
        assert (
            share_class.total_annual_expenses + share_class.fee_waiver
            == share_class.net_expenses
        )

    @pytest.mark.network
    @pytest.mark.vcr
    def test_fees_dataframe_exposes_both(self, prospectus):
        row = prospectus.fees.iloc[0]
        assert row["fee_waiver"] == Decimal("-0.19")
        assert row["net_expenses"] == Decimal("1.07")


class TestFeeLabelRouting:
    """Label routing, exercised directly so no network access is needed."""

    def test_standard_after_waiver_wording_is_the_net_ratio(self):
        rows = [
            ["Annual Fund Operating Expenses", ""],
            ["Management Fees", "0.65%"],
            ["Total Annual Fund Operating Expenses", "1.26%"],
            ["Fee Waiver and Reimbursement (3)", "(0.19)%"],
            [
                "Total Annual Fund Operating Expenses after Fee Waiver and Reimbursement",
                "1.07%",
            ],
        ]
        data = _extract_operating_expenses(rows)[0]

        assert data["total_annual_expenses"] == Decimal("1.26")
        assert data["fee_waiver"] == Decimal("-0.19")
        assert data["net_expenses"] == Decimal("1.07")

    def test_net_annual_wording_is_recognized(self):
        rows = [
            ["Annual Fund Operating Expenses", ""],
            ["Total Annual Fund Operating Expenses", "1.26%"],
            ["Less Fee Waiver and/or Expense Reimbursement", "(0.19)%"],
            ["Net Annual Fund Operating Expenses", "1.07%"],
        ]
        data = _extract_operating_expenses(rows)[0]

        assert data["fee_waiver"] == Decimal("-0.19")
        assert data["net_expenses"] == Decimal("1.07")

    def test_unparenthesized_waiver_is_normalized_to_a_reduction(self):
        """VALIC-style filings write the waiver bare; the sign must still reconcile."""
        rows = [
            ["Annual Fund Operating Expenses", ""],
            ["Total Annual Fund Operating Expenses", "0.61%"],
            ["Fee Waiver", "0.03%"],
            ["Total Annual Fund Operating Expenses After Fee Waiver", "0.58%"],
        ]
        data = _extract_operating_expenses(rows)[0]

        assert data["fee_waiver"] == Decimal("-0.03")
        assert data["total_annual_expenses"] + data["fee_waiver"] == data["net_expenses"]

    def test_footnote_prose_in_the_waiver_label_is_still_a_waiver(self):
        """Some filers spill the footnote into the waiver's own label cell.

        That prose routinely contains both "total ... expenses" and "after",
        so the net-expense match is anchored on the start of the label; an
        unanchored match reads the waiver row as a second net row and drops
        the waiver value entirely.
        """
        rows = [
            ["Annual Fund Operating Expenses", ""],
            ["Total Annual Fund Operating Expenses", "1.26%"],
            [
                "Fee Waiver and Reimbursement (3) The Adviser agreed to waive so that "
                "the total annual operating expenses do not exceed 0.78% after taking "
                "into account the recoupment",
                "(0.19)%",
            ],
            [
                "Total Annual Fund Operating Expenses after Fee Waiver and Reimbursement",
                "1.07%",
            ],
        ]
        data = _extract_operating_expenses(rows)[0]

        assert data["fee_waiver"] == Decimal("-0.19")
        assert data["net_expenses"] == Decimal("1.07")

    def test_a_fee_table_with_no_waiver_leaves_both_fields_unset(self):
        """Silence check: absent rows stay absent rather than borrowing a value."""
        rows = [
            ["Annual Fund Operating Expenses", ""],
            ["Management Fees", "0.13%"],
            ["Total Annual Fund Operating Expenses", "0.14%"],
        ]
        data = _extract_operating_expenses(rows)[0]

        assert data["total_annual_expenses"] == Decimal("0.14")
        assert data.get("fee_waiver") is None
        assert data.get("net_expenses") is None
