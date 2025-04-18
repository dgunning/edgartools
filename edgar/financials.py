from typing import Optional

from edgar.richtools import repr_rich
from edgar.xbrl import XBRL, XBRLS, Statement
from edgar.core import log

from edgar.xbrl.xbrl import XBRLFilingWithNoXbrlData


class Financials:

    def __init__(self, xb: Optional[XBRL]):
        self.xb: XBRL = xb

    @classmethod
    def extract(cls, filing) -> Optional['Financials']:
        try:
            xb = XBRL.from_filing(filing)
            return Financials(xb)
        except XBRLFilingWithNoXbrlData as e:
            # Handle the case where the filing does not have XBRL data
            log.warning(f"Filing {filing} does not contain XBRL data: {e}")
            return None

    def balance_sheet(self):
        if self.xb is None:
            return None
        return self.xb.statements.balance_sheet()

    def income_statement(self):
        if self.xb is None:
            return None
        return self.xb.statements.income_statement()

    def cashflow_statement(self):
        if self.xb is None:
            return None
        return self.xb.statements.cashflow_statement()

    def statement_of_equity(self):
        if self.xb is None:
            return None
        return self.xb.statements.statement_of_equity()

    def comprehensive_income(self):
        if self.xb is None:
            return None
        return self.xb.statements.comprehensive_income()

    def cover(self):
        if self.xb is None:
            return None
        return self.xb.statements.cover_page()

    def __rich__(self):
        if self.xb is None:
            return "No XBRL data available"
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
        return self.xbs.statements.cashflow_statement()

    def __rich__(self):
        self.xbs.__rich__()

    def __repr__(self):
        return repr_rich(self.__rich__())
