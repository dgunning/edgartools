"""Financial metrics and analysis module.

This module provides various financial metrics and analysis tools including:
- Altman Z-Score for bankruptcy prediction
- Beneish M-Score for earnings manipulation detection
- Piotroski F-Score for financial strength assessment
- Montier C-Score for earnings manipulation detection
"""

from dataclasses import dataclass
from typing import Dict, Optional

from ..standardization import MappingStore, StandardConcept


@dataclass
class MetricResult:
    """Container for metric calculation results with metadata."""
    value: float
    components: Dict[str, float]
    interpretation: str
    period: str
    
    def __repr__(self) -> str:
        return f"{self.value:.2f} ({self.interpretation})"

class FinancialMetrics:
    """Base class for financial metrics calculations."""
    
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
        if self.xbrl.statements.balance_sheet:
            bs = self.xbrl.statements.balance_sheet
            self._balance_sheet_df = bs.to_dataframe()
            self._bs_period = bs.periods[0].label
            
        if self.xbrl.statements.income_statement:
            is_ = self.xbrl.statements.income_statement
            self._income_stmt_df = is_.to_dataframe()
            self._is_period = is_.periods[0].label
            
        if self.xbrl.statements.cash_flow:
            cf = self.xbrl.statements.cash_flow
            self._cash_flow_df = cf.to_dataframe()
            self._cf_period = cf.periods[0].label
    
    def _get_value(self, label: StandardConcept, statement_type: str = "BalanceSheet", period_offset: int = 0) -> Optional[float]:
        """Safely extract a numeric value using the standardized label from the appropriate statement.
        
        Args:
            label: The standardized concept to retrieve
            statement_type: Type of financial statement ("BalanceSheet", "IncomeStatement", "CashFlow")
            period_offset: Offset from current period (0 for current, -1 for prior, etc.)
            
        Returns:
            The numeric value if found, None otherwise
        """
        try:
            concepts = self._mapping_store.get_company_concepts(label)
            if not concepts:
                return None
                
            df = None
            if statement_type == "BalanceSheet" and self._balance_sheet_df is not None:
                df = self._balance_sheet_df
            elif statement_type == "IncomeStatement" and self._income_stmt_df is not None:
                df = self._income_stmt_df
            elif statement_type == "CashFlow" and self._cash_flow_df is not None:
                df = self._cash_flow_df
                
            if df is None:
                return None
                
            # Get all available periods
            periods = df.columns.tolist()
            if not periods:
                return None
                
            # Get target period based on offset
            try:
                target_period = periods[period_offset]
            except IndexError:
                return None
                
            # Try each concept mapping
            for concept in concepts:
                try:
                    return df.loc[concept, target_period]
                except KeyError:
                    continue
                    
            return None
        except ValueError:
            return None

class AltmanZScore(FinancialMetrics):
    """Calculate Altman Z-Score for bankruptcy prediction."""
    
    def calculate(self) -> Optional[MetricResult]:
        """Calculate Altman Z-Score.
        
        Z-Score = 1.2X₁ + 1.4X₂ + 3.3X₃ + 0.6X₄ + 1.0X₅
        where:
        X₁ = Working Capital / Total Assets
        X₂ = Retained Earnings / Total Assets
        X₃ = EBIT / Total Assets
        X₄ = Market Value of Equity / Total Liabilities
        X₅ = Sales / Total Assets
        """
        # Get required values
        working_capital = self._get_working_capital()
        total_assets = self._get_value(StandardConcept.TOTAL_ASSETS)
        retained_earnings = self._get_value(StandardConcept.RETAINED_EARNINGS)
        ebit = self._get_value(StandardConcept.OPERATING_INCOME, "IncomeStatement")
        market_value = self._get_value(StandardConcept.TOTAL_EQUITY)  # Using book value as proxy
        total_liabilities = self._get_value(StandardConcept.TOTAL_LIABILITIES)
        revenue = self._get_value(StandardConcept.REVENUE, "IncomeStatement")
        
        # Check if we have all required values
        if not all([working_capital, total_assets, retained_earnings, ebit, 
                    market_value, total_liabilities, revenue]):
            return None
            
        # Cast to float to help type checker
        working_capital = float(working_capital)  # type: ignore
        total_assets = float(total_assets)  # type: ignore
        retained_earnings = float(retained_earnings)  # type: ignore
        ebit = float(ebit)  # type: ignore
        market_value = float(market_value)  # type: ignore
        total_liabilities = float(total_liabilities)  # type: ignore
        revenue = float(revenue)  # type: ignore
            
        # Calculate ratios
        x1 = working_capital / total_assets
        x2 = retained_earnings / total_assets
        x3 = ebit / total_assets
        x4 = market_value / total_liabilities
        x5 = revenue / total_assets
        
        # Calculate Z-Score
        z_score = 1.2*x1 + 1.4*x2 + 3.3*x3 + 0.6*x4 + 1.0*x5
        
        # Interpret score
        if z_score > 2.99:
            interpretation = "Safe Zone: Low probability of financial distress"
        elif z_score > 1.81:
            interpretation = "Grey Zone: Moderate risk of financial distress"
        else:
            interpretation = "Distress Zone: High risk of financial distress"
        
        return MetricResult(
            value=z_score,
            components={
                'working_capital_to_assets': x1,
                'retained_earnings_to_assets': x2,
                'ebit_to_assets': x3,
                'equity_to_liabilities': x4,
                'sales_to_assets': x5
            },
            interpretation=interpretation,
            period=self._bs_period if self._bs_period is not None else ""
        )
        
    def _get_working_capital(self) -> Optional[float]:
        """Calculate working capital."""
        current_assets = self._get_value(StandardConcept.TOTAL_CURRENT_ASSETS)
        current_liab = self._get_value(StandardConcept.TOTAL_CURRENT_LIABILITIES)
        
        if current_assets is None or current_liab is None:
            return None
            
        return current_assets - current_liab

class BeneishMScore(FinancialMetrics):
    """Calculate Beneish M-Score for earnings manipulation detection."""
    
    def calculate(self) -> Optional[MetricResult]:
        """Calculate Beneish M-Score.
        
        M-Score = -4.84 + 0.92*DSRI + 0.528*GMI + 0.404*AQI + 0.892*SGI + 0.115*DEPI 
                  - 0.172*SGAI + 4.679*TATA - 0.327*LVGI
        
        where:
        DSRI = Days Sales in Receivables Index
        GMI = Gross Margin Index
        AQI = Asset Quality Index
        SGI = Sales Growth Index
        DEPI = Depreciation Index
        SGAI = SG&A Expense Index
        TATA = Total Accruals to Total Assets
        LVGI = Leverage Index
        
        A score greater than -2.22 indicates a high probability of earnings manipulation.
        """
        # Get current year values
        receivables = self._get_value(StandardConcept.ACCOUNTS_RECEIVABLE)
        revenue = self._get_value(StandardConcept.REVENUE, "IncomeStatement")
        gross_profit = self._get_value(StandardConcept.GROSS_PROFIT, "IncomeStatement")
        total_assets = self._get_value(StandardConcept.TOTAL_ASSETS)
        ppe = self._get_value(StandardConcept.PROPERTY_PLANT_EQUIPMENT)
        depreciation = self._get_value(StandardConcept.DEPRECIATION_AMORTIZATION, "IncomeStatement")
        sga = self._get_value(StandardConcept.SGA_EXPENSE, "IncomeStatement")
        total_liabilities = self._get_value(StandardConcept.TOTAL_LIABILITIES)
        
        # Get prior year values (assuming they're available)
        prior_receivables = self._get_value(StandardConcept.ACCOUNTS_RECEIVABLE, period_offset=-1)
        prior_revenue = self._get_value(StandardConcept.REVENUE, "IncomeStatement", period_offset=-1)
        prior_gross_profit = self._get_value(StandardConcept.GROSS_PROFIT, "IncomeStatement", period_offset=-1)
        prior_total_assets = self._get_value(StandardConcept.TOTAL_ASSETS, period_offset=-1)
        prior_ppe = self._get_value(StandardConcept.PROPERTY_PLANT_EQUIPMENT, period_offset=-1)
        prior_depreciation = self._get_value(StandardConcept.DEPRECIATION_AMORTIZATION, "IncomeStatement", period_offset=-1)
        prior_sga = self._get_value(StandardConcept.SGA_EXPENSE, "IncomeStatement", period_offset=-1)
        prior_total_liabilities = self._get_value(StandardConcept.TOTAL_LIABILITIES, period_offset=-1)
        
        # Check if we have all required values
        if not all([receivables, revenue, gross_profit, total_assets, ppe, depreciation, sga, total_liabilities,
                    prior_receivables, prior_revenue, prior_gross_profit, prior_total_assets, prior_ppe,
                    prior_depreciation, prior_sga, prior_total_liabilities]):
            return None
            
        # Cast to float to help type checker
        receivables = float(receivables)  # type: ignore
        revenue = float(revenue)  # type: ignore
        gross_profit = float(gross_profit)  # type: ignore
        total_assets = float(total_assets)  # type: ignore
        ppe = float(ppe)  # type: ignore
        depreciation = float(depreciation)  # type: ignore
        sga = float(sga)  # type: ignore
        total_liabilities = float(total_liabilities)  # type: ignore
        
        prior_receivables = float(prior_receivables)  # type: ignore
        prior_revenue = float(prior_revenue)  # type: ignore
        prior_gross_profit = float(prior_gross_profit)  # type: ignore
        prior_total_assets = float(prior_total_assets)  # type: ignore
        prior_ppe = float(prior_ppe)  # type: ignore
        prior_depreciation = float(prior_depreciation)  # type: ignore
        prior_sga = float(prior_sga)  # type: ignore
        prior_total_liabilities = float(prior_total_liabilities)  # type: ignore
        
        # Calculate components
        dsri = (receivables / revenue) / (prior_receivables / prior_revenue)
        gmi = (prior_gross_profit / prior_revenue) / (gross_profit / revenue)
        aqi = ((total_assets - ppe) / total_assets) / ((prior_total_assets - prior_ppe) / prior_total_assets)
        sgi = revenue / prior_revenue
        depi = (prior_depreciation / prior_ppe) / (depreciation / ppe)
        sgai = (sga / revenue) / (prior_sga / prior_revenue)
        tata = (total_assets - prior_total_assets) / total_assets
        lvgi = (total_liabilities / total_assets) / (prior_total_liabilities / prior_total_assets)
        
        # Calculate M-Score
        m_score = -4.84 + 0.92*dsri + 0.528*gmi + 0.404*aqi + 0.892*sgi + \
                  0.115*depi - 0.172*sgai + 4.679*tata - 0.327*lvgi
        
        # Interpret score
        if m_score > -2.22:
            interpretation = "High probability of earnings manipulation"
        else:
            interpretation = "Low probability of earnings manipulation"
        
        return MetricResult(
            value=m_score,
            components={
                'dsri': dsri,
                'gmi': gmi,
                'aqi': aqi,
                'sgi': sgi,
                'depi': depi,
                'sgai': sgai,
                'tata': tata,
                'lvgi': lvgi
            },
            interpretation=interpretation,
            period=self._bs_period if self._bs_period is not None else ""
        )

class PiotroskiFScore(FinancialMetrics):
    """Calculate Piotroski F-Score for financial strength assessment."""
    
    def calculate(self) -> Optional[MetricResult]:
        """Calculate Piotroski F-Score.
        
        The F-Score is the sum of 9 binary signals (0 or 1) across three categories:
        
        Profitability:
        1. Return on Assets (ROA) > 0
        2. Operating Cash Flow > 0
        3. ROA(t) > ROA(t-1)
        4. Cash flow from operations > ROA
        
        Leverage, Liquidity and Source of Funds:
        5. Long-term debt ratio(t) < Long-term debt ratio(t-1)
        6. Current ratio(t) > Current ratio(t-1)
        7. No new shares issued
        
        Operating Efficiency:
        8. Gross margin(t) > Gross margin(t-1)
        9. Asset turnover(t) > Asset turnover(t-1)
        
        A score of 8-9 indicates a strong company, while 0-2 indicates a weak company.
        """
        scores = {}
        total_score = 0
        
        # Get current year values
        net_income = self._get_value(StandardConcept.NET_INCOME, "IncomeStatement")
        total_assets = self._get_value(StandardConcept.TOTAL_ASSETS)
        operating_cash_flow = self._get_value(StandardConcept.OPERATING_CASH_FLOW, "CashFlow")
        long_term_debt = self._get_value(StandardConcept.LONG_TERM_DEBT)
        current_assets = self._get_value(StandardConcept.TOTAL_CURRENT_ASSETS)
        current_liab = self._get_value(StandardConcept.TOTAL_CURRENT_LIABILITIES)
        shares_outstanding = self._get_value(StandardConcept.SHARES_OUTSTANDING)
        revenue = self._get_value(StandardConcept.REVENUE, "IncomeStatement")
        gross_profit = self._get_value(StandardConcept.GROSS_PROFIT, "IncomeStatement")
        
        # Get prior year values
        prior_net_income = self._get_value(StandardConcept.NET_INCOME, "IncomeStatement", -1)
        prior_total_assets = self._get_value(StandardConcept.TOTAL_ASSETS, "BalanceSheet", -1)
        prior_long_term_debt = self._get_value(StandardConcept.LONG_TERM_DEBT, "BalanceSheet", -1)
        prior_current_assets = self._get_value(StandardConcept.TOTAL_CURRENT_ASSETS, "BalanceSheet", -1)
        prior_current_liab = self._get_value(StandardConcept.TOTAL_CURRENT_LIABILITIES, "BalanceSheet", -1)
        prior_shares_outstanding = self._get_value(StandardConcept.SHARES_OUTSTANDING, "BalanceSheet", -1)
        prior_revenue = self._get_value(StandardConcept.REVENUE, "IncomeStatement", -1)
        prior_gross_profit = self._get_value(StandardConcept.GROSS_PROFIT, "IncomeStatement", -1)
        
        # Check if we have minimum required values for any calculations
        if not all([net_income, total_assets, operating_cash_flow]):
            return None
            
        # Cast to float
        net_income = float(net_income)  # type: ignore
        total_assets = float(total_assets)  # type: ignore
        operating_cash_flow = float(operating_cash_flow)  # type: ignore
        
        # 1. ROA > 0
        roa = net_income / total_assets
        scores['roa_positive'] = 1 if roa > 0 else 0
        total_score += scores['roa_positive']
        
        # 2. Operating Cash Flow > 0
        scores['cfoa_positive'] = 1 if operating_cash_flow > 0 else 0
        total_score += scores['cfoa_positive']
        
        # 3. ROA(t) > ROA(t-1)
        if prior_net_income is not None and prior_total_assets is not None:
            prior_roa = float(prior_net_income) / float(prior_total_assets)  # type: ignore
            scores['roa_higher'] = 1 if roa > prior_roa else 0
            total_score += scores['roa_higher']
        
        # 4. Cash flow from operations > ROA
        scores['quality_earnings'] = 1 if operating_cash_flow / total_assets > roa else 0
        total_score += scores['quality_earnings']
        
        # 5. Long-term debt ratio
        if all([long_term_debt, prior_long_term_debt]):
            ltdr = float(long_term_debt) / total_assets  # type: ignore
            prior_ltdr = float(prior_long_term_debt) / float(prior_total_assets)  # type: ignore
            scores['leverage_lower'] = 1 if ltdr < prior_ltdr else 0
            total_score += scores['leverage_lower']
        
        # 6. Current ratio
        if all([current_assets, current_liab, prior_current_assets, prior_current_liab]):
            curr_ratio = float(current_assets) / float(current_liab)  # type: ignore
            prior_curr_ratio = float(prior_current_assets) / float(prior_current_liab)  # type: ignore
            scores['liquidity_higher'] = 1 if curr_ratio > prior_curr_ratio else 0
            total_score += scores['liquidity_higher']
        
        # 7. No new shares issued
        if shares_outstanding is not None and prior_shares_outstanding is not None:
            scores['no_dilution'] = 1 if float(shares_outstanding) <= float(prior_shares_outstanding) else 0  # type: ignore
            total_score += scores['no_dilution']
        
        # 8. Gross margin
        if all([gross_profit, revenue, prior_gross_profit, prior_revenue]):
            margin = float(gross_profit) / float(revenue)  # type: ignore
            prior_margin = float(prior_gross_profit) / float(prior_revenue)  # type: ignore
            scores['margin_higher'] = 1 if margin > prior_margin else 0
            total_score += scores['margin_higher']
        
        # 9. Asset turnover
        if all([revenue, prior_revenue]):
            turnover = float(revenue) / total_assets  # type: ignore
            prior_turnover = float(prior_revenue) / float(prior_total_assets)  # type: ignore
            scores['turnover_higher'] = 1 if turnover > prior_turnover else 0
            total_score += scores['turnover_higher']
        
        # Interpret score
        if total_score >= 8:
            interpretation = "Strong financial position"
        elif total_score >= 5:
            interpretation = "Moderate financial position"
        else:
            interpretation = "Weak financial position"
        
        return MetricResult(
            value=total_score,
            components=scores,
            interpretation=interpretation,
            period=self._bs_period if self._bs_period is not None else ""
        )