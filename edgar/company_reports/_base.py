"""Base class for company report filings."""
from functools import cached_property
from typing import List

from rich import print
from rich.console import Group, Text
from rich.panel import Panel

from edgar.files.htmltools import ChunkedDocument
from edgar.financials import Financials
from edgar.richtools import repr_rich

__all__ = ['CompanyReport']


class CompanyReport:

    def __init__(self, filing):
        self._filing = filing

    @property
    def filing_date(self):
        return self._filing.filing_date

    @property
    def form(self):
        return self._filing.form

    @property
    def company(self):
        return self._filing.company

    @property
    def income_statement(self):
        return self.financials.income_statement() if self.financials else None

    @property
    def balance_sheet(self):
        return self.financials.balance_sheet() if self.financials else None

    @property
    def cash_flow_statement(self):
        return self.financials.cashflow_statement() if self.financials else None

    @cached_property
    def financials(self):
        """Get the financials for this filing"""
        return Financials.extract(self._filing)

    @property
    def period_of_report(self):
        return self._filing.header.period_of_report

    @cached_property
    def chunked_document(self):
        return ChunkedDocument(self._filing.html())

    @property
    def doc(self):
        return self.chunked_document

    @property
    def items(self) -> List[str]:
        return self.chunked_document.list_items()

    def __getitem__(self, item_or_part: str):
        # Show the item or part from the filing document. e.g. Item 1 Business from 10-K or Part I from 10-Q
        item_text = self.chunked_document[item_or_part]
        return item_text

    def view(self, item_or_part: str):
        """Get the Item or Part from the filing document. e.g. Item 1 Business from 10-K or Part I from 10-Q"""
        item_text = self[item_or_part]
        if item_text:
            print(item_text)

    def __rich__(self):
        return Panel(
            Group(
                self._filing.__rich__(),
                self.financials or Text("No financial data available")
            )
        )

    def __repr__(self):
        return repr_rich(self.__rich__())
