"""
Fund reporting module for NPORT and other fund reports.

This module provides classes and functions for working with fund reports like N-PORT.
"""
import logging
from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from typing import Union, List, Dict, Any, Optional

import pandas as pd
from bs4 import Tag
from pydantic import BaseModel
from rich import box
from rich.console import Group, Text
from rich.panel import Panel
from rich.table import Table

from edgar.core import get_bool
from edgar.formatting import moneyfmt
from edgar.funds import FundSeries, FundCompany
from edgar.reference import cusip_ticker_mapping
from edgar.richtools import repr_rich, df_to_rich_table
from edgar.xmltools import find_element, child_text, optional_decimal

log = logging.getLogger(__name__)

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
    # These elements are part of B.3.c. Credit Spread Risk (SDV01, CR01 or CS01).
    # e.g. <intrstRtRiskdv01 period3Mon="0" period1Yr="0" period5Yr="0" period10Yr="0" period30Yr="0"/>
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

    @property
    def ticker(self):
        return self.identifiers.ticker

    @property
    def isin(self):
        return self.identifiers.isin


class FundReport:
    """
    Form N-PORT-P is a form filed with the SEC by mutual funds to report their monthly portfolio holdings to the SEC.
    """

    def __init__(self,
                 header: Header,
                 general_info: GeneralInfo,
                 fund_info: FundInfo,
                 investments: List[InvestmentOrSecurity],
                 series_and_contracts: 'FundSeriesAndContracts' = None):
        self.header = header
        self.general_info: GeneralInfo = general_info
        self.fund_info: FundInfo = fund_info
        self.investments: List[InvestmentOrSecurity] = investments
        self.series_and_contracts: 'FundSeriesAndContracts' = series_and_contracts
        self.fund_company = FundCompany(cik_or_identifier=self.general_info.cik, fund_name=self.general_info.name)

    def __str__(self):
        return (f"{self.name} {self.general_info.rep_period_date} - {self.general_info.fiscal_year_end}"
                )

    def get_fund_series(self) -> FundSeries:
        return FundSeries(series_id=self.general_info.series_id,
                          name=self.general_info.series_name,
                          fund_company=self.fund_company)
    @property
    def reporting_period(self):
        return self.general_info.rep_period_date

    @property
    def name(self):
        return f"{self.general_info.name} - {self.general_info.series_name}"

    @property
    def has_investments(self):
        return len(self.investments) > 0

    @lru_cache(maxsize=2)
    def investment_data(self) -> pd.DataFrame:
        """
        :return: The investments as a pandas dataframe
        """
        if len(self.investments) == 0:
            return pd.DataFrame(columns=['name', 'title', 'cusip', 'ticker', 'balance', 'units'])

        # This is for adding Ticker to the investments in case it is None
        cusip_mapping = cusip_ticker_mapping(allow_duplicate_cusips=False)

        investment_df = pd.DataFrame(
            [{
                "name": investment.name,
                "title": investment.title,
                "lei": investment.lei,
                "cusip": investment.cusip,
                "ticker": investment.identifiers.ticker,
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
                "maturity_date": investment.debt_security.maturity_date if investment.debt_security else pd.NA,
                "annualized_rate": investment.debt_security.annualized_rate if investment.debt_security else pd.NA,
                "is_default": investment.debt_security.is_default if investment.debt_security else pd.NA,
                "cash_collateral": investment.security_lending.is_cash_collateral
                if investment.security_lending else pd.NA,
                "non_cash_collateral": investment.security_lending.is_non_cash_collateral
                if investment.security_lending else pd.NA
            }
                for investment in self.investments
            ]
        ).sort_values(['value_usd', 'name', 'title'], ascending=[False, True, True]).reset_index(drop=True)

        # Step 1: Map CUSIP to Ticker using the cusip_mapping
        mapped_tickers = investment_df.cusip.map(cusip_mapping.Ticker)

        # Step 2: Fill NaN values in the ticker column with mapped tickers
        investment_df['ticker'] = investment_df['ticker'].astype(str).fillna(mapped_tickers).fillna("")

        return investment_df

    @classmethod
    def from_filing(cls, filing):
        xml = filing.xml()
        if not xml:
            return None
        fund_report_dict = FundReport.parse_fund_xml(xml)

        # Parse ticker, fund, series information from the filing header
        # Import here to avoid circular imports
        from edgar.funds import get_fund_information
        fund_report_dict['series_and_contracts'] = get_fund_information(filing.header)

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
                    value_usd=optional_decimal(investment_tag, "valUSD"),
                    pct_value=optional_decimal(investment_tag, "pctVal"),
                    payoff_profile=child_text(investment_tag, "payoffProfile"),
                    asset_category=asset_category,
                    issuer_category=issuer_category,
                    investment_country=child_text(investment_tag, "invCountry"),
                    is_restricted_security=child_text(investment_tag, "isRestrictedSec") == "Y",
                    fair_value_level=child_text(investment_tag, "fairValLevel"),
                    debt_security=DebtSecurity.from_xml(investment_tag.find("debtSec")),
                    security_lending=SecurityLending.from_xml(investment_tag.find("securityLending"))
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
                                 "Investments",
                                 title="Financials", title_style="bold deep_sky_blue1", box=box.SIMPLE)
        financials_table.add_row(moneyfmt(self.fund_info.total_assets, curr="$", places=0),
                                 moneyfmt(self.fund_info.total_liabilities, curr="$", places=0),
                                 moneyfmt(self.fund_info.net_assets, curr="$", places=0),
                                 f"{len(self.investments)}"
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
        investments = self.investment_data()
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
        return df_to_rich_table(investments, title="Investments", title_style="bold deep_sky_blue1", max_rows=2000)

    def __rich__(self):
        title = f"{self.general_info.name} - {self.general_info.series_name} {self.general_info.rep_period_date}"
        return Panel(Group(
            self.fund_summary_table,
            self.metrics_table,
            self.credit_spread_table,
            self.investments_table
        ), title=title, subtitle=title
        )

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
        log.warning(f"Error extracting portfolio from NPORT filing: {e}")

    # Return empty DataFrame if extraction failed
    return pd.DataFrame()


# Functions for export
__all__ = [
    'FundReport',
    'CurrentMetric',
    'NPORT_FORMS',
    'get_fund_portfolio_from_filing',
]
