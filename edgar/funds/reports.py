"""
Enhanced Fund reporting module with better derivative transaction handling.
"""
import logging
from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from typing import Any, Dict, List, Optional, Union

import pandas as pd
from bs4 import Tag
from pydantic import BaseModel
from rich import box
from rich.console import Group, Text
from rich.panel import Panel
from rich.table import Table

from edgar.core import get_bool
from edgar.formatting import moneyfmt
from edgar.funds import FundCompany, FundSeries
from edgar.richtools import df_to_rich_table, repr_rich
from edgar.xmltools import child_text, find_element, optional_decimal

log = logging.getLogger(__name__)

# Functions for export
__all__ = [
    'FundReport',
    'CurrentMetric',
    'NPORT_FORMS',
    'get_fund_portfolio_from_filing',
]

def optional_decimal_attr(element, attr_name):
    """Helper function to parse optional decimal attributes from XML elements"""
    if element is None:
        return None

    attr_value = element.attrs.get(attr_name)
    if not attr_value or attr_value == "N/A":
        return None

    try:
        return Decimal(attr_value)
    except (ValueError, TypeError):
        return None

# Define constants
NPORT_FORMS = ["NPORT-P", "NPORT-EX", "N-PORT", "N-PORT/A"]


class IssuerCredentials(BaseModel):
    cik: str
    ccc: str  # cik confirmation code


class SeriesClassInfo(BaseModel):
    series_id: str
    class_id: str

    @classmethod
    def from_xml(cls, tag):
        if tag and tag.name == "seriesClassInfo":
            return cls(series_id=child_text(tag, "seriesId"),
                       class_id=child_text(tag, "classId"))


class FilerInfo(BaseModel):
    issuer_credentials: IssuerCredentials
    series_class_info: Optional[SeriesClassInfo]

    @property
    def series_id(self):
        return self.series_class_info.series_id if self.series_class_info else ""

    @property
    def class_id(self):
        return self.series_class_info.class_id if self.series_class_info else ""


class Header(BaseModel):
    submission_type: str
    is_confidential: bool
    filer_info: FilerInfo


class GeneralInfo(BaseModel):
    name: str
    cik: str
    file_number: str
    reg_lei: Optional[str]
    street1: str
    street2: Optional[str]
    city: Optional[str]
    state: Optional[str]
    country: Optional[str]
    zip_or_postal_code: Optional[str]
    phone: Optional[str]
    series_name: Optional[str]
    series_lei: Optional[str]
    series_id: Optional[str]
    fiscal_year_end: Optional[str]
    rep_period_date: Optional[str]
    is_final_filing: Optional[bool]


class PeriodType(BaseModel):
    period3Mon: Decimal
    period1Yr: Decimal
    period5Yr: Decimal
    period10Yr: Decimal
    period30Yr: Decimal

    @classmethod
    def from_xml(cls, tag: Tag = None):
        if tag:
            return cls(period1Yr=Decimal(tag.attrs.get("period1Yr")),
                       period3Mon=Decimal(tag.attrs.get("period3Mon")),
                       period5Yr=Decimal(tag.attrs.get("period5Yr")),
                       period10Yr=Decimal(tag.attrs.get("period10Yr")),
                       period30Yr=Decimal(tag.attrs.get("period30Yr"))
                       )


class CurrentMetric(BaseModel):
    currency: str
    intrstRtRiskdv01: PeriodType
    intrstRtRiskdv100: PeriodType


def decimal_or_na(value: str):
    return value if value == "N/A" else Decimal(value)


def datetime_or_na(value: str):
    return value if value == "N/A" else datetime.strptime(value, "%Y-%m-%d")


def format_date(date: Union[str, datetime]) -> str:
    if isinstance(date, str):
        return date
    return date.strftime("%Y-%m-%d")


class MonthlyTotalReturn(BaseModel):
    class_id: Optional[str]
    return1: Optional[Union[Decimal, str]]
    return2: Optional[Union[Decimal, str]]
    return3: Optional[Union[Decimal, str]]

    @classmethod
    def from_xml(cls, tag: Tag):
        return cls(
            class_id=tag.attrs.get("classId"),
            return1=decimal_or_na(tag.attrs.get("rtn1")),
            return2=decimal_or_na(tag.attrs.get("rtn2")),
            return3=decimal_or_na(tag.attrs.get("rtn3"))
        )


class RealizedChange(BaseModel):
    net_realized_gain: Optional[Union[Decimal, str]]
    net_unrealized_appreciation: Optional[Union[Decimal, str]]

    @classmethod
    def from_xml(cls, tag):
        if tag:
            return cls(
                net_realized_gain=decimal_or_na(tag.attrs.get("netRealizedGain")),
                net_unrealized_appreciation=decimal_or_na(tag.attrs.get("netUnrealizedAppr"))
            )


class MonthlyFlow(BaseModel):
    redemption: Optional[Union[Decimal, str]]
    reinvestment: Optional[Union[Decimal, str]]
    sales: Optional[Union[Decimal, str]]

    @classmethod
    def from_xml(cls, tag):
        if tag:
            return cls(
                redemption=decimal_or_na(tag.attrs.get("redemption")),
                reinvestment=decimal_or_na(tag.attrs.get("reinvestment")),
                sales=decimal_or_na(tag.attrs.get("sales"))
            )


class ReturnInfo(BaseModel):
    monthly_total_returns: List[MonthlyTotalReturn]
    other_mon1: RealizedChange
    other_mon2: RealizedChange
    other_mon3: RealizedChange


class FundInfo(BaseModel):
    total_assets: Decimal
    total_liabilities: Decimal
    net_assets: Optional[Decimal]
    assets_attr_misc_sec: Optional[Decimal]
    assets_invested: Optional[Decimal]
    amt_pay_one_yr_banks_borr: Optional[Decimal]
    amt_pay_one_yr_ctrld_comp: Optional[Decimal]
    amt_pay_one_yr_oth_affil: Optional[Decimal]
    amt_pay_one_yr_other: Optional[Decimal]
    amt_pay_aft_one_yr_banks_borr: Optional[Decimal]
    amt_pay_aft_one_yr_ctrld_comp: Optional[Decimal]
    amt_pay_aft_one_yr_oth_affil: Optional[Decimal]
    amt_pay_aft_one_yr_other: Optional[Decimal]
    delay_deliv: Optional[Decimal]
    stand_by_commit: Optional[Decimal]
    liquidity_pref: Optional[Decimal]
    cash_not_report_in_cor_d: Optional[Decimal]
    current_metrics: Dict[str, CurrentMetric]
    credit_spread_risk_investment_grade: Optional[PeriodType]
    credit_spread_risk_non_investment_grade: Optional[PeriodType]
    is_non_cash_collateral: Optional[bool]
    return_info: Optional[ReturnInfo]
    monthly_flow1: Optional[MonthlyFlow]
    monthly_flow2: Optional[MonthlyFlow]
    monthly_flow3: Optional[MonthlyFlow]


class DebtSecurity(BaseModel):
    maturity_date: Union[datetime, str]
    coupon_kind: str
    annualized_rate: Optional[Decimal]
    is_default: bool
    are_instrument_payents_in_arrears: bool
    is_paid_kind: bool
    is_mandatory_convertible: bool
    is_continuing_convertible: bool

    @classmethod
    def from_xml(cls, tag: Tag):
        if tag and tag.name == "debtSec":
            return cls(
                maturity_date=datetime_or_na(child_text(tag, "maturityDt")),
                coupon_kind=child_text(tag, "couponKind"),
                annualized_rate=optional_decimal(tag, "annualizedRt"),
                is_default=child_text(tag, "isDefault") == "Y",
                are_instrument_payents_in_arrears=child_text(tag, "areIntrstPmntsInArrs") == "Y",
                is_paid_kind=child_text(tag, "isPaidKind") == "Y",
                is_mandatory_convertible=child_text(tag, "isMandatoryConvrtbl") == "Y",
                is_continuing_convertible=child_text(tag, "isContngtConvrtbl") == "Y"
            )


class SecurityLending(BaseModel):
    is_cash_collateral: Optional[str]
    is_non_cash_collateral: Optional[str]
    is_loan_by_fund: Optional[str]

    @classmethod
    def from_xml(cls, tag):
        if tag and tag.name == "securityLending":
            return cls(
                is_cash_collateral=child_text(tag, "isCashCollateral"),
                is_non_cash_collateral=child_text(tag, "isNonCashCollateral"),
                is_loan_by_fund=child_text(tag, "isLoanByFund")
            )


class Identifiers(BaseModel):
    ticker: Optional[str]
    isin: Optional[str]
    other: Dict

    @classmethod
    def from_xml(cls, tag):
        if tag and tag.name == "identifiers":
            ticker_tag = tag.find("ticker")
            ticker = ticker_tag.attrs.get("value") if ticker_tag else None

            isin_tag = tag.find("isin")
            isin = isin_tag.attrs.get("value") if isin_tag else None

            other_tag = tag.find("other")
            other = {other_tag.attrs.get("otherDesc"): other_tag.attrs.get("value")} if other_tag else {}

            return cls(ticker=ticker, isin=isin, other=other)


# Import derivative models from separate module
from edgar.funds.models.derivatives import (
    DerivativeInfo,
    ForwardDerivative,
    SwapDerivative,
    FutureDerivative,
    SwaptionDerivative,
    OptionDerivative,
)


class InvestmentOrSecurity(BaseModel):
    name: str
    lei: str
    title: str
    cusip: str
    identifiers: Identifiers
    balance: Optional[Decimal]
    units: Optional[str]
    desc_other_units: Optional[str]
    currency_code: Optional[str]
    # Currency conditional fields
    currency_conditional_code: Optional[str]
    exchange_rate: Optional[Decimal]
    value_usd: Decimal
    pct_value: Optional[Decimal]
    payoff_profile: Optional[str]
    asset_category: Optional[str]
    issuer_category: Optional[str]
    investment_country: Optional[str]
    is_restricted_security: bool
    fair_value_level: Optional[str]
    debt_security: Optional[DebtSecurity]
    security_lending: Optional[SecurityLending]
    derivative_info: Optional[DerivativeInfo]  # New field

    @property
    def ticker(self) -> Optional[str]:
        """Return resolved ticker with fallback logic"""
        result = self.ticker_resolution_info
        return result.ticker

    @property
    def ticker_resolution_info(self) -> 'TickerResolutionResult':
        """Provide full resolution metadata"""
        from edgar.funds.ticker_resolution import TickerResolutionService

        return TickerResolutionService.resolve_ticker(
            ticker=self.identifiers.ticker,
            cusip=self.cusip,
            isin=self.identifiers.isin,
            company_name=self.name
        )

    @property
    def isin(self):
        return self.identifiers.isin

    @property
    def is_derivative(self):
        """Check if this investment is a derivative"""
        return self.derivative_info is not None

    @property
    def absolute_value(self):
        """Return absolute value for sorting purposes"""
        return abs(self.value_usd) if self.value_usd else Decimal(0)

    @property
    def derivative_type(self):
        """Get the derivative type (FWD, SWP, FUT, OPT)"""
        if self.derivative_info:
            return self.derivative_info.derivative_category
        return None

    @property
    def is_credit_derivative(self):
        """Check if this is a credit derivative (CDS)"""
        return self.asset_category == "DCR"

    @property
    def is_interest_rate_derivative(self):
        """Check if this is an interest rate derivative"""
        return self.asset_category == "DIR"

    @property
    def is_commodity_derivative(self):
        """Check if this is a commodity derivative"""
        return self.asset_category == "DCO"

    @property
    def is_fx_derivative(self):
        """Check if this is a foreign exchange derivative"""
        return self.asset_category == "DFE"

    @property
    def is_equity_derivative(self):
        """Check if this is an equity derivative (including TRS)"""
        return self.asset_category == "DE"

    @property
    def derivative_subtype(self):
        """Get a descriptive derivative subtype"""
        if not self.is_derivative:
            return None

        deriv_type = self.derivative_type
        asset_cat = self.asset_category

        if deriv_type == "SWP":
            if asset_cat == "DCR":
                return "Credit Default Swap"
            elif asset_cat == "DIR":
                return "Interest Rate Swap"
            elif asset_cat == "DE":
                return "Total Return Swap (Equity)"
            else:
                return "Swap"
        elif deriv_type == "FUT":
            if asset_cat == "DCO":
                return "Commodity Future"
            elif asset_cat == "DIR":
                return "Interest Rate Future"
            else:
                return "Future"
        elif deriv_type == "FWD":
            if asset_cat == "DFE":
                return "FX Forward"
            else:
                return "Forward"
        elif deriv_type == "OPT":
            return "Option"
        else:
            return deriv_type


class FundReport:
    """
    Form N-PORT-P is a form filed with the SEC by mutual funds to report their monthly portfolio holdings to the SEC.
    """

    def __init__(self,
                 header: Header,
                 general_info: GeneralInfo,
                 fund_info: FundInfo,
                 investments: List[InvestmentOrSecurity]):
        self.header = header
        self.general_info: GeneralInfo = general_info
        self.fund_info: FundInfo = fund_info
        self.investments: List[InvestmentOrSecurity] = investments
        self.fund_company = FundCompany(cik_or_identifier=self.general_info.cik, fund_name=self.general_info.name)

    def __str__(self):
        return (f"{self.name} {self.general_info.rep_period_date} - {self.general_info.fiscal_year_end}"
                )

    def get_fund_series(self) -> FundSeries:
        return FundSeries(series_id=self.general_info.series_id,
                          name=self.general_info.series_name,
                          fund_company=self.fund_company)

    def get_ticker_for_series(self) -> Optional[str]:
        """Get the ticker that corresponds to this report's series."""
        if not self.general_info.series_id:
            return None

        from edgar.reference.tickers import get_mutual_fund_tickers
        mf_data = get_mutual_fund_tickers()
        matches = mf_data[mf_data['seriesId'] == self.general_info.series_id]

        if len(matches) == 1:
            return matches.iloc[0]['ticker']
        return None

    def matches_ticker(self, ticker: str) -> bool:
        """Check if this report's series matches the given ticker."""
        series_ticker = self.get_ticker_for_series()
        return series_ticker and series_ticker.upper() == ticker.upper()

    @property
    def reporting_period(self):
        return self.general_info.rep_period_date

    @property
    def name(self):
        return f"{self.general_info.name} - {self.general_info.series_name}"

    @property
    def has_investments(self):
        return len(self.investments) > 0

    @property
    def derivatives(self) -> List[InvestmentOrSecurity]:
        """Return only derivative investments"""
        return [inv for inv in self.investments if inv.is_derivative]

    @property
    def non_derivatives(self) -> List[InvestmentOrSecurity]:
        """Return only non-derivative investments"""
        return [inv for inv in self.investments if not inv.is_derivative]

    @lru_cache(maxsize=2)
    def investment_data(self, include_derivatives=True, include_ticker_metadata=False) -> pd.DataFrame:
        """
        Enhanced to optionally include ticker resolution information

        Args:
            include_derivatives: Whether to include derivative positions
            include_ticker_metadata: Add columns for ticker resolution method and confidence

        Returns:
            DataFrame with investment data, optionally including ticker resolution metadata
        """
        if len(self.investments) == 0:
            return pd.DataFrame(columns=['name', 'title', 'cusip', 'ticker', 'balance', 'units'])

        # Filter investments based on derivative inclusion
        investments_to_process = self.investments if include_derivatives else self.non_derivatives

        # Handle case where no investments match the filter
        if len(investments_to_process) == 0:
            return pd.DataFrame(columns=['name', 'title', 'cusip', 'ticker', 'balance', 'units', 'value_usd'])


        # Build data rows
        data = []
        for investment in investments_to_process:
            row_data = {
                "name": investment.name,
                "title": investment.title,
                "lei": investment.lei,
                "cusip": investment.cusip,
                "ticker": investment.ticker,  # Now uses resolved ticker
                "isin": investment.identifiers.isin,
                "balance": investment.balance,
                "units": investment.units,
                "desc_other_units": investment.desc_other_units,
                "value_usd": investment.value_usd,
                "pct_value": investment.pct_value,
                "payoff_profile": investment.payoff_profile,
                "asset_category": investment.asset_category,
                "issuer_category": investment.issuer_category,
                "currency_code": investment.currency_code,
                "investment_country": investment.investment_country,
                "restricted": investment.is_restricted_security,
                "is_derivative": investment.is_derivative,
                "maturity_date": investment.debt_security.maturity_date if investment.debt_security else pd.NA,
                "annualized_rate": investment.debt_security.annualized_rate if investment.debt_security else pd.NA,
                "is_default": investment.debt_security.is_default if investment.debt_security else pd.NA,
                "cash_collateral": investment.security_lending.is_cash_collateral
                if investment.security_lending else pd.NA,
                "non_cash_collateral": investment.security_lending.is_non_cash_collateral
                if investment.security_lending else pd.NA,
                # Derivative-specific fields
                "derivative_type": investment.derivative_info.derivative_category if investment.derivative_info else pd.NA,
                "notional_amount": self._get_notional_amount(investment),
                "counterparty": self._get_counterparty(investment),
            }

            # Add metadata columns if requested
            if include_ticker_metadata:
                ticker_info = investment.ticker_resolution_info
                row_data.update({
                    "ticker_resolution_method": ticker_info.method,
                    "ticker_resolution_confidence": ticker_info.confidence
                })

            data.append(row_data)

        investment_df = pd.DataFrame(data)

        # Sort by absolute value using a temporary column
        investment_df = pd.DataFrame(investment_df)
        investment_df['_sort_value'] = investment_df['value_usd'].abs()
        investment_df = investment_df.sort_values(['_sort_value', 'name', 'title'], ascending=[False, True, True]).reset_index(drop=True)
        investment_df = investment_df.drop(columns=['_sort_value'])


        return investment_df

    def securities_data(self) -> pd.DataFrame:
        """
        Return only non-derivative securities (stocks, bonds, etc.)

        This is equivalent to calling investment_data(include_derivatives=False).
        Use this method when you want to analyze only traditional securities
        without derivatives positions.

        :return: Securities data as pandas dataframe (excluding derivatives)
        """
        return self.investment_data(include_derivatives=False)

    def _get_notional_amount(self, investment: InvestmentOrSecurity) -> Optional[Decimal]:
        """Extract notional amount - check investment level first, then derivative-specific"""
        # First check if investment balance represents notional (when desc_other_units indicates it)
        if (investment.desc_other_units and 
            'notional' in investment.desc_other_units.lower() and 
            investment.balance):
            return investment.balance

        if not investment.derivative_info:
            return pd.NA

        deriv = investment.derivative_info
        if deriv.swap_derivative:
            return deriv.swap_derivative.notional_amount
        elif deriv.swaption_derivative:
            # For swaptions, notional is from the underlying swap
            if deriv.swaption_derivative.nested_swap:
                return deriv.swaption_derivative.nested_swap.notional_amount
            return pd.NA
        elif deriv.future_derivative:
            return deriv.future_derivative.notional_amount
        elif deriv.forward_derivative:
            # For forwards, use the larger absolute amount as notional
            sold = abs(deriv.forward_derivative.amount_sold) if deriv.forward_derivative.amount_sold else 0
            purchased = abs(deriv.forward_derivative.amount_purchased) if deriv.forward_derivative.amount_purchased else 0
            return max(sold, purchased) if max(sold, purchased) > 0 else pd.NA
        elif deriv.option_derivative:
            # Options themselves don't have notional amounts at the derivative level
            return pd.NA
        return pd.NA

    def _get_payoff_profile(self, investment: InvestmentOrSecurity) -> Optional[str]:
        """Extract payoff profile from any derivative type"""
        if not investment.derivative_info:
            return investment.payoff_profile  # Fallback to investment level

        deriv = investment.derivative_info
        if deriv.future_derivative:
            return deriv.future_derivative.payoff_profile
        elif deriv.swap_derivative:
            return None  # Swaps don't have payoff_profile in N-PORT
        elif deriv.option_derivative:
            return None  # Options don't have payoff_profile in N-PORT
        elif deriv.forward_derivative:
            return None  # Forwards don't have payoff_profile in N-PORT

        return investment.payoff_profile  # Fallback

    def _get_counterparty(self, investment: InvestmentOrSecurity) -> Optional[str]:
        """Extract counterparty name from any derivative type"""
        if not investment.derivative_info:
            return pd.NA

        deriv = investment.derivative_info
        if deriv.forward_derivative:
            return deriv.forward_derivative.counterparty_name
        elif deriv.swap_derivative:
            return deriv.swap_derivative.counterparty_name
        elif deriv.future_derivative:
            return deriv.future_derivative.counterparty_name
        elif deriv.option_derivative:
            return deriv.option_derivative.counterparty_name
        return pd.NA

    def _get_unrealized_pnl(self, investment: InvestmentOrSecurity) -> Optional[Decimal]:
        """Extract unrealized P&L from derivative, preferring derivative-specific fields"""
        if not investment.derivative_info:
            return investment.value_usd

        deriv = investment.derivative_info
        # Try to get unrealized appreciation from the derivative itself
        if deriv.option_derivative and deriv.option_derivative.unrealized_appreciation is not None:
            return deriv.option_derivative.unrealized_appreciation
        elif deriv.swaption_derivative and deriv.swaption_derivative.unrealized_appreciation is not None:
            return deriv.swaption_derivative.unrealized_appreciation
        elif deriv.swap_derivative and deriv.swap_derivative.unrealized_appreciation is not None:
            return deriv.swap_derivative.unrealized_appreciation
        elif deriv.forward_derivative and deriv.forward_derivative.unrealized_appreciation is not None:
            return deriv.forward_derivative.unrealized_appreciation
        elif deriv.future_derivative and deriv.future_derivative.unrealized_appreciation is not None:
            return deriv.future_derivative.unrealized_appreciation

        # Fallback to investment level
        return investment.value_usd

    def get_base_derivative_data(self, investment):
        """Get base fields that ALL derivatives should have for consistency"""
        derivative = investment.derivative_info

        return {
            # Basic investment info
            "name": investment.name,  # Added name field as requested
            "title": investment.title,
            "asset_category": investment.asset_category,
            "issuer_category": investment.issuer_category,
            "investment_country": investment.investment_country,
            "restricted": investment.is_restricted_security,  # Changed to match investment_data naming
            "fair_value_level": investment.fair_value_level,

            # Position info
            "balance": investment.balance,
            "units": investment.units,
            "pct_value": investment.pct_value,  # Changed from pct_nav to pct_value to match investment_data
            "value_usd": getattr(investment, 'value_usd', None),

            # Identifiers
            "lei": investment.lei,
            "cusip": investment.cusip,
            "ticker": investment.ticker,
            "isin": investment.isin,

            # Financial
            "currency_code": investment.currency_code,
            "exchange_rate": investment.exchange_rate,

            # Common derivative fields
            "derivative_type": derivative.derivative_category if derivative else "Unknown",  # Changed from type to derivative_type
            "subtype": investment.derivative_subtype,
            "payoff_profile": self._get_payoff_profile(investment),
            "counterparty": self._get_counterparty(investment) if derivative else None,
            "counterparty_lei": self._get_counterparty_lei(derivative) if derivative else None,
            "notional_amount": self._get_notional_amount(investment) if derivative else None,
            "currency": investment.currency_conditional_code or investment.currency_code,
            "unrealized_pnl": self._get_unrealized_pnl(investment),  # Now uses derivative-specific P&L
            "termination_date": self._get_termination_date(investment) if derivative else None,
        }

    def _get_counterparty_lei(self, derivative):
        """Get counterparty LEI from any derivative type"""
        if derivative.swap_derivative:
            return derivative.swap_derivative.counterparty_lei
        elif derivative.future_derivative:
            return derivative.future_derivative.counterparty_lei
        elif derivative.option_derivative:
            return derivative.option_derivative.counterparty_lei
        elif derivative.forward_derivative:
            return derivative.forward_derivative.counterparty_lei
        return None

    @lru_cache(maxsize=2)
    def derivatives_data(self) -> pd.DataFrame:
        """
        :return: Only derivative positions as a pandas dataframe
        """
        derivatives = [inv for inv in self.investments if inv.is_derivative]

        if len(derivatives) == 0:
            return pd.DataFrame()

        deriv_data = []
        for d in derivatives:
            # Get base derivative fields (unified across all types)
            row_data = self.get_base_derivative_data(d)

            # Add derivatives_data-specific fields
            row_data.update({
                "reference": self._get_reference(d)
            })

            deriv_data.append(row_data)

        deriv_df = pd.DataFrame(deriv_data)

        # Sort by absolute unrealized P&L
        deriv_df['abs_pnl'] = deriv_df['unrealized_pnl'].abs()
        deriv_df = deriv_df.sort_values('abs_pnl', ascending=False).drop('abs_pnl', axis=1)

        return deriv_df.reset_index(drop=True)

    def swaps_data(self) -> pd.DataFrame:
        """Return detailed swap derivatives data with directional receive/pay fields"""
        swaps = [inv for inv in self.investments 
                if inv.is_derivative and inv.derivative_info and inv.derivative_info.swap_derivative]

        if len(swaps) == 0:
            return pd.DataFrame()

        swap_data = []
        for d in swaps:
            swap = d.derivative_info.swap_derivative
            swap_data.append({
                # Basic investment info
                "name": d.name,
                "title": d.title,
                "derivative_type": "SWP",
                "subtype": d.derivative_subtype,
                "asset_category": d.asset_category,
                "issuer_category": d.issuer_category,
                "investment_country": d.investment_country,
                "restricted": d.is_restricted_security,
                "fair_value_level": d.fair_value_level,
                "payoff_profile": d.payoff_profile,
                "balance": d.balance,
                "units": d.units,
                "pct_value": d.pct_value,
                "exchange_rate": d.exchange_rate,

                # Basic swap info
                "counterparty": swap.counterparty_name,
                "counterparty_lei": swap.counterparty_lei,
                "reference_entity": swap.reference_entity_name,
                "reference_entity_isin": swap.reference_entity_isin,
                "reference_entity_ticker": swap.reference_entity_ticker,
                "swap_flag": swap.swap_flag,
                "notional_amount": swap.notional_amount,
                "currency": swap.currency,
                "termination_date": swap.termination_date,
                "upfront_payment": swap.upfront_payment,
                "payment_currency": swap.payment_currency,
                "upfront_receipt": swap.upfront_receipt,
                "receipt_currency": swap.receipt_currency,
                "unrealized_pnl": swap.unrealized_appreciation,

                # DIRECTIONAL RECEIVE LEG (what we receive)
                "fixed_rate_receive": swap.fixed_rate_receive,
                "fixed_amount_receive": swap.fixed_amount_receive,
                "fixed_currency_receive": swap.fixed_currency_receive,
                "floating_index_receive": swap.floating_index_receive,
                "floating_spread_receive": swap.floating_spread_receive,
                "floating_amount_receive": swap.floating_amount_receive,
                "floating_currency_receive": swap.floating_currency_receive,
                "floating_tenor_receive": swap.floating_tenor_receive,
                "floating_tenor_unit_receive": swap.floating_tenor_unit_receive,
                "floating_reset_date_tenor_receive": swap.floating_reset_date_tenor_receive,
                "floating_reset_date_unit_receive": swap.floating_reset_date_unit_receive,
                "other_description_receive": swap.other_description_receive,
                "other_type_receive": swap.other_type_receive,

                # DIRECTIONAL PAYMENT LEG (what we pay)
                "fixed_rate_pay": swap.fixed_rate_pay,
                "fixed_amount_pay": swap.fixed_amount_pay,
                "fixed_currency_pay": swap.fixed_currency_pay,
                "floating_index_pay": swap.floating_index_pay,
                "floating_spread_pay": swap.floating_spread_pay,
                "floating_amount_pay": swap.floating_amount_pay,
                "floating_currency_pay": swap.floating_currency_pay,
                "floating_tenor_pay": swap.floating_tenor_pay,
                "floating_tenor_unit_pay": swap.floating_tenor_unit_pay,
                "floating_reset_date_tenor_pay": swap.floating_reset_date_tenor_pay,
                "floating_reset_date_unit_pay": swap.floating_reset_date_unit_pay,
                "other_description_pay": swap.other_description_pay,
                "other_type_pay": swap.other_type_pay
            })

        return pd.DataFrame(swap_data)

    def swaptions_data(self) -> pd.DataFrame:
        """Return detailed swaptions (SWO) derivatives data with unified base fields and nested swap info"""
        swaptions = [inv for inv in self.investments 
                    if inv.is_derivative and inv.derivative_info and inv.derivative_info.swaption_derivative]

        if len(swaptions) == 0:
            return pd.DataFrame()

        swaption_data = []
        for d in swaptions:
            swo = d.derivative_info.swaption_derivative

            # Get base derivative fields (consistent across all types)
            row_data = self.get_base_derivative_data(d)

            # Add swaption-specific fields
            row_data.update({
                "put_or_call": swo.put_or_call,
                "written_or_purchased": swo.written_or_purchased,
                "share_number": swo.share_number,
                "exercise_price": swo.exercise_price,
                "exercise_price_currency": swo.exercise_price_currency,
                "expiration_date": swo.expiration_date,
                "delta": swo.delta,

                # Additional identifiers if available
                "main_internal_id": list(d.identifiers.other.values())[0] if d.identifiers and d.identifiers.other else None,
                "main_internal_id_desc": list(d.identifiers.other.keys())[0] if d.identifiers and d.identifiers.other else None,
            })

            # Add nested swap info if available
            if swo.nested_swap:
                nested = swo.nested_swap
                row_data.update({
                    "underlying_swap_counterparty": nested.counterparty_name,
                    "underlying_swap_notional": nested.notional_amount,
                    "underlying_swap_currency": nested.currency,
                    "underlying_swap_termination": nested.termination_date,

                    # Fixed rate legs
                    "underlying_swap_fixed_rate_receive": nested.fixed_rate_receive,
                    "underlying_swap_fixed_currency_receive": nested.fixed_currency_receive,
                    "underlying_swap_fixed_rate_pay": nested.fixed_rate_pay,
                    "underlying_swap_fixed_currency_pay": nested.fixed_currency_pay,

                    # Floating rate legs with detailed info
                    "underlying_swap_floating_index_receive": nested.floating_index_receive,
                    "underlying_swap_floating_currency_receive": nested.floating_currency_receive,
                    "underlying_swap_floating_spread_receive": nested.floating_spread_receive,
                    "underlying_swap_floating_tenor_receive": nested.floating_tenor_receive,
                    "underlying_swap_floating_tenor_unit_receive": nested.floating_tenor_unit_receive,

                    "underlying_swap_floating_index_pay": nested.floating_index_pay,
                    "underlying_swap_floating_currency_pay": nested.floating_currency_pay,
                    "underlying_swap_floating_spread_pay": nested.floating_spread_pay,
                    "underlying_swap_floating_tenor_pay": nested.floating_tenor_pay,
                    "underlying_swap_floating_tenor_unit_pay": nested.floating_tenor_unit_pay,

                    # Upfront payment/receipt info
                    "underlying_swap_upfront_payment": nested.upfront_payment,
                    "underlying_swap_payment_currency": nested.payment_currency,
                    "underlying_swap_upfront_receipt": nested.upfront_receipt,
                    "underlying_swap_receipt_currency": nested.receipt_currency,

                    # Additional info from derivAddlInfo if present
                    "underlying_swap_internal_id": nested.deriv_addl_identifier,
                    "underlying_swap_value_usd": nested.deriv_addl_value_usd,
                    "underlying_swap_balance": nested.deriv_addl_balance,
                    "underlying_swap_units": nested.deriv_addl_units,
                })

            swaption_data.append(row_data)

        return pd.DataFrame(swaption_data)

    def options_data(self) -> pd.DataFrame:
        """Return detailed options derivatives data with clear separation of option vs underlying data"""
        options = [inv for inv in self.investments 
                  if inv.is_derivative and inv.derivative_info and inv.derivative_info.option_derivative]

        if len(options) == 0:
            return pd.DataFrame()

        option_data = []
        for d in options:
            opt = d.derivative_info.option_derivative

            # Get base derivative fields (consistent across all types)
            row_data = self.get_base_derivative_data(d)

            # OPTION-SPECIFIC FIELDS (what the option contract itself specifies)
            row_data.update({
                # Core option contract terms
                "option_type": opt.put_or_call,
                "option_position": opt.written_or_purchased,
                "option_quantity": opt.share_number,
                "exercise_price": opt.exercise_price,
                "exercise_currency": opt.exercise_price_currency,
                "expiration_date": opt.expiration_date,
                "delta": opt.delta,

                # Reference entity (for options on stocks/bonds)
                "reference_entity": opt.reference_entity_name,
                "reference_entity_title": opt.reference_entity_title,
                "reference_entity_isin": opt.reference_entity_isin,
                "reference_entity_ticker": opt.reference_entity_ticker,
                "reference_entity_cusip": opt.reference_entity_cusip,
                "reference_entity_other_id": opt.reference_entity_other_id,

                # Index reference (for options on indices like S&P 500)
                "index_name": opt.index_name,
                "index_identifier": opt.index_identifier,
            })

            # UNDERLYING DERIVATIVE INFO (dynamic columns based on actual nested type)
            has_nested = False
            nested_type = None

            if opt.nested_forward:
                has_nested = True
                nested_type = "Forward"
                fwd = opt.nested_forward

                # Calculate primary exposure in USD equivalent
                sold_usd = abs(fwd.amount_sold) if fwd.currency_sold == 'USD' else None
                purchased_usd = abs(fwd.amount_purchased) if fwd.currency_purchased == 'USD' else None
                primary_exposure_usd = sold_usd or purchased_usd

                # Calculate exchange rate from forward amounts
                fwd_exchange_rate = None
                if (fwd.amount_sold and fwd.amount_purchased and 
                    abs(fwd.amount_sold) > 0 and abs(fwd.amount_purchased) > 0):
                    fwd_exchange_rate = abs(fwd.amount_sold) / abs(fwd.amount_purchased)

                # Add forward-specific fields (only when relevant)
                row_data.update({
                    "nested_fwd_currency_sold": fwd.currency_sold,
                    "nested_fwd_amount_sold": fwd.amount_sold,
                    "nested_fwd_currency_purchased": fwd.currency_purchased,  
                    "nested_fwd_amount_purchased": fwd.amount_purchased,
                    "nested_fwd_settlement_date": fwd.settlement_date,
                    "nested_fwd_internal_id": fwd.deriv_addl_identifier,
                    "nested_fwd_unrealized_pnl": fwd.unrealized_appreciation,
                    "nested_fwd_exchange_rate": fwd_exchange_rate,
                    "nested_fx_pair": f"{fwd.currency_sold}/{fwd.currency_purchased}" if fwd.currency_sold and fwd.currency_purchased else None,
                    "primary_exposure_usd": primary_exposure_usd,
                })

            elif opt.nested_future:
                has_nested = True
                nested_type = "Future"
                fut = opt.nested_future

                # Add future-specific fields (only when relevant)
                row_data.update({
                    "nested_fut_payoff_profile": fut.payoff_profile,
                    "nested_fut_expiration_date": fut.expiration_date,
                    "nested_fut_notional_amount": fut.notional_amount,
                    "nested_fut_currency": fut.currency,
                    "nested_fut_unrealized_pnl": fut.unrealized_appreciation,
                    "nested_fut_internal_id": fut.reference_entity_other_id,
                    "nested_fut_reference_entity": fut.reference_entity_name,
                    "primary_exposure_usd": fut.notional_amount if fut.currency == 'USD' else None,
                })

            elif opt.nested_swap:
                has_nested = True
                nested_type = "Swap"
                swp = opt.nested_swap

                # Add swap-specific fields (only when relevant)
                # NOTE: This is rare - most options on swaps should be derivCat="SWO" (swaptions)
                row_data.update({
                    "nested_swp_notional_amount": swp.notional_amount,
                    "nested_swp_currency": swp.currency,
                    "nested_swp_termination_date": swp.termination_date,
                    "nested_swp_unrealized_pnl": swp.unrealized_appreciation,
                    "nested_swp_internal_id": swp.deriv_addl_identifier,
                    "nested_swp_fixed_rate_receive": swp.fixed_rate_receive,
                    "nested_swp_fixed_rate_pay": swp.fixed_rate_pay,
                    "nested_swp_floating_index_receive": swp.floating_index_receive,
                    "nested_swp_floating_index_pay": swp.floating_index_pay,
                    "primary_exposure_usd": swp.notional_amount if swp.currency == 'USD' else None,
                })

            # Add common nested derivative fields
            row_data.update({
                "has_nested_derivative": has_nested,
                "nested_derivative_type": nested_type,
            })

            # Set primary_exposure_usd to None if not set above (for pure options)
            if "primary_exposure_usd" not in row_data:
                row_data["primary_exposure_usd"] = None
            # No else block needed - dynamic columns only created when relevant

            option_data.append(row_data)

        return pd.DataFrame(option_data)

    def forwards_data(self) -> pd.DataFrame:
        """Return detailed forward derivatives data with unified base fields"""
        forwards = [inv for inv in self.investments 
                   if inv.is_derivative and inv.derivative_info and inv.derivative_info.forward_derivative]

        if len(forwards) == 0:
            return pd.DataFrame()

        forward_data = []
        for d in forwards:
            fwd = d.derivative_info.forward_derivative

            # Get base derivative fields (consistent across all types)
            row_data = self.get_base_derivative_data(d)

            # Add forward-specific fields
            row_data.update({
                "currency_sold": fwd.currency_sold,
                "amount_sold": fwd.amount_sold,
                "currency_purchased": fwd.currency_purchased,
                "amount_purchased": fwd.amount_purchased,
                "settlement_date": fwd.settlement_date,
            })

            forward_data.append(row_data)

        return pd.DataFrame(forward_data)

    def futures_data(self) -> pd.DataFrame:
        """Return detailed futures derivatives data with unified base fields"""
        futures = [inv for inv in self.investments 
                  if inv.is_derivative and inv.derivative_info and inv.derivative_info.future_derivative]

        if len(futures) == 0:
            return pd.DataFrame()

        future_data = []
        for d in futures:
            fut = d.derivative_info.future_derivative

            # Get base derivative fields (consistent across all types)
            row_data = self.get_base_derivative_data(d)

            # Add futures-specific fields
            row_data.update({
                "reference_entity": fut.reference_entity_name,
                "reference_entity_title": fut.reference_entity_title,
                "reference_entity_cusip": fut.reference_entity_cusip,
                "reference_entity_isin": fut.reference_entity_isin,
                "reference_entity_ticker": fut.reference_entity_ticker,
                "reference_entity_other_id": fut.reference_entity_other_id,
                "reference_entity_other_id_type": fut.reference_entity_other_id_type,
                "expiration_date": fut.expiration_date,
            })

            future_data.append(row_data)

        return pd.DataFrame(future_data)

    def _get_reference(self, investment: InvestmentOrSecurity) -> str:
        """Extract reference entity/index from derivative"""
        if not investment.derivative_info:
            return investment.title

        deriv = investment.derivative_info
        if deriv.swap_derivative and deriv.swap_derivative.reference_entity_name:
            return deriv.swap_derivative.reference_entity_name
        elif deriv.future_derivative and deriv.future_derivative.reference_entity_name:
            return deriv.future_derivative.reference_entity_name
        elif deriv.option_derivative:
            opt = deriv.option_derivative
            # Prioritize index name over reference entity for options
            if opt.index_name:
                return opt.index_name
            elif opt.reference_entity_name:
                return opt.reference_entity_name
            # Fallback to ticker if available
            elif opt.reference_entity_ticker:
                return opt.reference_entity_ticker
        elif deriv.forward_derivative:
            # For FX forwards, show currency pair
            fwd = deriv.forward_derivative
            if fwd.currency_sold and fwd.currency_purchased:
                return f"{fwd.currency_sold}/{fwd.currency_purchased}"
        return investment.title

    def _get_delta(self, investment: InvestmentOrSecurity):
        """Extract delta from option derivatives"""
        if not investment.derivative_info:
            return pd.NA

        deriv = investment.derivative_info
        if deriv.option_derivative and deriv.option_derivative.delta:
            # Try to convert to decimal, return as string if it's 'XXXX' or similar
            try:
                return float(deriv.option_derivative.delta)
            except (ValueError, TypeError, AttributeError):
                return deriv.option_derivative.delta
        return pd.NA

    def _get_termination_date(self, investment: InvestmentOrSecurity) -> str:
        """Extract termination/expiration date from derivative"""
        if not investment.derivative_info:
            return "N/A"

        deriv = investment.derivative_info
        if deriv.swap_derivative:
            return deriv.swap_derivative.termination_date or "N/A"
        elif deriv.future_derivative:
            return deriv.future_derivative.expiration_date or "N/A"
        elif deriv.forward_derivative:
            return deriv.forward_derivative.settlement_date or "N/A"
        elif deriv.option_derivative:
            return deriv.option_derivative.expiration_date or "N/A"
        return "N/A"

    @classmethod
    def from_filing(cls, filing):
        xml = filing.xml()
        if not xml:
            return None
        fund_report_dict = FundReport.parse_fund_xml(xml)

        return cls(**fund_report_dict)

    @classmethod
    def parse_fund_xml(cls, xml: Union[str, Tag]) -> Dict[str, Any]:
        root = find_element(xml, "edgarSubmission")

        # Get the header
        header_el = root.find("headerData")

        filer_info_tag = header_el.find("filerInfo")

        # Filer Info
        issuer_credentials_tag = header_el.find("issuerCredentials")

        header = Header(
            submission_type=child_text(header_el, "submissionType"),
            is_confidential=child_text(header_el, "isConfidential") == "true",
            filer_info=FilerInfo(
                issuer_credentials=IssuerCredentials(
                    cik=child_text(issuer_credentials_tag, "cik"),
                    ccc=child_text(issuer_credentials_tag, "ccc")
                ),
                series_class_info=SeriesClassInfo.from_xml(filer_info_tag.find("seriesClassInfo"))
            )
        )

        # Form data
        form_data_tag = root.find("formData")

        # General info
        general_info_tag = form_data_tag.find("genInfo")
        reg_state_conditional_tag = general_info_tag.find("regStateConditional")
        if reg_state_conditional_tag:
            state = reg_state_conditional_tag.attrs.get("regState")
            country = reg_state_conditional_tag.attrs.get("regCountry")
        else:
            state = None
            country = child_text(general_info_tag, "regCountry")

        general_info = GeneralInfo(
            name=child_text(general_info_tag, "regName"),
            cik=child_text(general_info_tag, "regCik"),
            file_number=child_text(general_info_tag, "regFileNumber"),
            reg_lei=child_text(general_info_tag, "regLei"),
            street1=child_text(general_info_tag, "regStreet1"),
            street2=child_text(general_info_tag, "regStreet2"),
            city=child_text(general_info_tag, "regCity"),
            zip_or_postal_code=child_text(general_info_tag, "regZipOrPostalCode"),
            phone=child_text(general_info_tag, "regPhone"),
            state=state,
            country=country,
            series_name=child_text(general_info_tag, "seriesName"),
            series_id=child_text(general_info_tag, "seriesId"),
            series_lei=child_text(general_info_tag, "seriesLei"),
            fiscal_year_end=child_text(general_info_tag, "repPdEnd"),
            rep_period_date=child_text(general_info_tag, "repPdDate"),
            is_final_filing=get_bool(child_text(general_info_tag, "isFinalFiling"))
        )

        # Fund info
        fund_info_tag = root.find("fundInfo")
        # Current metrics
        current_metrics_tag = fund_info_tag.find("curMetrics")
        current_metrics = {}
        if current_metrics_tag:
            for curr_metric_tag in current_metrics_tag.find_all("curMetric"):
                currency = child_text(curr_metric_tag, "curCd")
                current_metrics[currency] = CurrentMetric(
                    currency=currency,
                    intrstRtRiskdv01=PeriodType.from_xml(curr_metric_tag.find("intrstRtRiskdv01")),
                    intrstRtRiskdv100=PeriodType.from_xml(curr_metric_tag.find("intrstRtRiskdv100"))
                )

        # Return Info
        return_info_tag = fund_info_tag.find("returnInfo")
        monthly_returns_tag = return_info_tag.find("monthlyTotReturns")
        return_info: ReturnInfo = ReturnInfo(
            monthly_total_returns=[
                MonthlyTotalReturn.from_xml(monthly_return_tag)
                for monthly_return_tag
                in monthly_returns_tag.find_all("monthlyTotReturn")
            ],
            other_mon1=RealizedChange.from_xml(return_info_tag.find("othMon1")),
            other_mon2=RealizedChange.from_xml(return_info_tag.find("othMon2")),
            other_mon3=RealizedChange.from_xml(return_info_tag.find("othMon3"))
        )

        fund_info = FundInfo(
            total_assets=Decimal(child_text(fund_info_tag, "totAssets")),
            total_liabilities=Decimal(child_text(fund_info_tag, "totLiabs")),
            net_assets=Decimal(child_text(fund_info_tag, "netAssets")),
            assets_attr_misc_sec=Decimal(child_text(fund_info_tag, "assetsAttrMiscSec")),
            assets_invested=Decimal(child_text(fund_info_tag, "assetsInvested")),
            amt_pay_one_yr_banks_borr=Decimal(child_text(fund_info_tag, "amtPayOneYrBanksBorr")),
            amt_pay_one_yr_ctrld_comp=Decimal(child_text(fund_info_tag, "amtPayOneYrCtrldComp")),
            amt_pay_one_yr_oth_affil=Decimal(child_text(fund_info_tag, "amtPayOneYrOthAffil")),
            amt_pay_one_yr_other=Decimal(child_text(fund_info_tag, "amtPayOneYrOther")),
            amt_pay_aft_one_yr_banks_borr=optional_decimal(fund_info_tag, "amtPayAftOneYrBanksBorr"),
            amt_pay_aft_one_yr_ctrld_comp=optional_decimal(fund_info_tag, "amtPayAftOneYrCtrldComp"),
            amt_pay_aft_one_yr_oth_affil=optional_decimal(fund_info_tag, "amtPayAftOneYrOthAffil"),
            amt_pay_aft_one_yr_other=optional_decimal(fund_info_tag, "amtPayAftOneYrOther"),
            delay_deliv=optional_decimal(fund_info_tag, "delayDeliv"),
            stand_by_commit=optional_decimal(fund_info_tag, "standByCommit"),
            liquidity_pref=optional_decimal(fund_info_tag, "liquidPref"),
            cash_not_report_in_cor_d=optional_decimal(fund_info_tag, "cshNotRptdInCorD"),
            current_metrics=current_metrics,
            credit_spread_risk_investment_grade=PeriodType.from_xml(fund_info_tag.find("creditSprdRiskInvstGrade")),
            credit_spread_risk_non_investment_grade=PeriodType.from_xml(
                fund_info_tag.find("creditSprdRiskNonInvstGrade")),
            is_non_cash_collateral=child_text(fund_info_tag, "isNonCashCollateral") == "Y",
            return_info=return_info,
            monthly_flow1=MonthlyFlow.from_xml(fund_info_tag.find("mon1Flow")),
            monthly_flow2=MonthlyFlow.from_xml(fund_info_tag.find("mon2Flow")),
            monthly_flow3=MonthlyFlow.from_xml(fund_info_tag.find("mon3Flow"))
        )

        # Investments or securities
        investments_or_securities = []
        investment_or_secs_tag = form_data_tag.find("invstOrSecs")
        if investment_or_secs_tag:
            investments_or_securities = []
            for investment_tag in investment_or_secs_tag.find_all("invstOrSec"):
                # issuer conditional
                asset_conditional_tag = investment_tag.find("assetConditional")
                if asset_conditional_tag:
                    asset_category = asset_conditional_tag.attrs.get("assetCat")
                else:
                    asset_category = child_text(investment_tag, "assetCat")

                # issuer conditional
                issuer_conditional_tag = investment_tag.find("issuerConditional")
                if issuer_conditional_tag:
                    issuer_category = issuer_conditional_tag.attrs.get("issuerCat")
                else:
                    issuer_category = child_text(investment_tag, "issuerCat")

                # currency conditional
                currency_conditional_code = None
                exchange_rate = None
                currency_conditional_tag = investment_tag.find("currencyConditional")
                if currency_conditional_tag:
                    currency_conditional_code = currency_conditional_tag.attrs.get("curCd")
                    exchange_rate = optional_decimal_attr(currency_conditional_tag, "exchangeRt")

                investments_or_security = InvestmentOrSecurity(
                    name=child_text(investment_tag, "name"),
                    lei=child_text(investment_tag, "lei"),
                    title=child_text(investment_tag, "title"),
                    cusip=child_text(investment_tag, "cusip"),
                    identifiers=Identifiers.from_xml(investment_tag.find("identifiers")),
                    balance=optional_decimal(investment_tag, "balance"),
                    units=child_text(investment_tag, "units"),
                    desc_other_units=child_text(investment_tag, "descOthUnits"),
                    currency_code=child_text(investment_tag, "curCd"),
                    currency_conditional_code=currency_conditional_code,
                    exchange_rate=exchange_rate,
                    value_usd=optional_decimal(investment_tag, "valUSD"),
                    pct_value=optional_decimal(investment_tag, "pctVal"),
                    payoff_profile=child_text(investment_tag, "payoffProfile"),
                    asset_category=asset_category,
                    issuer_category=issuer_category,
                    investment_country=child_text(investment_tag, "invCountry"),
                    is_restricted_security=child_text(investment_tag, "isRestrictedSec") == "Y",
                    fair_value_level=child_text(investment_tag, "fairValLevel"),
                    debt_security=DebtSecurity.from_xml(investment_tag.find("debtSec")),
                    security_lending=SecurityLending.from_xml(investment_tag.find("securityLending")),
                    derivative_info=DerivativeInfo.from_xml(investment_tag.find("derivativeInfo"))  # Parse derivatives
                )

                investments_or_securities.append(investments_or_security)

        # Get the fund Information from the filing header

        return {'header': header,
                'general_info': general_info,
                'fund_info': fund_info,
                'investments': investments_or_securities}

    @property
    def fund_info_table(self) -> Table:
        fund_info_table = Table("Fund", "Series", "As Of Date", "Fiscal Year", box=box.SIMPLE)
        fund_info_table.add_row(self.general_info.name,
                                f"{self.general_info.series_name} {self.general_info.series_id or ''}",
                                self.general_info.rep_period_date,
                                self.general_info.fiscal_year_end)
        return fund_info_table

    @property
    def fund_summary_table(self) -> Table:
        # Financials
        financials_table = Table("Assets",
                                 "Liabilities",
                                 "Net Assets",
                                 "Total Positions",
                                 "Derivatives",
                                 title="Financials", title_style="bold deep_sky_blue1", box=box.SIMPLE)
        financials_table.add_row(moneyfmt(self.fund_info.total_assets, curr="$", places=0),
                                 moneyfmt(self.fund_info.total_liabilities, curr="$", places=0),
                                 moneyfmt(self.fund_info.net_assets, curr="$", places=0),
                                 f"{len(self.investments)}",
                                 f"{len(self.derivatives)}"
                                 )
        return financials_table

    @property
    def metrics_table(self):
        table = Table("Metric", "Currency", "3 month", "1 year", "5 year", "10 year", "30 year",
                      title="Interest Rate Sensitivity", title_style="bold deep_sky_blue1", box=box.SIMPLE)

        for currency, current_metric in self.fund_info.current_metrics.items():
            table.add_row("Dollar Value 01",
                          currency,
                          moneyfmt(current_metric.intrstRtRiskdv01.period3Mon),
                          moneyfmt(current_metric.intrstRtRiskdv01.period1Yr),
                          moneyfmt(current_metric.intrstRtRiskdv01.period5Yr),
                          moneyfmt(current_metric.intrstRtRiskdv01.period10Yr),
                          moneyfmt(current_metric.intrstRtRiskdv01.period30Yr)
                          )
            table.add_row("Dollar Value 100",
                          currency,
                          moneyfmt(current_metric.intrstRtRiskdv100.period3Mon, ),
                          moneyfmt(current_metric.intrstRtRiskdv100.period1Yr),
                          moneyfmt(current_metric.intrstRtRiskdv100.period5Yr),
                          moneyfmt(current_metric.intrstRtRiskdv100.period10Yr),
                          moneyfmt(current_metric.intrstRtRiskdv100.period30Yr))

        return table

    @property
    def credit_spread_table(self):
        if not (
                self.fund_info.credit_spread_risk_investment_grade or
                self.fund_info.credit_spread_risk_non_investment_grade):
            return Text(" ")
        table = Table("Metric", "3 month", "1 year", "5 year", "10 year", "30 year",
                      title="Credit Spread Risk", title_style="bold deep_sky_blue1", box=box.SIMPLE)
        if self.fund_info.credit_spread_risk_investment_grade:
            table.add_row("Investment Grade",
                          moneyfmt(self.fund_info.credit_spread_risk_investment_grade.period3Mon),
                          moneyfmt(self.fund_info.credit_spread_risk_investment_grade.period1Yr),
                          moneyfmt(self.fund_info.credit_spread_risk_investment_grade.period5Yr),
                          moneyfmt(self.fund_info.credit_spread_risk_investment_grade.period10Yr),
                          moneyfmt(self.fund_info.credit_spread_risk_investment_grade.period30Yr))
        if self.fund_info.credit_spread_risk_non_investment_grade:
            table.add_row("Non Investment Grade",
                          moneyfmt(self.fund_info.credit_spread_risk_non_investment_grade.period3Mon),
                          moneyfmt(self.fund_info.credit_spread_risk_non_investment_grade.period1Yr),
                          moneyfmt(self.fund_info.credit_spread_risk_non_investment_grade.period5Yr),
                          moneyfmt(self.fund_info.credit_spread_risk_non_investment_grade.period10Yr),
                          moneyfmt(self.fund_info.credit_spread_risk_non_investment_grade.period30Yr))
        return table

    @property
    @lru_cache(maxsize=2)
    def investments_table(self):
        investments = self.investment_data(include_derivatives=False)
        if not investments.empty:
            investments = (investments
                           .assign(Name=lambda df: df.name,
                                   Title=lambda df: df.title,
                                   Cusip=lambda df: df.cusip,
                                   Ticker=lambda df: df.ticker,
                                   Value=lambda df: df.value_usd.apply(moneyfmt, curr='$', places=0),
                                   Pct=lambda df: df.pct_value.apply(moneyfmt, curr='', places=1),
                                   Category=lambda df: df.issuer_category + " " + df.asset_category)
                           ).filter(['Name', 'Title', 'Cusip', 'Ticker', 'Category', 'Value', 'Pct'])
        return df_to_rich_table(investments, title="Non-Derivative Investments", title_style="bold deep_sky_blue1", max_rows=2000)

    @property
    @lru_cache(maxsize=2)
    def derivatives_table(self):
        def safe_moneyfmt(value, **kwargs):
            """Apply moneyfmt safely, handling NaN/NA values"""
            if pd.isna(value):
                return "N/A"
            return moneyfmt(value, **kwargs)

        derivatives = self.derivatives_data()
        if not derivatives.empty:
            derivatives = derivatives.assign(
                Title=lambda df: df.title,
                Subtype=lambda df: df.subtype,
                Reference=lambda df: df.reference,
                Counterparty=lambda df: df.counterparty,
                Notional=lambda df: df.notional_amount.apply(safe_moneyfmt, curr='$', places=0),
                **{
                    'Unrealized P&L': lambda df: df.unrealized_pnl.apply(safe_moneyfmt, curr='$', places=0),
                    '% NAV': lambda df: df.pct_value.apply(safe_moneyfmt, curr='', places=2),
                    'Term/Exp Date': lambda df: df.termination_date
                }
            ).filter(['Title', 'Subtype', 'Reference', 'Counterparty', 'Notional', 'Unrealized P&L', '% NAV', 'Term/Exp Date'])
        return df_to_rich_table(derivatives, title="Derivative Positions", title_style="bold deep_sky_blue1", max_rows=2000)

    def __rich__(self):
        title = f"{self.general_info.name} - {self.general_info.series_name} {self.general_info.rep_period_date}"

        tables_to_show = [
            self.fund_summary_table,
            self.metrics_table,
            self.credit_spread_table,
            self.investments_table
        ]

        # Only add derivatives table if there are derivatives
        if len(self.derivatives) > 0:
            tables_to_show.append(self.derivatives_table)

        return Panel(Group(*tables_to_show), title=title, subtitle=title)

    def __repr__(self):
        return repr_rich(self.__rich__())


def get_fund_portfolio_from_filing(filing) -> pd.DataFrame:
    """
    Extract portfolio holdings from an NPORT filing.

    Args:
        filing: The NPORT filing to extract data from

    Returns:
        DataFrame containing portfolio holdings
    """
    try:
        # Create a FundReport from the filing
        fund_report = FundReport.from_filing(filing)
        if fund_report and hasattr(fund_report, 'investment_data'):
            return fund_report.investment_data()
    except Exception as e:
        log.warning("Error extracting portfolio from NPORT filing: %s", e)

    # Return empty DataFrame if extraction failed
    return pd.DataFrame()


