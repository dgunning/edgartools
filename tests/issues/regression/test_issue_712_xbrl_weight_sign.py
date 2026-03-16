"""
Regression tests for GitHub Issue #712: Incorrect weight and sign across XBRL concepts

Root cause: _get_primary_weight() in facts.py used keyword matching ("income" in role_lower)
to identify income statement calculation trees. Many companies (AAPL, TSLA) name their income
statement "Consolidated Statements of Operations" which does NOT contain "income". This caused
the function to skip the correct calculation tree (weight=-1.0) and pick up the weight from
an unrelated detail tree like IncomeTaxesProvision (weight=1.0).

Fix: Use exact role URI matching (from presentation tree scan) before falling back to keywords,
and add "operation" as a keyword for income statement matching.

Affected concepts confirmed:
- us-gaap:IncomeTaxExpenseBenefit (Income Statement) — weight was 1.0, should be -1.0
- us-gaap:IncreaseDecreaseInInventories (Cash Flow) — already correct, regression guard
- us-gaap:IncreaseDecreaseInOtherOperatingAssets (Cash Flow) — already correct, regression guard
"""

import pytest
from edgar import Company


class TestIssue712WeightSign:
    """
    Ground-truth tests for XBRL calculation weights.
    Verifies weights match the filing's calculation linkbase, not a heuristic.
    """

    def test_aapl_income_tax_weight_is_negative(self):
        """
        AAPL 10-K: IncomeTaxExpenseBenefit must have weight=-1.0 in the income statement.

        The AAPL calculation linkbase at role CONSOLIDATEDSTATEMENTSOFOPERATIONS defines
        IncomeTaxExpenseBenefit as a child of NetIncomeLoss with weight=-1.0 (subtracted).

        Before the fix, _get_primary_weight() returned 1.0 because the role URI contains
        "operations" not "income", so it fell through to an IncomeTaxesProvision detail
        tree where the weight is 1.0.
        """
        company = Company("AAPL")
        filing = company.get_filings(form="10-K").latest()
        xbrl = filing.xbrl()

        income = xbrl.statements.income_statement()
        df = income.to_dataframe()
        tax_rows = df[df["concept"] == "us-gaap_IncomeTaxExpenseBenefit"]

        assert len(tax_rows) == 1, "Expected exactly one IncomeTaxExpenseBenefit row"
        assert tax_rows.iloc[0]["weight"] == -1.0, (
            f"IncomeTaxExpenseBenefit weight should be -1.0 (subtracted from pre-tax income), "
            f"got {tax_rows.iloc[0]['weight']}"
        )

    def test_tsla_income_tax_weight_is_negative(self):
        """
        TSLA 10-K: IncomeTaxExpenseBenefit must have weight=-1.0.
        Same bug pattern as AAPL — TSLA also uses "Statements of Operations" naming.
        """
        company = Company("TSLA")
        filing = company.get_filings(form="10-K").latest()
        xbrl = filing.xbrl()

        income = xbrl.statements.income_statement()
        df = income.to_dataframe()
        tax_rows = df[df["concept"] == "us-gaap_IncomeTaxExpenseBenefit"]

        assert len(tax_rows) == 1
        assert tax_rows.iloc[0]["weight"] == -1.0, (
            f"TSLA IncomeTaxExpenseBenefit weight should be -1.0, got {tax_rows.iloc[0]['weight']}"
        )

    def test_aapl_income_tax_weight_in_facts(self):
        """
        The Facts API must also return the correct weight for IncomeTaxExpenseBenefit.

        Statement._add_metadata_columns() reads weight from facts, so if facts are wrong,
        the statement is wrong — this was the actual bug path in GH-712.
        """
        company = Company("AAPL")
        filing = company.get_filings(form="10-K").latest()
        xbrl = filing.xbrl()

        facts_df = xbrl.facts.query().by_concept(
            "us-gaap:IncomeTaxExpenseBenefit", exact=True
        ).to_dataframe()

        assert not facts_df.empty, "Should find IncomeTaxExpenseBenefit facts"
        weights = facts_df["weight"].dropna().unique()
        assert len(weights) == 1, f"Expected one unique weight, got {weights}"
        assert weights[0] == -1.0, (
            f"Facts weight for IncomeTaxExpenseBenefit should be -1.0, got {weights[0]}"
        )

    def test_aapl_cashflow_weights_correct(self):
        """
        Regression guard: cash flow concept weights must remain -1.0.
        These were already correct before the fix but guard against future regressions.
        """
        company = Company("AAPL")
        filing = company.get_filings(form="10-K").latest()
        xbrl = filing.xbrl()

        cashflow = xbrl.statements.cash_flow_statement()
        df = cashflow.to_dataframe()

        expected_negative = [
            "us-gaap_IncreaseDecreaseInInventories",
            "us-gaap_IncreaseDecreaseInOtherOperatingAssets",
            "us-gaap_OtherNoncashIncomeExpense",
        ]

        for concept in expected_negative:
            rows = df[df["concept"] == concept]
            if not rows.empty:
                weight = rows.iloc[0]["weight"]
                assert weight == -1.0, (
                    f"{concept} weight should be -1.0, got {weight}"
                )
