from collections import defaultdict
from typing import Optional, List, Dict

import pandas as pd
from pydantic import BaseModel
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table, Column
from rich.text import Text

from edgar.richtools import repr_rich
from edgar.xbrl.presentation import FinancialStatementMapper, XBRLPresentation
from edgar.xbrl.xbrldata import XBRLData, Statement


class StandardStatement(BaseModel):
    statement_name: str
    concept: str
    display_name: str


balance_sheet = StandardStatement(statement_name="BALANCE_SHEET",
                                  concept="us-gaap_StatementOfFinancialPositionAbstract",
                                  display_name="Consolidated Balance Sheets")
income_statement = StandardStatement(statement_name="INCOME_STATEMENT",
                                     concept="us-gaap_IncomeStatementAbstract",
                                     display_name="Income Statements")
cash_flow_statement = StandardStatement(statement_name="CASH_FLOW",
                                        concept="us-gaap_StatementOfCashFlowsAbstract",
                                        display_name="Consolidated Statement of Cash Flows")
statement_of_changes_in_equity = StandardStatement(statement_name="EQUITY",
                                                   concept="us-gaap_StatementOfStockholdersEquityAbstract",
                                                   display_name="Consolidated Statement of Shareholders Equity")
statement_of_comprehensive_income = StandardStatement(statement_name="COMPREHENSIVE_INCOME",
                                                      concept="us-gaap_StatementOfIncomeAndComprehensiveIncomeAbstract"
                                                      , display_name="Comprehensive Income Statement")
cover_page = StandardStatement(statement_name="COVER_PAGE",
                               concept="dei_CoverAbstract",
                               display_name="Cover Page")


class Financials:

    @classmethod
    def get_standard_name(cls, role_name: str) -> Optional[str]:
        role_name_normalized = ''.join(char.upper() for char in role_name if char.isalnum())
        for standard_name, variations in FinancialStatementMapper.STANDARD_STATEMENTS.items():
            if any(variation in role_name_normalized for variation in variations):
                return standard_name
        return None

    def __init__(self, xbrl_data: XBRLData):
        self.xbrl_data: XBRLData = xbrl_data
        self.presentation: XBRLPresentation = xbrl_data.presentation

    @classmethod
    def extract(cls, filing) -> Optional['Financials']:
        assert filing.form in ['10-K', '10-Q', '10-K/A', '10-Q/A'], "Filing must be a 10-K or 10-Q"
        xbrl_data = XBRLData.extract(filing)
        if not xbrl_data:
            return None
        return cls(xbrl_data)

    def _get_statement_name_for_standard_name(self, standard_statement: StandardStatement) -> Optional[str]:
        role = self.xbrl_data.presentation.get_role_by_standard_name(standard_statement.statement_name)
        if not role:
            role = self.find_role_by_concept(standard_statement.concept)
        if role:
            statement_name = role.split('/')[-1]
            return statement_name

    def get_balance_sheet(self) -> Statement:
        """
        Retrieves the Balance Sheet (Statement of Financial Position).

        This statement provides a snapshot of the company's financial position at a specific point in time,
        showing its assets, liabilities, and shareholders' equity.

        Returns:
            Statement: The Balance Sheet data, or None if not found.
        """
        statement_name = self._get_statement_name_for_standard_name(balance_sheet)
        if statement_name:
            return self.xbrl_data.get_statement(statement_name, display_name="Consolidated Balance Sheets")

    def get_income_statement(self) -> Optional[Statement]:
        """
        Retrieves the Income Statement (Statement of Operations).

        This statement shows the company's revenues, expenses, and resulting profit or loss over a specific period.
        It may also be referred to as the Profit and Loss Statement (P&L) or Statement of Earnings.

        Returns:
            Statement: The Income Statement data, or None if not found.
        """
        statement_name = self._get_statement_name_for_standard_name(income_statement)
        if statement_name:
            return self.xbrl_data.get_statement(statement_name,
                                                display_name="Income Statements") if statement_name else None

    def get_cash_flow_statement(self) -> Statement:
        """
        Retrieves the Statement of Cash Flows.

        This statement shows how changes in balance sheet accounts and income affect cash and cash equivalents,
        breaking the analysis down into operating, investing, and financing activities.

        Returns:
            Statement: The Cash Flow Statement data, or None if not found.
        """
        statement_name = self._get_statement_name_for_standard_name(cash_flow_statement)
        if statement_name:
            return self.xbrl_data.get_statement(statement_name, display_name="Consolidated Statement of Cash Flows")

    def get_statement_of_changes_in_equity(self) -> Statement:
        """
        Retrieves the Statement of Changes in Equity (Statement of Stockholders' Equity).

        This statement shows the changes in the company's equity over a period, including items such as
        share capital, retained earnings, and other equity items.

        Returns:
            Statement: The Statement of Changes in Equity data, or None if not found.
        """
        statement_name = self._get_statement_name_for_standard_name(statement_of_changes_in_equity)
        if statement_name:
            return self.xbrl_data.get_statement(statement_name,
                                                display_name="Consolidated Statement of Shareholders Equity")

    def get_statement_of_comprehensive_income(self) -> Statement:
        """
        Retrieves the Statement of Comprehensive Income.

        This statement shows all changes in equity during a period, except those resulting from
        investments by owners and distributions to owners. It includes both net income from the
        Income Statement and other comprehensive income items.

        Returns:
            Statement: The Statement of Comprehensive Income data, or None if not found.
        """
        statement_name = self._get_statement_name_for_standard_name(statement_of_comprehensive_income)
        if statement_name:
            return self.xbrl_data.get_statement(statement_name,
                                                display_name="Comprehensive Income Statement")

    def get_cover_page(self) -> Statement:
        """
        Retrieves the Document and Entity Information.

        This is not a financial statement per se, but contains important metadata about the filing entity
        and the document itself, such as company name, filing date, and other regulatory information.

        Returns:
            Statement: The Document and Entity Information data, or None if not found.
        """
        statement_name = self._get_statement_name_for_standard_name(cover_page)
        if statement_name:
            return self.xbrl_data.get_statement(statement_name, display_name="Cover Page")

    def find_role_by_concept(self, concept: str) -> Optional[str]:
        """
        Helper method to find a role containing specific concepts.

        Args:
            concept str: Concept names to search for.

        Returns:
            Optional[str]: The role containing the most matching concepts, or None if no matches found.
        """
        role_matches = defaultdict(int)
        for role in self.xbrl_data.presentation.get_roles_containing_concept(concept):
            role_matches[role] += 1

        return max(role_matches, key=role_matches.get) if role_matches else None

    def list_standard_statements(self) -> List[str]:
        return [
            standard_statement.display_name
            for standard_statement in [cover_page, balance_sheet, income_statement, cash_flow_statement,
                                       statement_of_changes_in_equity, statement_of_comprehensive_income]
            if self._get_statement_name_for_standard_name(standard_statement) is not None
        ]

    def get_dimensioned_statement(self, statement_name: str, dimensions: Dict[str, str]) -> Optional[Statement]:
        return self.xbrl_data.generate_dimensioned_statement(statement_name, dimensions)

    def pivot_statement(self, statement_name: str, dimension: str) -> pd.DataFrame:
        return self.xbrl_data.pivot_on_dimension(statement_name, dimension)

    def compare_statement_dimensions(self, statement_name: str, dimension: str, value1: str,
                                     value2: str) -> pd.DataFrame:
        return self.xbrl_data.compare_dimension_values(statement_name, dimension, value1, value2)

    def __rich__(self):
        statements_table = Table(Column(""), Column("Standard Financial Statements", justify="left"),
                                 box=box.ROUNDED, show_header=True)
        for index, statement in enumerate(self.list_standard_statements()):
            statements_table.add_row(str(index + 1), statement)

        contents = [statements_table]

        panel = Panel(
            Group(*contents),
            title=Text.assemble((self.xbrl_data.company, "bold deep_sky_blue1"), " financials",
                                (f" period ended {self.xbrl_data.period_end}", "bold green")),
        )
        return panel

    def __repr__(self):
        return repr_rich(self.__rich__())
