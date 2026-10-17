"""
Regression test for edgartools-iirl: cash_flow_statement() on every surface.

cash_flow_statement() is the canonical name. The deprecated cashflow_statement()
spelling was removed in 6.0 (bead edgartools-07lk.22.1), so it must not exist.
"""
import pytest

from edgar.entity.core import Company
from edgar.financials import Financials, MultiFinancials
from edgar.xbrl.statements import Statements, StitchedStatements


@pytest.mark.parametrize("cls", [Financials, MultiFinancials, Statements, StitchedStatements, Company])
def test_cash_flow_statement_exists_and_old_spelling_is_gone(cls):
    assert hasattr(cls, 'cash_flow_statement')
    assert not hasattr(cls, 'cashflow_statement')
