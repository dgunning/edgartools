from typing import Optional

from edgar.richtools import repr_rich
from edgar.xbrl2 import XBRL, XBRLS, Statement

__all__ = ['Financials', 'MultiFinancials']


class Financials:

    def __init__(self, xb: XBRL):
        self.xb: XBRL = xb

    @classmethod
    def extract(cls, filing) -> Optional['Financials']:
        xb = XBRL.from_filing(filing)
        return cls(xb)

    def balance_sheet(self):
        return self.xb.statements.balance_sheet()

    def income(self):
        return self.xb.statements.income_statement()

    def cashflow(self):
        return self.xb.statements.cash_flow_statement()

    def equity(self):
        return self.xb.statements.statement_of_equity()

    def comprehensive_income(self):
        return self.xb.statements.comprehensive_income()

    def cover(self):
        return self.xb.statements.cover_page()

    def __rich__(self):
        return self.xb.__rich__()

    def __repr__(self):
        return repr_rich(self.__rich__())


class MultiFinancials:
    """
    Merges the financial statements from multiple periods into a single financials.
    """

    def __init__(self, xbs:XBRLS):
        self.xbs = xbs

    @classmethod
    def extract(cls, filings) -> 'MultiFinancials':
        return cls(XBRLS.from_filings(filings))

    def balance_sheet(self) -> Optional[Statement]:
        return self.xbs.statements.balance_sheet()

    def income_statement(self) -> Optional[Statement]:
        return self.xbs.statements.income_statement()

    def cashflow_statement(self) -> Optional[Statement]:
        return self.xbs.statements.cash_flow_statement()

    def __rich__(self):
        self.xbs.__rich__()

    def __repr__(self):
        return repr_rich(self.__rich__())
