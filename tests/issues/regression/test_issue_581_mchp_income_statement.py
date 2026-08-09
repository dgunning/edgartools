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
        """Get MCHP 2016 10-K XBRL for testing.

        MCHP has a March fiscal year end, so the FY2016 10-K was filed in May 2016.
        """
        from edgar import Company
        company = Company("MCHP")
        filings = company.get_filings(form="10-K")
        filing_2016 = filings.filter(date="2016-01-01:2016-12-31").latest()

        # MCHP's FY2016 10-K is a filed historical document (0000827054-16-000344,
        # 2016-05-24) and does not stop existing. An empty filter result or an
        # unparseable XBRL is a defect in the filter or the parser, which is
        # what this test is for -- skipping on it hid both.
        assert filing_2016 is not None, (
            "MCHP 10-K filed 2016-05-24 should be reachable by date filter"
        )

        xbrl = filing_2016.xbrl()
        assert xbrl is not None, (
            f"MCHP 2016 10-K ({filing_2016.accession_no}) should parse to XBRL"
        )

        return xbrl

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
        """The income statement carries MCHP's FY2016 figures, not a tax table.

        Concept-name presence was the whole test: "some row mentions Revenue,
        some row mentions GrossProfit". The tax disclosure this bug selected
        contains an income-tax reconciliation, and a wrong-but-plausible
        statement — a later fiscal year, the wrong column, a sign flip — passes
        every one of those checks. The figures below are read off the filing
        itself (0000827054-16-000344, FY ended 2016-03-31), which is a historic
        document and does not move.

            Net sales        $2,173,334k     Gross profit  $1,205,464k
            Operating income $  352,345k     Net income    $  324,132k
                                             (attributable to Microchip)
        """
        income_statement = mchp_2016_xbrl.statements.income_statement()
        assert income_statement is not None, "Should have income statement"

        df = income_statement.to_dataframe()
        fy2016 = '2016-03-31 (FY)'
        assert fy2016 in df.columns, (
            f"FY2016 column missing; got {[c for c in df.columns if '20' in c]}. "
            "A statement without the filing's own fiscal year is the wrong "
            "statement."
        )

        def face_value(concept, label):
            """The undimensioned row for a concept — segment rows repeat the
            concept with a different label and would otherwise match first."""
            rows = df[(df['concept'] == concept) & (df['label'] == label)]
            assert len(rows) == 1, (
                f"expected one {concept} row labelled {label!r}, found {len(rows)}"
            )
            return rows.iloc[0][fy2016]

        assert face_value('us-gaap_SalesRevenueNet', 'Net sales') == 2_173_334_000
        assert face_value('us-gaap_GrossProfit', 'Gross profit') == 1_205_464_000
        assert face_value('us-gaap_OperatingIncomeLoss', 'Operating income') == 352_345_000
        assert face_value('us-gaap_NetIncomeLoss',
                          'Net income attributable to Microchip Technology') == 324_132_000

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
