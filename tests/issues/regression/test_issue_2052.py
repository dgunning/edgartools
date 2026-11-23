"""
Regression test: 497K fee-table values that were plainly filed but silently
dropped or put in the wrong field.

GitHub Issue: https://github.com/dgunning/edgartools/issues/2052

Four label shapes in `_extract_operating_expenses` and one in
`_extract_quarter_data`, each hand-checked against the filing named below:

1. Waycross Independent Trust, 0001580642-25-003937: the waiver row "Less
   Management Fee Reductions and/or Expense Reimbursements" contains
   "management fee", so its (0.43%) overwrote the real 0.66% management fee.
2. American Pension Investors Trust, 0001580642-25-003520: the GROSS total is
   the qualified row ("... (before fee waivers ...)") and the NET row is plain
   "Total Annual Fund Operating Expenses", so the net overwrote the gross.
3. Weitz Funds, 0001821268-24-000157 (and Voya, 0001683863-25-005452): the net
   row's label wraps onto a second row ("expense reimbursement") whose value
   cells are blank, and that continuation row overwrote the waiver with None.
4. Investment Managers Series Trust II, 0001213900-25-038390: "Fees waived
   and/or expenses reimbursed" matched neither "fee waiver" nor "reimbursement".
5. GMO Trust, 0001193125-25-152548: best/worst quarter labels written "4Q 2023"
   (or "12/31/2023") were never captured, leaving an empty date string.
"""
from decimal import Decimal

import pytest

from edgar import find
from edgar.funds._497k_tables import _extract_operating_expenses, _extract_quarter_data

# Rows as `_table_texts` reads them from each filing's fee table.
WAYCROSS_ROWS = [
    ["Management\n    Fees", "0.66%"],
    ["Distribution\n    and/or Service (12b-1) Fees", "None"],
    ["Other\n    Expenses", "0.46%"],
    ["Total\n    Annual Fund Operating Expenses", "1.12%"],
    ["Less\n    Management Fee Reductions and/or Expense Reimbursements (1)", "(0.43%)"],
    ["Total\n    Annual Fund Operating Expenses After Fee Reductions and/or "
     "Expense Reimbursements (1)", "0.69%"],
]

AMERICAN_PENSION_ROWS = [
    ["", "Class A", "Class L", "Class"],
    ["Management Fee", "0.70%", "0.70%", "0.70%"],
    ["Distribution/Service (12b-1 Fees)", "0.00%", "0.65%", "0.00%"],
    ["Other Expenses (2)", "0.29%", "0.29%", "0.29%"],
    ["Total Annual Fund Operating Expenses (before fee waivers and/or expense "
     "reimbursements)", "0.99%", "1.64%", "0.99%"],
    ["Fee Waivers and/or Expense Reimbursements (3)", "(0.19)%", "(0.19)%", "(0.19)%"],
    ["Total Annual Fund Operating Expenses (3)", "0.80%", "1.45%", "0.80%"],
]

WEITZ_ROWS = [
    ["", "Institutional Class"],
    ["Management fees", "0.30%"],
    ["Distribution (12b-1) fees", "None"],
    ["Other expenses*", "0.20%"],
    ["Acquired Fund Fees", "0.01%"],
    ["Total annual fund operating expenses*", "0.51%"],
    ["Fee waiver and/or expense reimbursement (1) *", "(0.18)%"],
    ["Total annual fund operating expenses after fee waiver and/or", "0.33%"],
    ["expense reimbursement", ""],
]

IMST_II_ROWS = [
    ["", "Investor Class\xa0Shares", "", "Institutional Class\xa0Shares", ""],
    ["Management fees", "0.82%", "", "0.82%", ""],
    ["Distribution (Rule 12b -1 ) fees", "0.25%", "", "None", ""],
    ["Other expenses", "31.84%", "", "31.84%", ""],
    ["Total annual fund operating expenses 1", "32.91%", "", "32.66%", ""],
    ["Fees waived and/or expenses reimbursed 2", "(31.77)%", "", "(31.77)%", ""],
    ["Total annual fund operating expenses after waiving fees a nd/or reimbursing "
     "exp enses 1,2", "1.14%", "", "0.89%", ""],
]

GMO_QUARTER_ROWS = [
    ["Highest Quarter:", "6.02%", "4Q 2023"],
    ["Lowest Quarter:", "-6.88%", "1Q 2022"],
    ["Year-to-Date:", "2.96%", "As of", "3/31/2025"],
]


def _reconciles(data):
    return data["total_annual_expenses"] + data["fee_waiver"] == data["net_expenses"]


class TestFeeLabelRouting:

    def test_waiver_naming_the_management_fee_is_the_waiver(self):
        data = _extract_operating_expenses(WAYCROSS_ROWS)[0]

        # Before the fix: management_fee == -0.43 and fee_waiver is absent.
        assert data["management_fee"] == Decimal("0.66")
        assert data["fee_waiver"] == Decimal("-0.43")
        assert data["net_expenses"] == Decimal("0.69")
        assert _reconciles(data)

    def test_qualified_gross_and_plain_net_totals(self):
        class_a, class_l, institutional = _extract_operating_expenses(AMERICAN_PENSION_ROWS)

        # Before the fix: total == 0.80 (the net) and net_expenses is None.
        assert class_a["total_annual_expenses"] == Decimal("0.99")
        assert class_a["fee_waiver"] == Decimal("-0.19")
        assert class_a["net_expenses"] == Decimal("0.80")
        assert class_l["total_annual_expenses"] == Decimal("1.64")
        assert class_l["net_expenses"] == Decimal("1.45")
        assert all(_reconciles(d) for d in (class_a, class_l, institutional))

    def test_wrapped_label_continuation_keeps_the_waiver(self):
        data = _extract_operating_expenses(WEITZ_ROWS)[0]

        # Before the fix: the blank "expense reimbursement" row set fee_waiver to None.
        assert data["fee_waiver"] == Decimal("-0.18")
        assert data["net_expenses"] == Decimal("0.33")
        assert _reconciles(data)

    def test_waived_and_reimbursed_wording_is_the_waiver(self):
        investor, institutional = _extract_operating_expenses(IMST_II_ROWS)

        assert investor["fee_waiver"] == Decimal("-31.77")
        assert _reconciles(investor)
        assert _reconciles(institutional)

    def test_unqualified_single_total_is_still_the_gross(self):
        """The positional net rule needs a waiver row before the second total."""
        rows = [
            ["Management Fees", "0.50%"],
            ["Total Annual Fund Operating Expenses", "0.75%"],
        ]
        data = _extract_operating_expenses(rows)[0]

        assert data["total_annual_expenses"] == Decimal("0.75")
        assert "net_expenses" not in data


class TestQuarterDateLabels:

    def test_quarter_number_labels_are_captured(self):
        best, worst = _extract_quarter_data(GMO_QUARTER_ROWS)

        # Before the fix: (6.02, '') and (-6.88, '').
        assert best == (Decimal("6.02"), "4Q 2023")
        assert worst == (Decimal("-6.88"), "1Q 2022")

    @pytest.mark.parametrize(
        "label",
        ["Q2 2020", "Q1/2023", "12/31/2023", "Quarter Ended 06/30/2020", "March 31, 2020"],
    )
    def test_other_period_label_shapes(self, label):
        best, _ = _extract_quarter_data([["Highest", "5.00%", label]])

        assert best == (Decimal("5.00"), label)

    def test_return_and_label_in_one_cell_keeps_the_return(self):
        best, _ = _extract_quarter_data([["Best Quarter", "6.02% (Q4 2023)"]])

        assert best == (Decimal("6.02"), "6.02% (Q4 2023)")

    def test_row_without_a_return_yields_none(self):
        assert _extract_quarter_data([["Highest Quarter", "4Q 2023"]]) == (None, None)


@pytest.mark.network
@pytest.mark.vcr
class TestIssue2052Filings:

    def test_waycross(self):
        share_class = find("0001580642-25-003937").obj().share_classes[0]

        assert share_class.management_fee == Decimal("0.66")
        assert share_class.fee_waiver == Decimal("-0.43")
        assert share_class.net_expenses == Decimal("0.69")

    def test_american_pension_class_a(self):
        class_a = find("0001580642-25-003520").obj().share_classes[0]

        assert class_a.total_annual_expenses == Decimal("0.99")
        assert class_a.net_expenses == Decimal("0.80")

    def test_gmo_quarters(self):
        prospectus = find("0001193125-25-152548").obj()

        assert prospectus.best_quarter == (Decimal("6.02"), "4Q 2023")
        assert prospectus.worst_quarter == (Decimal("-6.88"), "1Q 2022")
