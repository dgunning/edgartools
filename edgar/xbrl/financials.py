from collections import defaultdict
from typing import Optional, List, Dict

import pandas as pd

from edgar.xbrl.parser import XBRLData, XBRLPresentation, StatementData, FinancialStatementMapper


class Financials:

    @classmethod
    def get_standard_name(cls, role_name: str) -> Optional[str]:
        role_name_normalized = ''.join(char.upper() for char in role_name if char.isalnum())
        for standard_name, variations in FinancialStatementMapper.STANDARD_STATEMENTS.items():
            if any(variation in role_name_normalized for variation in variations):
                return standard_name
        return None

    def __init__(self, xbrl_data: XBRLData):
        self.xbrl_data:XBRLData = xbrl_data
        self.presentation:XBRLPresentation = xbrl_data.presentation

    @classmethod
    def extract(cls, filing):
        assert filing.form in ['10-K', '10-Q', '10-K/A', '10-Q/A'], "Filing must be a 10-K or 10-Q"
        xbrl_data = XBRLData.extract(filing)
        return cls(xbrl_data)

    def get_balance_sheet(self) -> StatementData:
        """
        Retrieves the Balance Sheet (Statement of Financial Position).

        This statement provides a snapshot of the company's financial position at a specific point in time,
        showing its assets, liabilities, and shareholders' equity.

        Returns:
            StatementData: The Balance Sheet data, or None if not found.
        """
        role = self.xbrl_data.presentation.get_role_by_standard_name('BALANCE_SHEET')
        if not role:
            balance_sheet_concepts = ['us-gaap_StatementOfFinancialPositionAbstract',
                                      'us-gaap_AssetsAbstract',
                                      'us-gaap_LiabilitiesAndStockholdersEquityAbstract',
                                      'us-gaap_StockholdersEquity',
                                      'us-gaap_ShareholdersEquity']
            role = self._find_role_by_concepts(balance_sheet_concepts)

        standard_name = role.split('/')[-1]

        return self.xbrl_data.get_statement(standard_name, display_name="Consolidated Balance Sheets") if standard_name else None

    def get_income_statement(self) -> Optional[StatementData]:
        """
        Retrieves the Income Statement (Statement of Operations).

        This statement shows the company's revenues, expenses, and resulting profit or loss over a specific period.
        It may also be referred to as the Profit and Loss Statement (P&L) or Statement of Earnings.

        Returns:
            StatementData: The Income Statement data, or None if not found.
        """
        role = self.presentation.get_role_by_standard_name('INCOME_STATEMENT')
        if not role:
            income_statement_concepts = ['us-gaap_IncomeStatementAbstract',
                                         'us-gaap_RevenuesAbstract', 'us-gaap_OperatingExpensesAbstract']
            role = self._find_role_by_concepts(income_statement_concepts)
        if not role:
            return None

        standard_name = role.split('/')[-1]

        return self.xbrl_data.get_statement(standard_name, display_name="Income Statements") if standard_name else None

    def get_cash_flow_statement(self) -> StatementData:
        """
        Retrieves the Statement of Cash Flows.

        This statement shows how changes in balance sheet accounts and income affect cash and cash equivalents,
        breaking the analysis down into operating, investing, and financing activities.

        Returns:
            StatementData: The Cash Flow Statement data, or None if not found.
        """
        role = self.presentation.get_role_by_standard_name('CASH_FLOW')
        if not role:
            cash_flow_concepts = ['us-gaap_StatementOfCashFlowsAbstract',
                                  'us-gaap_NetCashProvidedByUsedInOperatingActivities',
                                  'us-gaap_NetCashProvidedByUsedInInvestingActivities',
                                  'us-gaap_NetCashProvidedByUsedInFinancingActivities']
            role = self._find_role_by_concepts(cash_flow_concepts)

        standard_name = role.split('/')[-1]

        return self.xbrl_data.get_statement(standard_name, display_name="Consolidated Statement of Cash Flows") if standard_name else None

    def get_statement_of_changes_in_equity(self) -> StatementData:
        """
        Retrieves the Statement of Changes in Equity (Statement of Stockholders' Equity).

        This statement shows the changes in the company's equity over a period, including items such as
        share capital, retained earnings, and other equity items.

        Returns:
            StatementData: The Statement of Changes in Equity data, or None if not found.
        """
        role = self.presentation.get_role_by_standard_name('EQUITY')
        if not role:
            equity_concepts = ['us-gaap_StatementOfStockholdersEquityAbstract',
                               'us-gaap_StockholdersEquity',
                               'us-gaap_ShareholdersEquity',
                               'us-gaap_RetainedEarnings',
                               'us-gaap_AdditionalPaidInCapital']
            role = self._find_role_by_concepts(equity_concepts)

        standard_name = role.split('/')[-1]

        return self.xbrl_data.get_statement(standard_name, display_name="Consolidated Statement of Shareholders Equity") if standard_name else None

    def get_statement_of_comprehensive_income(self) -> StatementData:
        """
        Retrieves the Statement of Comprehensive Income.

        This statement shows all changes in equity during a period, except those resulting from
        investments by owners and distributions to owners. It includes both net income from the
        Income Statement and other comprehensive income items.

        Returns:
            StatementData: The Statement of Comprehensive Income data, or None if not found.
        """
        role = self.presentation.get_role_by_standard_name('COMPREHENSIVE_INCOME')
        if not role:
            comprehensive_income_concepts = ['us-gaap_StatementOfIncomeAndComprehensiveIncomeAbstract',
                                             'us-gaap_StatementOfIncomeAndComprehensiveIncomeAbstract',
                                             'gaap_OtherComprehensiveIncomeLossNetOfTax',
                                             'us-gaap_ComprehensiveIncomeNetOfTax']
            role = self._find_role_by_concepts(comprehensive_income_concepts)

        standard_name = role.split('/')[-1]

        return self.xbrl_data.get_statement(standard_name, display_name="Comprehensive Income Statement") if standard_name else None

    def get_cover_page(self) -> StatementData:
        """
        Retrieves the Document and Entity Information.

        This is not a financial statement per se, but contains important metadata about the filing entity
        and the document itself, such as company name, filing date, and other regulatory information.

        Returns:
            StatementData: The Document and Entity Information data, or None if not found.
        """
        role = self.presentation.get_role_by_standard_name('COVER_PAGE')
        if not role:
            cover_page_concepts = ['dei_CoverAbstract',
                                   'dei_EntityRegistrantName',
                                   'dei_DocumentType',
                                   'dei_DocumentPeriodEndDate']
            role = self._find_role_by_concepts(cover_page_concepts)

        standard_name = role.split('/')[-1]

        return self.xbrl_data.get_statement(standard_name, display_name="Cover Page") if standard_name else None

    def _find_role_by_concepts(self, concepts: List[str]) -> Optional[str]:
        """
        Helper method to find a role containing specific concepts.

        Args:
            concepts (List[str]): List of concept names to search for.

        Returns:
            Optional[str]: The role containing the most matching concepts, or None if no matches found.
        """
        role_matches = defaultdict(int)
        for concept in concepts:
            for role in self.xbrl_data.presentation.get_roles_containing_concept(concept):
                role_matches[role] += 1

        return max(role_matches, key=role_matches.get) if role_matches else None

    def get_dimensioned_statement(self, statement_name: str, dimensions: Dict[str, str]) -> Optional[StatementData]:
        return self.xbrl_data.generate_dimensioned_statement(statement_name, dimensions)

    def pivot_statement(self, statement_name: str, dimension: str) -> pd.DataFrame:
        return self.xbrl_data.pivot_on_dimension(statement_name, dimension)

    def compare_statement_dimensions(self, statement_name: str, dimension: str, value1: str,
                                     value2: str) -> pd.DataFrame:
        return self.xbrl_data.compare_dimension_values(statement_name, dimension, value1, value2)

