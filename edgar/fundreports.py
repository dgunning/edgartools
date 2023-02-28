from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Union, List, Dict
from functools import lru_cache

import pandas as pd
from bs4 import Tag
from rich import box
from rich.console import Group, Text
from rich.table import Table

from edgar._rich import repr_rich, df_to_rich_table
from edgar.core import moneyfmt
from edgar._xml import find_element, child_text, optional_decimal

__all__ = [
    "FundReport",
    "CurrentMetric",
    "FUND_FORMS"
]

FUND_FORMS = ["NPORT-P", "NPORT-EX"]


@dataclass(frozen=True)
class IssuerCredentials:
    cik: str
    ccc: str  # cik confirmation code


@dataclass(frozen=True)
class SeriesClassInfo:
    series_id: str
    class_id: str

    @classmethod
    def from_xml(cls,
                 tag):
        if tag and tag.name == "seriesClassInfo":
            return cls(series_id=child_text(tag, "seriesId"),
                       class_id=child_text(tag, "classId"))


@dataclass(frozen=True)
class FilerInfo:
    issuer_credentials: IssuerCredentials
    series_class_info: SeriesClassInfo


@dataclass(frozen=True)
class Header:
    submission_type: str
    is_confidential: bool
    filer_info: FilerInfo


@dataclass(frozen=True)
class GeneralInfo:
    name: str
    cik: str
    file_number: str
    lei: str
    street1: str
    street2: str
    city: str
    state: str
    country: str
    zip_or_postal_code: str
    phone: str
    series_name: str
    series_lei: str
    series_id: str
    class_ids: List[str]
    reg_period_end: datetime
    reg_period_date: datetime
    is_final_filing: bool


@dataclass(frozen=True)
class PeriodType:
    # These elements are part of B.3.c. Credit Spread Risk (SDV01, CR01 or CS01).
    # e.g. <intrstRtRiskdv01 period3Mon="0" period1Yr="0" period5Yr="0" period10Yr="0" period30Yr="0"/>
    period3Mon: Decimal
    period1Yr: Decimal
    period5Yr: Decimal
    period10Yr: Decimal
    period30Yr: Decimal

    @classmethod
    def from_xml(cls,
                 tag: Tag = None):
        if tag:
            return cls(period1Yr=Decimal(tag.attrs.get("period1Yr")),
                       period3Mon=Decimal(tag.attrs.get("period3Mon")),
                       period5Yr=Decimal(tag.attrs.get("period5Yr")),
                       period10Yr=Decimal(tag.attrs.get("period10Yr")),
                       period30Yr=Decimal(tag.attrs.get("period30Yr"))
                       )


@dataclass(frozen=True)
class CurrentMetric:
    currency: str
    intrstRtRiskdv01: PeriodType
    intrstRtRiskdv100: PeriodType

    # See https://www.investopedia.com/terms/d/dollar-duration.asp


def decimal_or_na(value: str):
    return value if value == "N/A" else Decimal(value)


def datetime_or_na(value: str):
    return value if value == "N/A" else datetime.strptime(value, "%Y-%m-%d")


@dataclass(frozen=True)
class MonthlyTotalReturn:
    class_id: str
    return1: Decimal
    return2: Decimal
    return3: Decimal

    @classmethod
    def from_xml(cls, tag: Tag):
        return cls(
            class_id=tag.attrs.get("classId"),
            return1=decimal_or_na(tag.attrs.get("rtn1")),
            return2=decimal_or_na(tag.attrs.get("rtn2")),
            return3=decimal_or_na(tag.attrs.get("rtn3"))
        )


@dataclass(frozen=True)
class RealizedChange:
    net_realized_gain: Decimal
    net_unrealized_appreciation: Decimal

    @classmethod
    def from_xml(cls,
                 tag):
        if tag:
            return cls(
                net_realized_gain=decimal_or_na(tag.attrs.get("netRealizedGain")),
                net_unrealized_appreciation=decimal_or_na(tag.attrs.get("netUnrealizedAppr"))
            )


@dataclass(frozen=True)
class MonthlyFlow:
    redemption: Decimal
    reinvestment: Decimal
    sales: Decimal

    @classmethod
    def from_xml(cls,
                 tag):
        if tag:
            return cls(
                redemption=decimal_or_na(tag.attrs.get("redemption")),
                reinvestment=decimal_or_na(tag.attrs.get("reinvestment")),
                sales=decimal_or_na(tag.attrs.get("sales"))
            )


@dataclass(frozen=True)
class ReturnInfo:
    monthly_total_returns: List[MonthlyTotalReturn]
    other_mon1: RealizedChange
    other_mon2: RealizedChange
    other_mon3: RealizedChange


@dataclass(frozen=True)
class FundInfo:
    total_assets: Decimal
    total_liabilities: Decimal
    net_assets: Decimal
    assets_attr_misc_sec: Decimal
    assets_invested: Decimal
    amt_pay_one_yr_banks_borr: Decimal
    amt_pay_one_yr_ctrld_comp: Decimal
    amt_pay_one_yr_oth_affil: Decimal
    amt_pay_one_yr_other: Decimal
    amt_pay_aft_one_yr_banks_borr: Decimal
    amt_pay_aft_one_yr_ctrld_comp: Decimal
    amt_pay_aft_one_yr_oth_affil: Decimal
    amt_pay_aft_one_yr_other: Decimal
    delay_deliv: Decimal
    stand_by_commit: Decimal
    liquidity_pref: Decimal
    cash_not_report_in_cor_d: Decimal
    current_metrics: Dict[str, CurrentMetric]
    credit_spread_risk_investment_grade: PeriodType
    credit_spread_risk_non_investment_grade: PeriodType
    is_non_cash_collateral: bool
    return_info: ReturnInfo
    monthly_flow1: MonthlyFlow
    monthly_flow2: MonthlyFlow
    monthly_flow3: MonthlyFlow


@dataclass(frozen=True)
class DebtSecurity:
    maturity_date: datetime
    coupon_kind: str
    annualized_rate: Decimal
    is_default: bool
    are_instrument_payents_in_arrears: bool
    is_paid_kind: bool
    is_mandatory_convertible: bool
    is_continuing_convertible: bool

    @classmethod
    def from_xml(cls,
                 tag: Tag):
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


@dataclass(frozen=True)
class SecurityLending:
    is_cash_collateral: bool
    is_non_cash_collateral: bool
    is_loan_by_fund: bool

    @classmethod
    def from_xml(cls, tag):
        if tag and tag.name == "securityLending":
            return cls(
                is_cash_collateral=child_text(tag, "isCashCollateral"),
                is_non_cash_collateral=child_text(tag, "isNonCashCollateral"),
                is_loan_by_fund=child_text(tag, "isLoanByFund")
            )


@dataclass(frozen=True)
class Identifiers:
    ticker: str
    isin: str
    other: str

    @classmethod
    def from_xml(cls,
                 tag):
        if tag and tag.name == "identifiers":
            ticker_tag = tag.find("ticker")
            ticker = ticker_tag.attrs.get("value") if ticker_tag else None

            isin_tag = tag.find("isin")
            isin = isin_tag.attrs.get("value") if isin_tag else None

            other_tag = tag.find("other")
            other = {other_tag.attrs.get("otherDesc"): other_tag.attrs.get("value")} if other_tag else {}

            return cls(ticker=ticker, isin=isin, other=other)


@dataclass(frozen=True)
class InvestmentOrSecurity:
    name: str
    lei: str
    title: str
    cusip: str
    identifiers: Identifiers
    balance: Decimal
    units: str
    desc_other_units: str
    currency_code: str
    value_usd: Decimal
    pct_value: Decimal
    payoff_profile: str
    asset_category: str
    issuer_category: str
    investment_country: str
    is_restricted_security: bool
    fair_value_level: str
    debt_security: DebtSecurity
    security_lending: SecurityLending

    @property
    def ticker(self):
        return self.identifiers.ticker

    @property
    def isin(self):
        return self.identifiers.isin


class FundReport:

    def __init__(self,
                 header: Header,
                 general_info: GeneralInfo,
                 fund_info: FundInfo,
                 investments: List[InvestmentOrSecurity]):
        self.header = header
        self.general_info: GeneralInfo = general_info
        self.fund_info: FundInfo = fund_info
        self.investments = investments

    def __str__(self):
        return (f"{self.name} {self.general_info.reg_period_date} - {self.general_info.reg_period_end}"
                )

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
        return pd.DataFrame(
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

    @classmethod
    def from_xml(cls,
                 xml: Union[str, Tag]):
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
            lei=child_text(general_info_tag, "regLei"),
            street1=child_text(general_info_tag, "regStreet1"),
            street2=child_text(general_info_tag, "regStreet2"),
            city=child_text(general_info_tag, "regCity"),
            zip_or_postal_code=child_text(general_info_tag, "regZipOrPostalCode"),
            phone=child_text(general_info_tag, "regPhone"),
            state=state,
            country=country,
            series_name=child_text(general_info_tag, "seriesName"),
            series_id=child_text(general_info_tag, "seriesId"),
            class_ids=[child_text(tag) for tag in general_info_tag.find_all("class_id")],
            series_lei=child_text(general_info_tag, "seriesLei"),
            reg_period_end=child_text(general_info_tag, "repPdEnd"),
            reg_period_date=child_text(general_info_tag, "repPdDate"),
            is_final_filing=child_text(general_info_tag, "isFinalFiling")

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
            for investment_or_sec_tag in investment_or_secs_tag.find_all("invstOrSec"):
                # issuer conditional
                asset_conditional_tag = investment_or_sec_tag.find("assetConditional")
                if asset_conditional_tag:
                    asset_category = asset_conditional_tag.attrs.get("assetCat")
                else:
                    asset_category = child_text(investment_or_sec_tag, "assetCat")

                # issuer conditional
                issuer_conditional_tag = investment_or_sec_tag.find("issuerConditional")
                if issuer_conditional_tag:
                    issuer_category = issuer_conditional_tag.attrs.get("issuerCat")
                else:
                    issuer_category = child_text(investment_or_sec_tag, "issuerCat")

                    [

                    ]

                investments_or_security = InvestmentOrSecurity(
                    name=child_text(investment_or_sec_tag, "name"),
                    lei=child_text(investment_or_sec_tag, "lei"),
                    title=child_text(investment_or_sec_tag, "title"),
                    cusip=child_text(investment_or_sec_tag, "cusip"),
                    identifiers=Identifiers.from_xml(investment_or_secs_tag.find("identifiers")),
                    balance=optional_decimal(investment_or_sec_tag, "balance"),
                    units=child_text(investment_or_sec_tag, "units"),
                    desc_other_units=child_text(investment_or_sec_tag, "descOthUnits"),
                    currency_code=child_text(investment_or_sec_tag, "curCd"),
                    value_usd=optional_decimal(investment_or_sec_tag, "valUSD"),
                    pct_value=optional_decimal(investment_or_sec_tag, "pctVal"),
                    payoff_profile=child_text(investment_or_sec_tag, "payoffProfile"),
                    asset_category=asset_category,
                    issuer_category=issuer_category,
                    investment_country=child_text(investment_or_sec_tag, "invCountry"),
                    is_restricted_security=child_text(investment_or_sec_tag, "isRestrictedSec") == "Y",
                    fair_value_level=child_text(investment_or_sec_tag, "fairValLevel"),
                    debt_security=DebtSecurity.from_xml(investment_or_sec_tag.find("debtSec")),
                    security_lending=SecurityLending.from_xml(investment_or_sec_tag.find("securityLending"))
                )

                investments_or_securities.append(investments_or_security)

        fund_report = FundReport(header=header,
                                 general_info=general_info,
                                 fund_info=fund_info,
                                 investments=investments_or_securities)

        return fund_report

    @property
    def fund_summary_table(self) -> Table:
        # Financials
        financials_table = Table("Assets",
                                 "Liabilities",
                                 "Net Assets",
                                 "Investments",
                                 "Period",
                                 title="Fund Summary", title_style="bold deep_sky_blue1", box=box.SIMPLE)
        financials_table.add_row(moneyfmt(self.fund_info.total_assets, curr="$", places=0),
                                 moneyfmt(self.fund_info.total_liabilities, curr="$", places=0),
                                 moneyfmt(self.fund_info.net_assets, curr="$", places=0),
                                 f"{len(self.investments)}",
                                 f"{self.general_info.reg_period_date} - {self.general_info.reg_period_end}"
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
                                   Value=lambda df: df.value_usd.apply(moneyfmt, curr='$', places=0),
                                   Percent=lambda df: df.pct_value.apply(moneyfmt, curr='', places=1),
                                   Category=lambda df: df.issuer_category + " " + df.asset_category)
                           ).filter(['Name', 'Title', 'Cusip', 'Category', 'Value', 'Percent'])
        return df_to_rich_table(investments, title="Investments", title_style="bold deep_sky_blue1", max_rows=2000)

    def __rich__(self):
        return Group(
            Text(self.name, style="bold dark_sea_green4"),
            self.fund_summary_table,
            self.metrics_table,
            self.credit_spread_table,
            self.investments_table
        )

    def __repr__(self):
        return repr_rich(self.__rich__())
