"""Base class for company report filings."""
import warnings
from functools import cached_property
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from edgar.sgml.filing_summary import Reports

from rich import print
from rich.console import Group, Text
from rich.panel import Panel

from edgar.documents import Document, HTMLParser
from edgar.files.htmltools import ChunkedDocument  # Keep for backwards compat
from edgar.financials import Financials
from edgar.richtools import repr_rich

__all__ = ['CompanyReport']


class CompanyReport:

    def __init__(self, filing):
        self._filing = filing
        self._parser = None  # Lazy init for new parser

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
    def auditor(self):
        """Auditor information from XBRL DEI facts, if available."""
        from edgar.company_reports.auditor import extract_auditor_info
        if self.financials and self.financials.xb:
            return extract_auditor_info(self.financials.xb)
        return None

    @cached_property
    def reports(self) -> Optional['Reports']:
        """The XBRL report pages from FilingSummary.xml (statements, notes, tables, details)."""
        return self._filing.reports

    @cached_property
    def financials(self):
        """Get the financials for this filing"""
        return Financials.extract(self._filing)

    @property
    def period_of_report(self):
        return self._filing.header.period_of_report

    @cached_property
    def document(self) -> Document:
        """
        Get the filing document using new parser (primary API).

        Returns:
            Document: Parsed document with sections, tables, and content extraction

        Examples:
            >>> report.document.sections  # Get all sections
            >>> report.document.text()    # Get full text
            >>> report.document.tables    # Get all tables
        """
        if self._parser is None:
            from edgar.documents.config import ParserConfig
            # Create parser with form type for better section detection
            config = ParserConfig(form=self._filing.form)
            self._parser = HTMLParser(config)
        return self._parser.parse(self._filing.html())

    @cached_property
    def chunked_document(self):
        """
        Get chunked document using old parser.

        .. deprecated:: 5.0
            Use :attr:`document` instead. This will be removed in v6.0.
        """
        warnings.warn(
            "chunked_document is deprecated and will be removed in v6.0. "
            "Use document property instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return ChunkedDocument(self._filing.html())

    @property
    def doc(self):
        """Get the filing document (returns new Document object)."""
        return self.document

    @property
    def items(self) -> List[str]:
        """
        Get list of items/sections in the filing.

        Returns:
            List[str]: List of section identifiers in "Item X" format

        Examples:
            >>> report.items
            ['Item 1', 'Item 1A', 'Item 1B', 'Item 2', ...]
        """
        # Convert section keys to "Item X" format for backwards compatibility
        items = []
        for name, section in self.document.sections.items():
            if section.item:
                # Format as "Item 1", "Item 1A", etc.
                items.append(f"Item {section.item}")
            elif name.startswith("Item "):
                # Section name is already in "Item X" format
                items.append(name)
            elif name.startswith("item_"):
                # Convert "item_1" to "Item 1"
                item_num = name.replace("item_", "").replace("_", "").upper()
                items.append(f"Item {item_num}")
            elif name.startswith("part_"):
                # Convert "part_i_item_1" to "Item 1"
                # Extract item number from name like "part_i_item_1a"
                parts = name.split("_")
                if len(parts) >= 4 and parts[2] == "item":
                    item_num = parts[3].upper()
                    items.append(f"Item {item_num}")
        return items

    def __getitem__(self, item_or_part: str):
        """
        Get item or part text from the filing.

        Args:
            item_or_part: Item identifier (e.g., "Item 1", "1", "1A", "Part I")

        Returns:
            str: Item text or None if not found

        Examples:
            >>> report["Item 1"]
            >>> report["1A"]
            >>> report["Part I"]  # For 10-Q
        """
        # Try to get section using new parser
        section = self.document.sections.get(item_or_part)
        if section:
            return section.text()

        # Try flexible item lookup (handles "Item 1", "1", etc.)
        section = self.document.sections.get_item(item_or_part)
        if section:
            return section.text()

        return None

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
