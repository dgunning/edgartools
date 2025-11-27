"""
Regression tests for Issue #506: Income Statement returns ComprehensiveIncome fragment

Issue: https://github.com/dgunning/edgartools/issues/506

Problem: For EFX (Equifax) filings from 2015-2018, the income_statement() method
was returning ConsolidatedStatementsOfComprehensiveIncomeLoss instead of the
actual ConsolidatedStatementsOfIncome.

Root cause: Both statements share the same primary concept (us-gaap_IncomeStatementAbstract),
and the statement resolver was returning the first match without quality scoring.
The role pattern for IncomeStatement (r".*[Ss]tatement[Oo]f[Ii]ncome.*") matched
"ConsolidatedStatementsOfComprehensiveIncomeLoss" because it contains "StatementsOf...Income".

Fix: Extended _score_statement_quality() to deprioritize ComprehensiveIncome when
searching for IncomeStatement, and applied quality sorting to all matching methods
(_match_by_standard_name, _match_by_primary_concept, _match_by_concept_pattern).
"""
import pytest

from edgar import Company


@pytest.mark.network
def test_efx_2019_selects_correct_income_statement():
    """
    EFX 2019 10-K should return ConsolidatedStatementsOfIncome,
    not ConsolidatedStatementsOfComprehensiveIncomeLoss.
    """
    company = Company("EFX")
    filings = company.get_filings(form="10-K")

    # Get the 2019 filing (filed in Feb 2019 for fiscal year 2018)
    filing_2019 = None
    for filing in filings:
        if filing.filing_date.year == 2019:
            filing_2019 = filing
            break

    assert filing_2019 is not None, "Could not find EFX 2019 10-K filing"

    xbrl = filing_2019.xbrl()
    assert xbrl is not None, "XBRL data should be available"

    income = xbrl.statements.income_statement()
    assert income is not None, "Income statement should be found"

    # Verify we got the correct statement (not ComprehensiveIncome)
    role = income.role_or_type.lower()
    assert 'comprehensiveincome' not in role.replace(' ', '').replace('-', '').replace('_', ''), \
        f"Should not select ComprehensiveIncome statement, got: {income.role_or_type}"

    # Verify it's actually the income statement
    assert 'statementsofincome' in role.replace(' ', '').replace('-', '').replace('_', ''), \
        f"Should select StatementsOfIncome, got: {income.role_or_type}"

    # Verify the statement has revenue (a key income statement concept)
    df = income.to_dataframe()
    concepts = df['concept'].tolist() if 'concept' in df.columns else []
    has_revenue = any('revenue' in c.lower() for c in concepts)
    assert has_revenue, "Income statement should contain revenue concepts"


@pytest.mark.network
def test_income_statement_not_comprehensive_income():
    """
    Test that income_statement() returns the actual income statement,
    not the comprehensive income statement, across multiple filings.

    This is a broader test that validates the fix works generally.
    """
    company = Company("EFX")
    filings = company.get_filings(form="10-K")

    # Test filings from 2015-2018
    target_years = [2015, 2016, 2017, 2018]
    tested = 0

    for filing in filings:
        if filing.filing_date.year in target_years:
            xbrl = filing.xbrl()
            if xbrl and xbrl.statements:
                income = xbrl.statements.income_statement()
                if income:
                    df = income.to_dataframe()
                    concepts = df['concept'].tolist() if 'concept' in df.columns else []

                    # Should have revenue (income statement concept)
                    has_revenue = any('revenue' in c.lower() for c in concepts)

                    # Should NOT be dominated by comprehensive income concepts
                    comprehensive_count = sum(1 for c in concepts if 'comprehensive' in c.lower())
                    total_count = len(concepts)
                    comprehensive_ratio = comprehensive_count / total_count if total_count > 0 else 0

                    assert has_revenue, \
                        f"EFX {filing.filing_date.year} income statement should have revenue concepts"
                    assert comprehensive_ratio < 0.5, \
                        f"EFX {filing.filing_date.year} income statement should not be mostly comprehensive income concepts (ratio: {comprehensive_ratio:.2f})"

                    tested += 1

    assert tested >= 3, f"Should have tested at least 3 filings, only tested {tested}"
