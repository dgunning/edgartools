from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import List, Optional

from pydantic import BaseModel, ConfigDict
from rich import box
from rich.console import Group
from rich.table import Column, Table

from edgar._party import Address
from edgar.entity import Company
from edgar.reference import states
from edgar.richtools import repr_rich

from edgar.offerings.crowdfunding.formc.helpers import split_list


class FilerInformation(BaseModel):
    model_config = ConfigDict(frozen=True)

    cik: str
    ccc: Optional[str] = None  # Filer CCC; redacted to XXXXXXXX in disseminated filings
    confirming_copy_flag: bool
    return_copy_flag: bool
    override_internet_flag: bool
    live_or_test: bool
    period: Optional[date] = None

    @property
    def company(self):
        return Company(self.cik)


class FundingPortal(BaseModel):
    """The intermediary the company is using to raise funds"""

    name: str
    cik: str
    crd: Optional[str] = None
    file_number: str


class IssuerInformation(BaseModel):
    name: str
    address: Address
    website: str
    co_issuer: bool
    funding_portal: Optional[FundingPortal] = None
    legal_status: str
    jurisdiction: str
    date_of_incorporation: date

    @property
    def incorporated(self):
        return f"{self.date_of_incorporation or ''} {self.jurisdiction or ''}"


class OfferingInformation(BaseModel):
    """
       <offeringInformation>
      <compensationAmount>A fee equal of 3% in cash of the aggregate amount raised by the Company, payable at each closing of the Offering.</compensationAmount>
      <financialInterest>No</financialInterest>
      <securityOfferedType>Other</securityOfferedType>
      <securityOfferedOtherDesc>Membership Interests</securityOfferedOtherDesc>
      <noOfSecurityOffered>41666</noOfSecurityOffered>
      <price>1.20000</price>
      <priceDeterminationMethod>Determined arbitrarily by the issuer</priceDeterminationMethod>
      <offeringAmount>50000.00</offeringAmount>
      <overSubscriptionAccepted>Y</overSubscriptionAccepted>
      <overSubscriptionAllocationType>First-come, first-served basis</overSubscriptionAllocationType>
      <descOverSubscription>At issuer's discretion, with priority given to StartEngine Owners</descOverSubscription>
      <maximumOfferingAmount>950000.00</maximumOfferingAmount>
      <deadlineDate>12-31-2024</deadlineDate>
    </offeringInformation>
    """
    compensation_amount: str
    financial_interest: Optional[str] = None
    security_offered_type: Optional[str] = None
    security_offered_other_desc: Optional[str] = None
    no_of_security_offered: Optional[str] = None
    price: Optional[str] = None
    price_determination_method: Optional[str] = None
    offering_amount: Optional[float] = None
    over_subscription_accepted: Optional[str] = None
    over_subscription_allocation_type: Optional[str] = None
    desc_over_subscription: Optional[str] = None
    maximum_offering_amount: Optional[float] = None
    deadline_date: Optional[date] = None

    @property
    def security_description(self) -> str:
        """Combined security type and description for easier access"""
        if not self.security_offered_type:
            return "Not specified"
        sec_type = self.security_offered_type
        if self.security_offered_other_desc:
            return f"{sec_type} ({self.security_offered_other_desc})"
        return sec_type

    @property
    def target_amount(self) -> Optional[float]:
        """Alias for offering_amount - more intuitive name"""
        return self.offering_amount

    @property
    def price_per_security(self) -> Optional[float]:
        """Parse price string to float"""
        if not self.price:
            return None
        try:
            return float(self.price)
        except (ValueError, TypeError):
            return None

    @property
    def number_of_securities(self) -> Optional[int]:
        """Parse no_of_security_offered string to int"""
        if not self.no_of_security_offered:
            return None
        try:
            return int(float(self.no_of_security_offered))
        except (ValueError, TypeError):
            return None

    @property
    def percent_to_maximum(self) -> Optional[float]:
        """Calculate target as percentage of maximum offering amount"""
        if not self.offering_amount or not self.maximum_offering_amount:
            return None
        if self.maximum_offering_amount == 0:
            return None
        return (self.offering_amount / self.maximum_offering_amount) * 100

    @property
    def target_offering_amount(self) -> Optional[float]:
        """Alias for offering_amount - explicit name"""
        return self.offering_amount

    @property
    def offering_deadline(self) -> Optional[date]:
        """Alias for deadline_date - more intuitive name"""
        return self.deadline_date


class AnnualReportDisclosure(BaseModel):
    """
    <annualReportDisclosureRequirements>
      <currentEmployees>0.00</currentEmployees>
      <totalAssetMostRecentFiscalYear>0.00</totalAssetMostRecentFiscalYear>
      <totalAssetPriorFiscalYear>0.00</totalAssetPriorFiscalYear>
      <cashEquiMostRecentFiscalYear>0.00</cashEquiMostRecentFiscalYear>
      <cashEquiPriorFiscalYear>0.00</cashEquiPriorFiscalYear>
      <actReceivedMostRecentFiscalYear>0.00</actReceivedMostRecentFiscalYear>
      <actReceivedPriorFiscalYear>0.00</actReceivedPriorFiscalYear>
      <shortTermDebtMostRecentFiscalYear>0.00</shortTermDebtMostRecentFiscalYear>
      <shortTermDebtPriorFiscalYear>0.00</shortTermDebtPriorFiscalYear>
      <longTermDebtMostRecentFiscalYear>0.00</longTermDebtMostRecentFiscalYear>
      <longTermDebtPriorFiscalYear>0.00</longTermDebtPriorFiscalYear>
      <revenueMostRecentFiscalYear>0.00</revenueMostRecentFiscalYear>
      <revenuePriorFiscalYear>0.00</revenuePriorFiscalYear>
      <costGoodsSoldMostRecentFiscalYear>0.00</costGoodsSoldMostRecentFiscalYear>
      <costGoodsSoldPriorFiscalYear>0.00</costGoodsSoldPriorFiscalYear>
      <taxPaidMostRecentFiscalYear>0.00</taxPaidMostRecentFiscalYear>
      <taxPaidPriorFiscalYear>0.00</taxPaidPriorFiscalYear>
      <netIncomeMostRecentFiscalYear>0.00</netIncomeMostRecentFiscalYear>
      <netIncomePriorFiscalYear>0.00</netIncomePriorFiscalYear>
      </annualReportDisclosureRequirements>
    """
    current_employees: int
    total_asset_most_recent_fiscal_year: float
    total_asset_prior_fiscal_year: float
    cash_equi_most_recent_fiscal_year: float
    cash_equi_prior_fiscal_year: float
    act_received_most_recent_fiscal_year: float
    act_received_prior_fiscal_year: float
    short_term_debt_most_recent_fiscal_year: float
    short_term_debt_prior_fiscal_year: float
    long_term_debt_most_recent_fiscal_year: float
    long_term_debt_prior_fiscal_year: float
    revenue_most_recent_fiscal_year: float
    revenue_prior_fiscal_year: float
    cost_goods_sold_most_recent_fiscal_year: float
    cost_goods_sold_prior_fiscal_year: float
    tax_paid_most_recent_fiscal_year: float
    tax_paid_prior_fiscal_year: float
    net_income_most_recent_fiscal_year: float
    net_income_prior_fiscal_year: float

    offering_jurisdictions: List[str]

    @property
    def is_offered_in_all_states(self):
        return set(self.offering_jurisdictions).issuperset(states.keys())

    @property
    def total_debt_most_recent(self) -> float:
        """Total debt (short-term + long-term) for most recent fiscal year"""
        return self.short_term_debt_most_recent_fiscal_year + self.long_term_debt_most_recent_fiscal_year

    @property
    def total_debt_prior(self) -> float:
        """Total debt (short-term + long-term) for prior fiscal year"""
        return self.short_term_debt_prior_fiscal_year + self.long_term_debt_prior_fiscal_year

    @property
    def debt_to_asset_ratio(self) -> Optional[float]:
        """Debt-to-asset ratio as percentage for most recent fiscal year"""
        if self.total_asset_most_recent_fiscal_year == 0:
            return None
        return (self.total_debt_most_recent / self.total_asset_most_recent_fiscal_year) * 100

    @property
    def revenue_growth_yoy(self) -> Optional[float]:
        """Year-over-year revenue growth as percentage"""
        if self.revenue_prior_fiscal_year == 0:
            return None
        return ((self.revenue_most_recent_fiscal_year - self.revenue_prior_fiscal_year) /
                self.revenue_prior_fiscal_year) * 100

    @property
    def is_pre_revenue(self) -> bool:
        """True if company has no revenue in most recent fiscal year"""
        return self.revenue_most_recent_fiscal_year == 0

    @property
    def burn_rate_change(self) -> Optional[float]:
        """Change in net income (negative values indicate increased burn)"""
        return self.net_income_most_recent_fiscal_year - self.net_income_prior_fiscal_year

    @property
    def asset_growth_yoy(self) -> Optional[float]:
        """Year-over-year asset growth as percentage"""
        if self.total_asset_prior_fiscal_year == 0:
            return None
        return ((self.total_asset_most_recent_fiscal_year - self.total_asset_prior_fiscal_year) /
                self.total_asset_prior_fiscal_year) * 100

    # Convenience aliases for most recent fiscal year (simpler access)
    @property
    def total_assets(self) -> float:
        """Alias for total_asset_most_recent_fiscal_year"""
        return self.total_asset_most_recent_fiscal_year

    @property
    def cash_and_cash_equivalents(self) -> float:
        """Alias for cash_equi_most_recent_fiscal_year"""
        return self.cash_equi_most_recent_fiscal_year

    @property
    def accounts_receivable(self) -> float:
        """Alias for act_received_most_recent_fiscal_year"""
        return self.act_received_most_recent_fiscal_year

    @property
    def short_term_debt(self) -> float:
        """Alias for short_term_debt_most_recent_fiscal_year"""
        return self.short_term_debt_most_recent_fiscal_year

    @property
    def long_term_debt(self) -> float:
        """Alias for long_term_debt_most_recent_fiscal_year"""
        return self.long_term_debt_most_recent_fiscal_year

    @property
    def revenues(self) -> float:
        """Alias for revenue_most_recent_fiscal_year"""
        return self.revenue_most_recent_fiscal_year

    @property
    def cost_of_goods_sold(self) -> float:
        """Alias for cost_goods_sold_most_recent_fiscal_year"""
        return self.cost_goods_sold_most_recent_fiscal_year

    @property
    def taxes_paid(self) -> float:
        """Alias for tax_paid_most_recent_fiscal_year"""
        return self.tax_paid_most_recent_fiscal_year

    @property
    def net_income(self) -> float:
        """Alias for net_income_most_recent_fiscal_year"""
        return self.net_income_most_recent_fiscal_year

    @property
    def number_of_employees(self) -> int:
        """Alias for current_employees"""
        return self.current_employees

    def __rich__(self):
        annual_report_table = Table(Column("", style='bold'), Column("Current Fiscal Year", style="bold"),
                                    Column("Previous Fiscal Year"),
                                    box=box.SIMPLE, row_styles=["", "bold"])
        annual_report_table.add_row("Current Employees", f"{self.current_employees:,.0f}", "")
        annual_report_table.add_row("Total Asset", f"${self.total_asset_most_recent_fiscal_year:,.2f}",
                                    f"${self.total_asset_prior_fiscal_year:,.2f}")
        annual_report_table.add_row("Cash Equivalent", f"${self.cash_equi_most_recent_fiscal_year:,.2f}",
                                    f"${self.cash_equi_prior_fiscal_year:,.2f}")
        annual_report_table.add_row("Accounts Receivable", f"${self.act_received_most_recent_fiscal_year:,.2f}",
                                    f"${self.act_received_prior_fiscal_year:,.2f}")
        annual_report_table.add_row("Short Term Debt", f"${self.short_term_debt_most_recent_fiscal_year:,.2f}",
                                    f"${self.short_term_debt_prior_fiscal_year:,.2f}")
        annual_report_table.add_row("Long Term Debt", f"${self.long_term_debt_most_recent_fiscal_year:,.2f}",
                                    f"${self.long_term_debt_prior_fiscal_year:,.2f}")
        annual_report_table.add_row("Revenue", f"${self.revenue_most_recent_fiscal_year:,.2f}",
                                    f"${self.revenue_prior_fiscal_year:,.2f}")
        annual_report_table.add_row("Cost of Goods Sold", f"${self.cost_goods_sold_most_recent_fiscal_year:,.2f}",
                                    f"${self.cost_goods_sold_prior_fiscal_year:,.2f}")
        annual_report_table.add_row("Tax Paid", f"${self.tax_paid_most_recent_fiscal_year:,.2f}",
                                    f"${self.tax_paid_prior_fiscal_year:,.2f}")
        annual_report_table.add_row("Net Income", f"${self.net_income_most_recent_fiscal_year:,.2f}",
                                    f"${self.net_income_prior_fiscal_year:,.2f}")

        # Jurisdictions
        jurisdiction_table = Table(Column("Offered In", style="bold"), box=box.SIMPLE, row_styles=["", "bold"])
        if self.is_offered_in_all_states:
            juris_description = "All 50 States"
            jurisdiction_table.add_row(juris_description)
        else:
            jurisdiction_lists = split_list(self.offering_jurisdictions, chunk_size=25)
            for _index, jurisdictions in enumerate(jurisdiction_lists):
                jurisdiction_table.add_row(", ".join(jurisdictions))
        return Group(annual_report_table, jurisdiction_table)

    def __repr__(self):
        return repr_rich(self.__rich__())


class PersonSignature(BaseModel):
    signature: str
    title: str
    date: date


class IssuerSignature(BaseModel):
    issuer: str
    title: str
    signature: str


class Signer(BaseModel):
    name: str
    titles: List[str]


class SignatureInfo(BaseModel):
    issuer_signature: IssuerSignature
    signatures: List[PersonSignature]

    @property
    def signers(self) -> List[Signer]:
        signer_dict = defaultdict(list)
        for signature in self.signatures:
            signer_dict[signature.signature].append(signature.title)
        signer_dict[self.issuer_signature.signature].append(self.issuer_signature.title)
        return [Signer(name=name, titles=list(set(titles))) for name, titles in signer_dict.items()]
