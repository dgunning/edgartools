"""
Regression test for GitHub Issue #581: MCHP 2016 Income Statement corrupted

Problem: The income statement resolver was selecting a tax disclosure
(IncomeTaxBenefitProvisionFromContinuingOperationsDetails) instead of
the actual income statement (ConsolidatedStatementsOfIncome) because:
1. The role pattern `.*[Oo]perations.*` was too broad and matched tax disclosures
2. The pattern `.*[Ss]tatement[Oo]f[Ii]ncome.*` didn't match plural "Statements"

Fix:
1. Changed role pattern to `.*[Ss]tatements?[Oo]f[Ii]ncome.*` to match plural
2. Changed operations pattern to `.*[Ss]tatements?[Oo]f[Oo]perations.*` to be more specific
3. Added tax disclosure penalty in `_score_statement_quality`

See: https://github.com/dgunning/edgartools/issues/581
"""
import pytest


class TestIssue581MCHPIncomeStatement:
    """Test that MCHP 2016 income statement is correctly resolved."""

    @pytest.fixture
    def mchp_2016_xbrl(self):
        """Get MCHP 2016 10-K XBRL for testing."""
        from edgar import Company
        company = Company("MCHP")
        filings = company.get_filings(form="10-K")
        filing_2016 = filings.filter(date="2016-01-01:2016-12-31").latest()
        return filing_2016.xbrl()

    @pytest.mark.network
    def test_income_statement_selects_correct_role(self, mchp_2016_xbrl):
        """Test that income statement resolves to ConsolidatedStatementsOfIncome, not tax disclosure."""
        # Get the resolved statement
        result = mchp_2016_xbrl.find_statement("IncomeStatement")
        matching_stmts, found_role, canonical_type = result

        # Should select ConsolidatedStatementsOfIncome, NOT IncomeTaxBenefitProvisionFromContinuingOperationsDetails
        assert found_role is not None, "Should find an income statement"
        assert "ConsolidatedStatementsOfIncome" in found_role, \
            f"Expected ConsolidatedStatementsOfIncome, got {found_role}"
        assert "IncomeTax" not in found_role, \
            f"Should NOT select tax disclosure, got {found_role}"

    @pytest.mark.network
    def test_income_statement_has_revenue(self, mchp_2016_xbrl):
        """Test that income statement has revenue and proper financial data."""
        income_statement = mchp_2016_xbrl.statements.income_statement()

        assert income_statement is not None, "Should have income statement"

        # Convert to dataframe and check for key concepts
        df = income_statement.to_dataframe()

        # Check for revenue-related concepts
        concepts = df['concept'].tolist()
        labels = df['label'].tolist()

        # Should have revenue concepts (not just tax items)
        has_revenue = any('Revenue' in str(c) or 'Revenue' in str(l)
                         for c, l in zip(concepts, labels))
        has_gross_profit = any('GrossProfit' in str(c) or 'Gross Profit' in str(l)
                              for c, l in zip(concepts, labels))
        has_operating_income = any('OperatingIncome' in str(c) or 'Operating Income' in str(l)
                                   for c, l in zip(concepts, labels))

        assert has_revenue, "Income statement should have revenue"
        assert has_gross_profit, "Income statement should have gross profit"
        assert has_operating_income, "Income statement should have operating income"

    @pytest.mark.network
    def test_income_statement_not_all_tax_items(self, mchp_2016_xbrl):
        """Test that income statement is not entirely tax-related items."""
        income_statement = mchp_2016_xbrl.statements.income_statement()
        df = income_statement.to_dataframe()

        # Count tax-related vs non-tax concepts
        concepts = df['concept'].tolist()
        tax_count = sum(1 for c in concepts if 'Tax' in str(c) or 'tax' in str(c).lower())
        total_count = len(concepts)

        # Tax items should be a small minority (not the majority)
        tax_ratio = tax_count / total_count if total_count > 0 else 0
        assert tax_ratio < 0.5, \
            f"Income statement should not be majority tax items ({tax_count}/{total_count} = {tax_ratio:.1%})"
