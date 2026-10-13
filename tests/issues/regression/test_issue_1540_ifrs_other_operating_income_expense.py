"""
``ifrs-full:OtherOperatingIncomeExpense``, the operating income or expense an
IFRS filer does not disclose separately, had no standard concept. IFRS entries in
``gaap_mappings.json`` are keyed with their prefix, and an IFRS tag never falls
back to a bare key (gnx5), so the only entry of that name -- a bare
``OtherOperatingIncomeExpense`` mapped to ``OperatingIncomeLoss``, the operating
income total -- never answered for it, and the lookup returned ``None``.

It now maps to ``OtherOperatingIncomeExpenseNet``, the operating "other income
(expense), net" concept added for the us-gaap counterpart (#1417), and the bare
entry points at the same concept instead of the total.

Ground truth: SAP's FY2025 20-F (0001104659-26-020058) reports "Other operating
income/expense, net" of -EUR 49 million between Restructuring and Total
operating expenses, inside operating profit of EUR 9,617 million.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1540
"""

import pytest

from edgar.xbrl.standardization.reverse_index import get_reverse_index

SAP_FY2025_20F = "0001104659-26-020058"


@pytest.mark.fast
@pytest.mark.parametrize("tag", ["ifrs-full_OtherOperatingIncomeExpense", "ifrs-full:OtherOperatingIncomeExpense"])
def test_the_ifrs_element_maps_to_the_operating_concept(tag):
    result = get_reverse_index().lookup(tag)

    assert result is not None
    assert result.standard_concepts == ["OtherOperatingIncomeExpenseNet"]
    assert result.display_names == ["Other Operating Income (Expense), Net"]


@pytest.mark.fast
def test_the_bare_entry_no_longer_names_the_operating_income_total():
    result = get_reverse_index().lookup("OtherOperatingIncomeExpense")

    assert result is not None
    assert result.standard_concepts == ["OtherOperatingIncomeExpenseNet"]


@pytest.mark.network
def test_sap_fy2025_row_is_standardized_inside_operating_profit():
    from edgar import find

    df = find(SAP_FY2025_20F).xbrl().statements.income_statement().to_dataframe()
    df = df[df["dimension"] != True]  # noqa: E712 - the column holds bools and NaN

    rows = df[df["concept"] == "ifrs-full_OtherOperatingIncomeExpense"]
    assert len(rows) == 1
    row = rows.iloc[0]
    assert row["standard_concept"] == "OtherOperatingIncomeExpenseNet"
    assert row["2025-12-31 (FY)"] == -49_000_000
    assert row["label"] == "Other operating income/expense, net"

    concepts = list(df["concept"])
    assert concepts.index("ifrs-full_OtherOperatingIncomeExpense") < concepts.index("ifrs-full_ProfitLossFromOperatingActivities")
