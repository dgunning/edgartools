"""
Financial ratio analysis module for XBRL data.

This module provides a comprehensive set of financial ratio calculations
for analyzing company performance, efficiency, and financial health.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
import pandas as pd
from ..standardization import MappingStore, StandardConcept

@dataclass
class RatioResult:
    """Container for ratio calculation results with metadata."""
    value: float
    components: Dict[str, float]
    period: str
    
    def __repr__(self) -> str:
        return f"{self.value:.2f} ({self.period})"

class FinancialRatios:
    """Calculate and analyze financial ratios from XBRL data."""
    
    def __init__(self, xbrl):
        """Initialize with an XBRL instance."""
        self.xbrl = xbrl
        self._balance_sheet_df = None
        self._income_stmt_df = None
        self._cash_flow_df = None
        self._bs_period = None
        self._is_period = None
        self._cf_period = None
        
        # Initialize concept mappings
        self._mapping_store = MappingStore()
        
        # Initialize dataframes if statements exist
        bs = self.xbrl.statements.balance_sheet()
        bs_rendered = bs.render()
        self._balance_sheet_df = bs_rendered.to_dataframe()
        self._bs_period = bs_rendered.periods[0].label
            
        is_ = self.xbrl.statements.income_statement()
        is_rendered = is_.render()
        self._income_stmt_df = is_rendered.to_dataframe()
        self._is_period = is_rendered.periods[0].label
            
        cf = self.xbrl.statements.cash_flow_statement()
        cf_rendered = cf.render()
        self._cash_flow_df = cf_rendered.to_dataframe()
        self._cf_period = cf_rendered.periods[0].label
        
    def _get_value(self, label: str, statement_type: str = "BalanceSheet") -> Optional[float]:
        """Safely extract a numeric value using the standardized label from the appropriate statement."""
        try:
            # Get list of possible XBRL concepts for this label
            concepts = self._mapping_store.get_company_concepts(label)
            if not concepts:
                return None
                
            # Try each concept until we find one that exists
            df = None
            period = None
            if statement_type == "BalanceSheet" and self._balance_sheet_df is not None:
                df = self._balance_sheet_df
                period = self._bs_period
            elif statement_type == "IncomeStatement" and self._income_stmt_df is not None:
                df = self._income_stmt_df
                period = self._is_period
            elif statement_type == "CashFlow" and self._cash_flow_df is not None:
                df = self._cash_flow_df
                period = self._cf_period
                
            if df is None or period is None:
                return None
                
            # Try each concept until we find one that exists
            for concept in concepts:
                try:
                    return df.loc[concept, period]
                except KeyError:
                    continue
                    
            return None
        except ValueError:
            return None
            
    def liquidity_ratios(self) -> Dict[str, RatioResult]:
        """Calculate liquidity ratios.
        
        Returns:
            Dict containing:
            - current_ratio
            - quick_ratio
            - cash_ratio
            - working_capital
        """
        current_assets = self._get_value(StandardConcept.TOTAL_CURRENT_ASSETS)
        current_liab = self._get_value(StandardConcept.TOTAL_CURRENT_LIABILITIES)
        cash = self._get_value(StandardConcept.CASH_AND_EQUIVALENTS)
        inventory = self._get_value(StandardConcept.INVENTORY)
        receivables = self._get_value(StandardConcept.ACCOUNTS_RECEIVABLE)
        
        if not all([current_assets, current_liab]):
            return {}
            
        period = self.xbrl.reporting_periods()[0]
        
        results = {}
        
        # Current Ratio
        assert current_assets is not None and current_liab is not None  # Help type checker
        results['current_ratio'] = RatioResult(
            value=current_assets / current_liab,
            components={
                'current_assets': current_assets,
                'current_liabilities': current_liab
            },
            period=period
        )
        
        # Quick Ratio
        if all([inventory, receivables]):
            assert inventory is not None  # Help type checker
            quick_assets = current_assets - inventory
            assert current_liab is not None  # Help type checker
            results['quick_ratio'] = RatioResult(
                value=quick_assets / current_liab,
                components={
                    'quick_assets': quick_assets,
                    'current_liabilities': current_liab
                },
                period=period
            )
            
        # Cash Ratio
        if cash:
            assert cash is not None  # Help type checker
            assert current_liab is not None  # Help type checker
            results['cash_ratio'] = RatioResult(
                value=cash / current_liab,
                components={
                    'cash': cash,
                    'current_liabilities': current_liab
                },
                period=period
            )
            
        # Working Capital
        assert current_assets is not None and current_liab is not None  # Help type checker
        results['working_capital'] = RatioResult(
            value=current_assets - current_liab,
            components={
                'current_assets': current_assets,
                'current_liabilities': current_liab
            },
            period=period
        )
        
        return results
        
    def profitability_ratios(self) -> Dict[str, RatioResult]:
        """Calculate profitability ratios.
        
        Returns:
            Dict containing:
            - gross_margin
            - operating_margin
            - net_margin
            - return_on_assets
            - return_on_equity
        """
        revenue = self._get_value(StandardConcept.REVENUE, "IncomeStatement")
        gross_profit = self._get_value(StandardConcept.GROSS_PROFIT, "IncomeStatement")
        operating_income = self._get_value(StandardConcept.OPERATING_INCOME, "IncomeStatement")
        net_income = self._get_value(StandardConcept.NET_INCOME, "IncomeStatement")
        total_assets = self._get_value(StandardConcept.TOTAL_ASSETS)
        total_equity = self._get_value(StandardConcept.TOTAL_EQUITY)
        
        if not revenue:
            return {}
            
        period = self.xbrl.reporting_periods()[0]
        results = {}
        
        # Margin Ratios
        if gross_profit:
            assert gross_profit is not None and revenue is not None  # Help type checker
            results['gross_margin'] = RatioResult(
                value=gross_profit / revenue,
                components={
                    'gross_profit': gross_profit,
                    'revenue': revenue
                },
                period=period
            )
            
        if operating_income:
            assert operating_income is not None and revenue is not None  # Help type checker
            results['operating_margin'] = RatioResult(
                value=operating_income / revenue,
                components={
                    'operating_income': operating_income,
                    'revenue': revenue
                },
                period=period
            )
            
        if net_income:
            assert net_income is not None and revenue is not None  # Help type checker
            results['net_margin'] = RatioResult(
                value=net_income / revenue,
                components={
                    'net_income': net_income,
                    'revenue': revenue
                },
                period=period
            )
            
        # Return Ratios
        if all([net_income, total_assets]):
            assert net_income is not None and total_assets is not None  # Help type checker
            results['return_on_assets'] = RatioResult(
                value=net_income / total_assets,
                components={
                    'net_income': net_income,
                    'total_assets': total_assets
                },
                period=period
            )
            
        if all([net_income, total_equity]):
            assert net_income is not None and total_equity is not None  # Help type checker
            results['return_on_equity'] = RatioResult(
                value=net_income / total_equity,
                components={
                    'net_income': net_income,
                    'total_equity': total_equity
                },
                period=period
            )
            
        return results
        
    def efficiency_ratios(self) -> Dict[str, RatioResult]:
        """Calculate efficiency ratios.
        
        Returns:
            Dict containing:
            - asset_turnover
            - inventory_turnover
            - receivables_turnover
            - days_sales_outstanding
        """
        revenue = self._get_value(StandardConcept.REVENUE, "IncomeStatement")
        total_assets = self._get_value(StandardConcept.TOTAL_ASSETS)
        inventory = self._get_value(StandardConcept.INVENTORY)
        cogs = self._get_value(StandardConcept.COST_OF_REVENUE, "IncomeStatement")
        receivables = self._get_value(StandardConcept.ACCOUNTS_RECEIVABLE)
        
        period = self.xbrl.reporting_periods()[0]
        results = {}
        
        # Asset Turnover
        if all([revenue, total_assets]):
            assert revenue is not None and total_assets is not None  # Help type checker
            results['asset_turnover'] = RatioResult(
                value=revenue / total_assets,
                components={
                    'revenue': revenue,
                    'total_assets': total_assets
                },
                period=period
            )
            
        # Inventory Turnover
        if all([cogs, inventory]):
            assert cogs is not None and inventory is not None  # Help type checker
            results['inventory_turnover'] = RatioResult(
                value=cogs / inventory,
                components={
                    'cogs': cogs,
                    'inventory': inventory
                },
                period=period
            )
            
        # Receivables Turnover
        if all([revenue, receivables]):
            assert revenue is not None and receivables is not None  # Help type checker
            turnover = revenue / receivables
            results['receivables_turnover'] = RatioResult(
                value=turnover,
                components={
                    'revenue': revenue,
                    'receivables': receivables
                },
                period=period
            )
            
            # Days Sales Outstanding
            assert turnover is not None  # Help type checker
            results['days_sales_outstanding'] = RatioResult(
                value=365 / turnover,
                components={
                    'receivables_turnover': turnover
                },
                period=period
            )
            
        return results
        
    def leverage_ratios(self) -> Dict[str, RatioResult]:
        """Calculate leverage ratios.
        
        Returns:
            Dict containing:
            - debt_to_equity
            - debt_to_assets
            - interest_coverage
            - equity_multiplier
        """
        total_debt = self._get_value(StandardConcept.LONG_TERM_DEBT)
        total_equity = self._get_value(StandardConcept.TOTAL_EQUITY)
        total_assets = self._get_value(StandardConcept.TOTAL_ASSETS)
        operating_income = self._get_value(StandardConcept.OPERATING_INCOME, "IncomeStatement")
        interest_expense = self._get_value(StandardConcept.INTEREST_EXPENSE, "IncomeStatement")
        
        period = self.xbrl.reporting_periods()[0]
        results = {}
        
        # Debt to Equity
        if all([total_debt, total_equity]):
            assert total_debt is not None and total_equity is not None  # Help type checker
            results['debt_to_equity'] = RatioResult(
                value=total_debt / total_equity,
                components={
                    'total_debt': total_debt,
                    'total_equity': total_equity
                },
                period=period
            )
            
        # Debt to Assets
        if all([total_debt, total_assets]):
            assert total_debt is not None and total_assets is not None  # Help type checker
            results['debt_to_assets'] = RatioResult(
                value=total_debt / total_assets,
                components={
                    'total_debt': total_debt,
                    'total_assets': total_assets
                },
                period=period
            )
            
        # Interest Coverage
        if all([operating_income, interest_expense]) and interest_expense != 0:
            assert operating_income is not None and interest_expense is not None  # Help type checker
            results['interest_coverage'] = RatioResult(
                value=operating_income / interest_expense,
                components={
                    'operating_income': operating_income,
                    'interest_expense': interest_expense
                },
                period=period
            )
            
        # Equity Multiplier
        if all([total_assets, total_equity]):
            assert total_assets is not None and total_equity is not None  # Help type checker
            results['equity_multiplier'] = RatioResult(
                value=total_assets / total_equity,
                components={
                    'total_assets': total_assets,
                    'total_equity': total_equity
                },
                period=period
            )
            
        return results
        
    def calculate_all(self) -> Dict[str, Dict[str, RatioResult]]:
        """Calculate all available financial ratios."""
        return {
            'liquidity': self.liquidity_ratios(),
            'profitability': self.profitability_ratios(),
            'efficiency': self.efficiency_ratios(),
            'leverage': self.leverage_ratios()
        }