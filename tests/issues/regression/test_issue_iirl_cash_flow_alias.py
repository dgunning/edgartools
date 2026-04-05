"""
Regression test for edgartools-iirl: cash_flow_statement() alias

The canonical method is cashflow_statement() (no underscore), but Python convention
and user intuition expects cash_flow_statement() (with underscore). This test verifies
that cash_flow_statement() exists as an alias on all surfaces and delegates correctly.
"""


def test_financials_has_cash_flow_statement_alias():
    """Financials class should have cash_flow_statement() as alias for cashflow_statement()."""
    from edgar.financials import Financials
    assert hasattr(Financials, 'cash_flow_statement')
    assert hasattr(Financials, 'cashflow_statement')


def test_multi_financials_has_cash_flow_statement_alias():
    """MultiFinancials class should have cash_flow_statement() as alias for cashflow_statement()."""
    from edgar.financials import MultiFinancials
    assert hasattr(MultiFinancials, 'cash_flow_statement')
    assert hasattr(MultiFinancials, 'cashflow_statement')


def test_statements_has_cash_flow_statement_alias():
    """xbrl Statements class should have cash_flow_statement() as alias for cashflow_statement()."""
    from edgar.xbrl.statements import Statements
    assert hasattr(Statements, 'cash_flow_statement')
    assert hasattr(Statements, 'cashflow_statement')


def test_stitched_statements_has_cash_flow_statement_alias():
    """StitchedStatements class should have cash_flow_statement() as alias for cashflow_statement()."""
    from edgar.xbrl.statements import StitchedStatements
    assert hasattr(StitchedStatements, 'cash_flow_statement')
    assert hasattr(StitchedStatements, 'cashflow_statement')


def test_company_has_cash_flow_statement_alias():
    """Company class should have cash_flow_statement() as alias for cashflow_statement()."""
    from edgar.entity.core import Company
    assert hasattr(Company, 'cash_flow_statement')
    assert hasattr(Company, 'cashflow_statement')
