"""
Regression test for Issue #673: SNY (Sanofi, IFRS 20-F filer)
income_statement() and comprehensive_income() must resolve to different statements.

Root cause: IFRS concepts were not classified in Phase 1, and
ifrs-full_StatementOfComprehensiveIncomeAbstract was ambiguously listed as an
alternative_concept for both IncomeStatement and ComprehensiveIncome.
"""
import pytest
from edgar import Company


@pytest.mark.network
def test_sny_income_vs_comprehensive_income():
    """SNY income_statement() must not return the same statement as comprehensive_income()."""
    company = Company("SNY")
    filing = company.get_filings(form="20-F").latest()
    xbrl = filing.xbrl()

    income = xbrl.statements.income_statement()
    comprehensive = xbrl.statements.comprehensive_income()

    # Both should resolve
    assert income is not None, "income_statement() should resolve for SNY"
    assert comprehensive is not None, "comprehensive_income() should resolve for SNY"

    # They must be different statements (different roles)
    assert income.role != comprehensive.role, (
        f"income_statement() and comprehensive_income() resolved to the same role: {income.role}"
    )

    # Income statement should contain P&L indicators, not OCI
    income_def = income.definition.lower() if hasattr(income, 'definition') else ""
    assert "comprehensive" not in income_def or "profit" in income_def, (
        f"income_statement() definition looks like OCI: {income.definition}"
    )
