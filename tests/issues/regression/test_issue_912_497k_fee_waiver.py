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
from edgar.funds._497k_tables import _extract_operating_expenses, _parse_percentage
from edgar.funds.prospectus497k import Prospectus497K
from tests._offline_filings import offline_filing

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


class TestFootnoteMarkersInValueCells:
    """edgartools-cnl3: markers living in the value cell must not corrupt the number.

    Filers commonly render the footnote reference inside the value cell rather
    than beside the label. Collapsing whitespace before extracting the number
    glued the marker onto it, so John Hancock's "0.67 1" became 0.671 — wrong
    across management fees and totals, not just the waiver.
    """

    @pytest.mark.parametrize(
        "cell, expected",
        [
            # Whitespace-separated footnote digits (John Hancock).
            ("0.67 1", Decimal("0.67")),
            ("-0.01 3", Decimal("-0.01")),
            ("1.10 2", Decimal("1.10")),
            ("0.46 3 4", Decimal("0.46")),
            # Percent sign inside the bracket (GMO, Goldman Sachs, Columbia)
            # — stripping "%" and the rest first ate the closing bracket and
            # dropped the value entirely.
            ("(0.37%)", Decimal("-0.37")),
            ("(0.19 %)", Decimal("-0.19")),
            ("(0.06%)", Decimal("-0.06")),
            # Percent sign outside the bracket still works.
            ("(0.19)%", Decimal("-0.19")),
            ("(0.05) 3", Decimal("-0.05")),
            # Symbol and bracketed markers appended to the number.
            ("0.67*", Decimal("0.67")),
            ("0.67(1)", Decimal("0.67")),
            ("0.05%(3)", Decimal("0.05")),
            # Shapes that already worked and must keep working.
            ("0.14%", Decimal("0.14")),
            ("- 22.03 %", Decimal("-22.03")),
            ("-6.78", Decimal("-6.78")),
            ("0.00", Decimal("0.00")),
        ],
    )
    def test_leading_numeric_token_is_the_value(self, cell, expected):
        assert _parse_percentage(cell) == expected

    @pytest.mark.parametrize(
        "cell",
        ["None", "—", "–", "-", "", "n/a", "N/A 1", "up to 0.25", "December 31, 2023", "$25/yr"],
    )
    def test_non_numeric_cells_stay_none(self, cell):
        """Silence check: a cell with no leading number must not invent one."""
        assert _parse_percentage(cell) is None

    @pytest.mark.parametrize(
        "cell",
        [
            # Dates — taking the leading token would yield the month.
            "2/1/2010", "9-13-2017", "06/27/2023", "3/31/2025",
            # Labels and headers that merely begin with digits.
            "12b-1 Distribution Fee", "4Q 2023", "1Q 2022",
            "1 Year", "5 Years", "10 Years", "5 Years*", "5\n    years",
            # A stray closing bracket is not a footnote marker.
            "2020)",
            # Footnote prose that happens to open with a bracketed number.
            "(11.4% - 14.4% after taking into account the recoupment)",
        ],
    )
    def test_cells_that_merely_start_with_digits_stay_none(self, cell):
        """The number must end at a footnote marker, not at arbitrary text.

        Only accepting a leading numeric token made dates and headers parse:
        "2/1/2010" became 2 and "12b-1 Distribution Fee" became 12.
        """
        assert _parse_percentage(cell) is None

    @pytest.mark.network
    @pytest.mark.vcr
    def test_date_cells_no_longer_clobber_the_best_worst_quarter(self):
        """GMO Trust's quarter table, hand-read from the filing:

            Highest Quarter:   6.02%   4Q 2023
            Lowest Quarter:   -6.88%   1Q 2022

        The extractor keeps the last cell that parses, so when "4Q 2023"
        parsed as 4 it overwrote the real return. Best/worst came back as
        4 and 1.
        """
        prospectus = offline_filing("0001193125-25-152548").obj()

        assert prospectus.best_quarter[0] == Decimal("6.02")
        assert prospectus.worst_quarter[0] == Decimal("-6.88")

    @pytest.mark.network
    @pytest.mark.vcr
    def test_john_hancock_fees_are_not_glued_to_footnotes(self):
        """Ground truth hand-read from the filing's fee table.

        Class A: management fee 0.67, total 1.12, reimbursement (0.01), net 1.11.
        Before the fix these parsed as 0.671, 1.12, -0.013 and None.
        """
        prospectus = offline_filing("0001193125-25-148895").obj()
        class_a = prospectus.share_classes[0]

        assert class_a.class_name == "A"
        assert class_a.management_fee == Decimal("0.67")
        assert class_a.total_annual_expenses == Decimal("1.12")
        assert class_a.fee_waiver == Decimal("-0.01")
        assert class_a.net_expenses == Decimal("1.11")
        assert (
            class_a.total_annual_expenses + class_a.fee_waiver == class_a.net_expenses
        )
