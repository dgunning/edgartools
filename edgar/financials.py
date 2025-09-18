from typing import Any, Dict, Optional, Union

import pandas as pd

from edgar.core import log
from edgar.richtools import repr_rich
from edgar.xbrl import XBRL, XBRLS, Statement
from edgar.xbrl.xbrl import XBRLFilingWithNoXbrlData


class Financials:
    def __init__(self, xb: Optional[XBRL]):
        self.xb: XBRL = xb

    @classmethod
    def extract(cls, filing) -> Optional["Financials"]:
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

    # Standardized Financial Data Accessor Methods
    # These methods provide easy access to common financial metrics
    # using standardized labels across different companies

    def _get_standardized_concept_value(self, statement_type: str, concept_patterns: list, 
                                      period_offset: int = 0) -> Optional[Union[int, float]]:
        """
        Helper method to extract standardized concept values from financial statements.

        Args:
            statement_type: Type of statement ('income', 'balance', 'cashflow')
            concept_patterns: List of label patterns to search for (case-insensitive)
            period_offset: Which period to get (0=most recent, 1=previous, etc.)

        Returns:
            The concept value if found, None otherwise
        """
        if self.xb is None:
            return None

        try:
            # Get the appropriate statement
            if statement_type == 'income':
                statement = self.income_statement()
            elif statement_type == 'balance':
                statement = self.balance_sheet()
            elif statement_type == 'cashflow':
                statement = self.cashflow_statement()
            else:
                return None

            if statement is None:
                return None

            # Render with standardization enabled
            rendered = statement.render(standard=True)
            df = rendered.to_dataframe()

            if df.empty:
                return None

            # Find the concept using pattern matching
            for pattern in concept_patterns:
                matches = df[df['label'].str.contains(pattern, case=False, na=False)]
                if not matches.empty:
                    # Get available period columns (excluding metadata columns)
                    period_columns = [col for col in df.columns if col not in ['concept', 'label', 'level', 'abstract', 'dimension']]

                    if len(period_columns) > period_offset:
                        period_col = period_columns[period_offset]
                        value = matches.iloc[0][period_col]

                        # Convert to numeric if possible
                        if pd.notna(value) and value != '':
                            try:
                                return float(value) if '.' in str(value) else int(value)
                            except (ValueError, TypeError):
                                return value
                        return value

            return None

        except Exception as e:
            log.debug(f"Error getting standardized concept value: {e}")
            return None

    def get_revenue(self, period_offset: int = 0) -> Optional[Union[int, float]]:
        """
        Get revenue from the income statement using standardized labels.

        Args:
            period_offset: Which period to get (0=most recent, 1=previous, etc.)

        Returns:
            Revenue value if found, None otherwise

        Example:
            >>> company = Company('AAPL')
            >>> financials = company.get_financials()
            >>> revenue = financials.get_revenue()  # Most recent revenue
            >>> prev_revenue = financials.get_revenue(1)  # Previous period revenue
        """
        patterns = [
            r'Revenue$',           # Exact match for "Revenue"
            r'^Revenue',           # Starts with "Revenue"  
            r'Contract Revenue',   # Common standardized label
            r'Sales Revenue',      # Alternative form
            r'Total Revenue',      # Comprehensive revenue
            r'Net Revenue'         # Net form
        ]
        return self._get_standardized_concept_value('income', patterns, period_offset)

    def get_net_income(self, period_offset: int = 0) -> Optional[Union[int, float]]:
        """
        Get net income from the income statement using standardized labels.

        Args:
            period_offset: Which period to get (0=most recent, 1=previous, etc.)

        Returns:
            Net income value if found, None otherwise

        Example:
            >>> company = Company('AAPL')  
            >>> financials = company.get_financials()
            >>> net_income = financials.get_net_income()
        """
        patterns = [
            r'Net Income$',                    # Exact match
            r'^Net Income',                    # Starts with
            r'Net Income.*Common',             # Net income attributable to common
            r'Net Income.*Shareholders',       # Net income attributable to shareholders  
            r'Profit.*Loss',                   # International variations
            r'Net Earnings'                    # Alternative terminology
        ]
        return self._get_standardized_concept_value('income', patterns, period_offset)

    def get_total_assets(self, period_offset: int = 0) -> Optional[Union[int, float]]:
        """
        Get total assets from the balance sheet using standardized labels.

        Args:
            period_offset: Which period to get (0=most recent, 1=previous, etc.)

        Returns:
            Total assets value if found, None otherwise

        Example:
            >>> company = Company('AAPL')
            >>> financials = company.get_financials()  
            >>> total_assets = financials.get_total_assets()
        """
        patterns = [
            r'Total Assets$',      # Exact match
            r'^Total Assets',      # Starts with
            r'Assets$'             # Just "Assets" 
        ]
        return self._get_standardized_concept_value('balance', patterns, period_offset)

    def get_total_liabilities(self, period_offset: int = 0) -> Optional[Union[int, float]]:
        """
        Get total liabilities from the balance sheet using standardized labels.

        Args:
            period_offset: Which period to get (0=most recent, 1=previous, etc.)

        Returns:
            Total liabilities value if found, None otherwise
        """
        patterns = [
            r'Total Liabilities$',
            r'^Total Liabilities',
            r'Liabilities$'
        ]
        return self._get_standardized_concept_value('balance', patterns, period_offset)

    def get_stockholders_equity(self, period_offset: int = 0) -> Optional[Union[int, float]]:
        """
        Get stockholders' equity from the balance sheet using standardized labels.

        Args:
            period_offset: Which period to get (0=most recent, 1=previous, etc.)

        Returns:
            Stockholders' equity value if found, None otherwise
        """
        patterns = [
            r'Total.*Stockholders.*Equity',
            r'Stockholders.*Equity$',
            r'Shareholders.*Equity',
            r'Total.*Equity$',
            r'^Equity$'
        ]
        return self._get_standardized_concept_value('balance', patterns, period_offset)

    def get_operating_cash_flow(self, period_offset: int = 0) -> Optional[Union[int, float]]:
        """
        Get operating cash flow from the cash flow statement using standardized labels.

        Args:
            period_offset: Which period to get (0=most recent, 1=previous, etc.)

        Returns:
            Operating cash flow value if found, None otherwise
        """
        patterns = [
            r'Net Cash.*Operations',
            r'Operating.*Cash.*Flow',
            r'Cash.*Operations',
            r'Net Cash.*Operating'
        ]
        return self._get_standardized_concept_value('cashflow', patterns, period_offset)

    def get_free_cash_flow(self, period_offset: int = 0) -> Optional[Union[int, float]]:
        """
        Calculate free cash flow (Operating Cash Flow - Capital Expenditures).

        Args:
            period_offset: Which period to get (0=most recent, 1=previous, etc.)

        Returns:
            Free cash flow if both components found, None otherwise
        """
        operating_cf = self.get_operating_cash_flow(period_offset)
        capex = self.get_capital_expenditures(period_offset)

        if operating_cf is not None and capex is not None:
            # CapEx is usually negative, so we subtract it (making FCF = OCF - |CapEx|)
            return operating_cf - abs(capex)
        return None

    def get_capital_expenditures(self, period_offset: int = 0) -> Optional[Union[int, float]]:
        """
        Get capital expenditures from the cash flow statement using standardized labels.

        Args:
            period_offset: Which period to get (0=most recent, 1=previous, etc.)

        Returns:
            Capital expenditures value if found, None otherwise
        """
        patterns = [
            r'Capital Expenditures',
            r'Property.*Plant.*Equipment',
            r'Payments.*Property',
            r'Acquisitions.*Property',
            r'Capex'
        ]
        return self._get_standardized_concept_value('cashflow', patterns, period_offset)

    def get_current_assets(self, period_offset: int = 0) -> Optional[Union[int, float]]:
        """
        Get current assets from the balance sheet using standardized labels.

        Args:
            period_offset: Which period to get (0=most recent, 1=previous, etc.)

        Returns:
            Current assets value if found, None otherwise
        """
        patterns = [
            r'Total Current Assets',
            r'^Current Assets',
            r'Assets Current'
        ]
        return self._get_standardized_concept_value('balance', patterns, period_offset)

    def get_current_liabilities(self, period_offset: int = 0) -> Optional[Union[int, float]]:
        """
        Get current liabilities from the balance sheet using standardized labels.

        Args:
            period_offset: Which period to get (0=most recent, 1=previous, etc.)

        Returns:
            Current liabilities value if found, None otherwise
        """
        patterns = [
            r'Total Current Liabilities',
            r'^Current Liabilities',
            r'Liabilities Current'
        ]
        return self._get_standardized_concept_value('balance', patterns, period_offset)

    def get_financial_metrics(self) -> Dict[str, Any]:
        """
        Get a dictionary of common financial metrics using standardized labels.

        Returns:
            Dictionary containing available financial metrics

        Example:
            >>> company = Company('AAPL')
            >>> financials = company.get_financials()
            >>> metrics = financials.get_financial_metrics()
            >>> print(f"Revenue: ${metrics.get('revenue', 'N/A'):,}")
        """
        metrics = {}

        # Income Statement Metrics
        metrics['revenue'] = self.get_revenue()
        metrics['net_income'] = self.get_net_income()

        # Balance Sheet Metrics  
        metrics['total_assets'] = self.get_total_assets()
        metrics['total_liabilities'] = self.get_total_liabilities()
        metrics['stockholders_equity'] = self.get_stockholders_equity()
        metrics['current_assets'] = self.get_current_assets()
        metrics['current_liabilities'] = self.get_current_liabilities()

        # Cash Flow Metrics
        metrics['operating_cash_flow'] = self.get_operating_cash_flow()
        metrics['capital_expenditures'] = self.get_capital_expenditures()
        metrics['free_cash_flow'] = self.get_free_cash_flow()

        # Calculate basic ratios if we have the data
        if metrics['current_assets'] and metrics['current_liabilities']:
            try:
                metrics['current_ratio'] = metrics['current_assets'] / metrics['current_liabilities']
            except (TypeError, ZeroDivisionError):
                metrics['current_ratio'] = None
        else:
            metrics['current_ratio'] = None

        if metrics['total_liabilities'] and metrics['total_assets']:
            try:
                metrics['debt_to_assets'] = metrics['total_liabilities'] / metrics['total_assets'] 
            except (TypeError, ZeroDivisionError):
                metrics['debt_to_assets'] = None
        else:
            metrics['debt_to_assets'] = None

        return metrics

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

    def __init__(self, xbs: XBRLS):
        self.xbs = xbs

    @classmethod
    def extract(cls, filings) -> "MultiFinancials":
        return cls(XBRLS.from_filings(filings))

    def balance_sheet(self) -> Optional[Statement]:
        return self.xbs.statements.balance_sheet()

    def income_statement(self) -> Optional[Statement]:
        return self.xbs.statements.income_statement()

    def cashflow_statement(self) -> Optional[Statement]:
        return self.xbs.statements.cashflow_statement()

    def __rich__(self):
        return self.xbs.__rich__()

    def __repr__(self):
        return repr_rich(self.__rich__())
