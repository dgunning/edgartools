from collections import defaultdict
from datetime import date, datetime
from functools import lru_cache, cached_property
from typing import List, Optional, Dict

from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict
from rich import box
from rich.columns import Columns
from rich.console import Group, Text
from rich.panel import Panel
from rich.table import Column, Table

from edgar._party import Address
from edgar.core import get_bool
from edgar.entity import Company
from edgar.formatting import yes_no
from edgar.reference import states
from edgar.richtools import repr_rich, Docs
from edgar.xmltools import child_text

__all__ = ['FormC', 'Signer', 'FundingPortal', 'IssuerCompany']


class FilerInformation(BaseModel):
    model_config = ConfigDict(frozen=True)

    cik: str
    ccc: str
    confirming_copy_flag: bool
    return_copy_flag: bool
    override_internet_flag: bool
    live_or_test: bool
    period: Optional[date] = None

    @property
    @lru_cache(maxsize=1)
    def company(self):
        return Company(self.cik)


class FundingPortal(BaseModel):
    """The intermediary the company is using to raise funds"""

    name: str
    cik: str
    crd: Optional[str]
    file_number: str


class IssuerInformation(BaseModel):
    name: str
    address: Address
    website: str
    co_issuer: bool
    funding_portal: Optional[FundingPortal]
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
    financial_interest: Optional[str]
    security_offered_type: Optional[str]
    security_offered_other_desc: Optional[str]
    no_of_security_offered: Optional[str]
    price: Optional[str]
    price_determination_method: Optional[str]
    offering_amount: Optional[float]
    over_subscription_accepted: Optional[str]
    over_subscription_allocation_type: Optional[str]
    desc_over_subscription: Optional[str]
    maximum_offering_amount: Optional[float]
    deadline_date: Optional[date]

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


def split_list(states, chunk_size=10):
    # Split a list into sublist of size chunk_size
    return [states[i:i + chunk_size] for i in range(0, len(states), chunk_size)]


def maybe_float(value):
    if not value:
        return 0.00
    try:
        return float(value)
    except ValueError:
        return 0.00


def maybe_date(value):
    if not value:
        return None
    try:
        return FormC.parse_date(value)
    except ValueError:
        return None


def group_offerings_by_file_number(filings) -> Dict[str, 'EntityFilings']:
    """
    Group Form C filings by issuer file number.

    This utility efficiently groups crowdfunding filings using PyArrow operations,
    which is particularly useful for companies with many offerings. Each group
    represents one complete offering lifecycle (initial C, amendments, updates, etc.).

    Args:
        filings: EntityFilings containing Form C variant filings

    Returns:
        Dictionary mapping file numbers (020-XXXXX) to EntityFilings for that offering

    Example:
        >>> company = Company('1881570')  # ViiT Health
        >>> all_filings = company.get_filings(form=['C', 'C/A', 'C-U', 'C-AR'])
        >>> grouped = group_offerings_by_file_number(all_filings)
        >>> for file_num, offering_filings in grouped.items():
        ...     print(f"{file_num}: {len(offering_filings)} filings")
        020-28927: 1 filings
        020-32444: 3 filings
        020-36002: 4 filings

    Note:
        Uses PyArrow for efficient grouping. For small filing sets, a simple loop
        may be clearer, but this approach scales better for companies with many filings.
    """
    # Use PyArrow to get unique file numbers efficiently
    unique_file_numbers = filings.data['fileNumber'].unique()

    # Create grouped dictionary using filter
    return {
        str(fn): filings.filter(file_number=str(fn))
        for fn in unique_file_numbers.to_pylist()
    }


class IssuerCompany:
    """
    Represents the company issuing a crowdfunding offering (Regulation CF).

    This class provides offering-specific methods for companies that have
    filed Form C crowdfunding offerings. It wraps basic company information
    and provides convenient access to offerings and related data.

    Attributes:
        cik: The company's CIK number
        name: The company's legal name from Form C

    Example:
        >>> formc = filing.obj()
        >>> issuer = formc.get_issuer_company()
        >>> offerings = issuer.get_offerings()
        >>> print(issuer.name, len(offerings), "offerings")
    """

    def __init__(self, cik: str, name: str):
        """
        Initialize an IssuerCompany.

        Args:
            cik: The company's CIK number (as string)
            name: The company's legal name
        """
        self.cik = cik
        self.name = name
        self._company = None

    def as_company(self) -> Company:
        """
        Convert to a full Company object with complete entity data.

        Returns:
            Company object for this issuer

        Example:
            >>> issuer = formc.get_issuer_company()
            >>> company = issuer.as_company()
            >>> print(company.tickers)  # Full company data available
        """
        if self._company is None:
            self._company = Company(self.cik)
        return self._company

    def get_offerings(self):
        """
        Get all crowdfunding offerings (Form C filings) by this company.

        Returns:
            EntityFilings containing all Form C variant filings

        Example:
            >>> issuer = formc.get_issuer_company()
            >>> offerings = issuer.get_offerings()
            >>> for filing in offerings:
            ...     print(filing.form, filing.filing_date)
        """
        from edgar.offerings import Offering
        company = self.as_company()
        filings = company.get_filings(form=['C', 'C/A', 'C-U', 'C-U/A', 'C-AR', 'C-AR/A', 'C-TR'])
        grouped_filings = group_offerings_by_file_number(filings)
        offerings: List[Offering] = []
        for file_num, _ in grouped_filings.items():
            offerings.append(Offering(file_num, cik=str(company.cik)))
        return offerings

    def latest_offering(self)->'Offering':
        """
        Get the most recent Form C offering (excludes amendments and reports).

        Returns:
            Latest Form C filing or None if no offerings found

        Example:
            >>> issuer = formc.get_issuer_company()
            >>> latest = issuer.latest_offering()
            >>> if latest:
            ...     offering = latest.obj().get_offering(latest)
        """
        offerings = self.get_offerings()
        if len(offerings) >0:
            return offerings[0]


    def __str__(self):
        return f"IssuerCompany({self.name} [{self.cik}])"

    def __repr__(self):
        return self.__str__()


class FormC:

    def __init__(self,
                 filer_information: FilerInformation,
                 issuer_information: IssuerInformation,
                 offering_information: Optional[OfferingInformation],
                 annual_report_disclosure: Optional[AnnualReportDisclosure],
                 signature_info: SignatureInfo,
                 form: str):
        self.filer_information: FilerInformation = filer_information
        self.issuer_information: IssuerInformation = issuer_information
        self.offering_information: OfferingInformation = offering_information
        self.annual_report_disclosure: Optional[AnnualReportDisclosure] = annual_report_disclosure
        self.signature_info: SignatureInfo = signature_info
        self.form = form
        self._filing:'Filing' = None

    @property
    def description(self):
        desc = ""
        if self.form == "C":
            desc = "Form C - Offering"
        elif self.form == "C/A":
            desc = "Form C/A - Offering Amendment"
        elif self.form == "C-U":
            desc = "Form C-U - Offering Progress Update"
        elif self.form == "C-U/A":
            desc = "Form C-U/A - Offering Progress Update Amendment"
        elif self.form == "C-AR":
            desc = "Form C-AR - Offering Annual Report"
        elif self.form == "C-AR/A":
            desc = "Form C-AR/A - Offering Annual Report Amendment"
        elif self.form == "C-TR":
            desc = "Form C-TR - Offering Termination Report"
        return desc

    @property
    def portal_file_number(self) -> Optional[str]:
        """
        The funding portal's SEC commission file number (e.g., '007-00033').

        This identifies the PORTAL, not the specific offering. Multiple companies
        can use the same portal, so this number appears across different offerings.

        To track a specific offering's lifecycle, use the issuer file number from
        filing.as_company_filing().file_number or Campaign.issuer_file_number.

        Returns None if no funding portal is specified (e.g., in C-AR forms).
        """
        if self.issuer_information.funding_portal:
            return self.issuer_information.funding_portal.file_number
        return None

    @property
    def issuer_name(self) -> str:
        """Convenience property for issuer name"""
        return self.issuer_information.name

    @property
    def issuer_cik(self) -> str:
        """Convenience property for issuer CIK"""
        return self.filer_information.cik

    @property
    def portal_name(self) -> Optional[str]:
        """Convenience property for funding portal name. Returns None if no portal."""
        if self.issuer_information.funding_portal:
            return self.issuer_information.funding_portal.name
        return None

    @property
    def portal_cik(self) -> Optional[str]:
        """Convenience property for funding portal CIK. Returns None if no portal."""
        if self.issuer_information.funding_portal:
            return self.issuer_information.funding_portal.cik
        return None

    @property
    def days_to_deadline(self) -> Optional[int]:
        """
        Days remaining until offering deadline.
        Returns negative number if deadline has passed.
        Returns None if no deadline is set or no offering information.
        """
        if not self.offering_information or not self.offering_information.deadline_date:
            return None
        return (self.offering_information.deadline_date - date.today()).days

    @property
    def is_expired(self) -> bool:
        """True if offering deadline has passed"""
        days = self.days_to_deadline
        return days is not None and days < 0

    @property
    def campaign_status(self) -> str:
        """User-friendly status derived from form type"""
        if self.form == "C-TR":
            return "Terminated"
        elif self.form.startswith("C-AR"):
            return "Annual Report"
        elif self.form.startswith("C-U"):
            return "Progress Update"
        elif self.form.endswith("/A"):
            return "Active (Amendment)"
        else:
            return "Active (Initial)"

    @cached_property
    def issuer(self) -> 'IssuerCompany':
        """
        Get the issuer company for this offering (cached).

        Returns an IssuerCompany object that provides offering-specific methods
        and can be converted to a full Company object with as_company().

        Returns:
            IssuerCompany with CIK and name from this Form C

        Example:
            >>> formc = filing.obj()
            >>> issuer = formc.issuer
            >>> print(issuer.name)
            >>> offerings = issuer.get_offerings()  # All offerings by this company
            >>> company = issuer.as_company()  # Full Company object
        """
        return IssuerCompany(
            cik=self.filer_information.cik,
            name=self.issuer_information.name
        )

    def get_issuer_company(self) -> 'IssuerCompany':
        """
        Get the issuer company for this offering.

        .. deprecated::
            Use the `issuer` property instead. This method is kept for backward compatibility.

        Returns:
            IssuerCompany with CIK and name from this Form C
        """
        return self.issuer

    def get_offering(self):
        """
        Get the complete offering lifecycle for this Form C filing.

        Returns an Offering object that provides access to all related filings
        (initial offering, amendments, updates, annual reports, termination).

        Returns:
            Offering object for this filing's offering lifecycle

        Raises:
            ValueError: If filing is not provided or file_number cannot be determined

        Example:
            >>> filing = company.get_filings(form='C')[0]
            >>> formc = filing.obj()
            >>> offering = formc.get_offering()
            >>> print(offering.timeline())
        """
        from edgar.offerings.campaign import Offering
        return Offering(self._filing)

    def to_context(self, detail: str = 'standard', filing_date: Optional[date] = None) -> str:
        """
        Returns a token-efficient, AI-optimized text representation of the Form C filing.

        This method provides a compact alternative to __rich__() that is optimized for
        LLM context windows. It includes computed fields (status, days remaining, ratios)
        and only displays populated fields.

        Args:
            detail: Level of detail to include:
                - 'minimal': ~100-200 tokens, essential fields only
                - 'standard': ~300-500 tokens, most important data (default)
                - 'full': ~600-1000 tokens, comprehensive view
            filing_date: Optional filing date to include in header

        Returns:
            Formatted string suitable for AI context

        Example:
            >>> formc.to_context()  # Standard detail
            >>> formc.to_context(detail='minimal')  # Minimal tokens
            >>> formc.to_context(detail='full')  # Everything
        """
        lines = []

        # Header (always included)
        header = f"FORM {self.form} - {self.description.upper()}"
        if filing_date:
            header += f" (Filed: {filing_date})"
        lines.append(header)
        lines.append("")

        # Issuer (always included)
        lines.append(f"ISSUER: {self.issuer_information.name}")
        if detail in ['standard', 'full']:
            lines.append(f"  CIK: {self.filer_information.cik}")
            lines.append(f"  Legal: {self.issuer_information.jurisdiction} "
                        f"{self.issuer_information.legal_status}")
            if self.issuer_information.website:
                lines.append(f"  Website: {self.issuer_information.website}")
            if detail == 'full' and self.issuer_information.address:
                city = self.issuer_information.address.city
                state = self.issuer_information.address.state_or_country
                lines.append(f"  Location: {city}, {state}")

        # Funding Portal (standard+)
        if self.issuer_information.funding_portal and detail in ['standard', 'full']:
            portal = self.issuer_information.funding_portal
            lines.append(f"\nFUNDING PORTAL: {portal.name}")
            if detail == 'full':
                lines.append(f"  CIK: {portal.cik} | CRD: {portal.crd or 'N/A'}")
            lines.append(f"  File Number: {portal.file_number}")

        # Offering (if present)
        if self.offering_information:
            lines.append("\nOFFERING:")

            # Security description
            lines.append(f"  Security: {self.offering_information.security_description}")

            # Amounts
            if self.offering_information.target_amount and self.offering_information.maximum_offering_amount:
                target = self.offering_information.target_amount
                max_amt = self.offering_information.maximum_offering_amount
                if detail == 'minimal':
                    # Compact format with K/M abbreviations
                    target_str = f"${target/1000:.0f}K" if target < 1000000 else f"${target/1000000:.1f}M"
                    max_str = f"${max_amt/1000:.0f}K" if max_amt < 1000000 else f"${max_amt/1000000:.1f}M"
                    lines.append(f"  Target: {target_str} → Max: {max_str}")
                else:
                    lines.append(f"  Target: ${target:,.0f} | Maximum: ${max_amt:,.0f}")
                    if self.offering_information.percent_to_maximum:
                        lines.append(f"  Target is {self.offering_information.percent_to_maximum:.0f}% of maximum")

            # Price and units (standard+)
            if detail in ['standard', 'full']:
                if self.offering_information.price_per_security:
                    price_str = f"${self.offering_information.price_per_security:,.2f}/unit"
                    if self.offering_information.number_of_securities:
                        price_str += f" | Units: {self.offering_information.number_of_securities:,}"
                    lines.append(f"  Price: {price_str}")

            # Deadline with computed days remaining
            if self.offering_information.deadline_date:
                days = self.days_to_deadline
                if days is not None:
                    if days > 0:
                        status = f"{days} days remaining"
                    elif days == 0:
                        status = "EXPIRES TODAY"
                    else:
                        status = f"EXPIRED ({abs(days)} days ago)"
                else:
                    status = ""

                if detail == 'minimal':
                    lines.append(f"  Deadline: {self.offering_information.deadline_date} ({status})")
                else:
                    lines.append(f"  Deadline: {self.offering_information.deadline_date}")
                    if status:
                        lines.append(f"  Status: {status}")

            # Over-subscription (full only)
            if detail == 'full' and self.offering_information.over_subscription_accepted == "Y":
                lines.append(f"  Over-subscription: Accepted")

            # Portal fees (full only)
            if detail == 'full' and self.offering_information.compensation_amount:
                lines.append(f"  Portal Fee: {self.offering_information.compensation_amount}")

        # Financials (if present)
        if self.annual_report_disclosure and detail in ['standard', 'full']:
            fin = self.annual_report_disclosure
            lines.append("\nFINANCIALS (Current vs Prior Year):")

            # Employees
            if detail == 'full':
                lines.append(f"  Employees: {fin.current_employees}")

            # Assets
            assets_curr = fin.total_asset_most_recent_fiscal_year
            assets_prior = fin.total_asset_prior_fiscal_year
            if assets_curr > 0:
                if assets_prior > 0 and fin.asset_growth_yoy is not None:
                    lines.append(f"  Assets: ${assets_curr:,.0f} "
                               f"({fin.asset_growth_yoy:+.0f}% from ${assets_prior:,.0f})")
                else:
                    lines.append(f"  Assets: ${assets_curr:,.0f}")

            # Cash
            if detail == 'full':
                cash_curr = fin.cash_equi_most_recent_fiscal_year
                if cash_curr > 0:
                    lines.append(f"  Cash: ${cash_curr:,.0f}")

            # Revenue status
            if fin.is_pre_revenue:
                lines.append(f"  Revenue: $0 (pre-revenue)")
            else:
                rev_curr = fin.revenue_most_recent_fiscal_year
                rev_prior = fin.revenue_prior_fiscal_year
                if fin.revenue_growth_yoy is not None and rev_prior > 0:
                    lines.append(f"  Revenue: ${rev_curr:,.0f} ({fin.revenue_growth_yoy:+.0f}% YoY)")
                else:
                    lines.append(f"  Revenue: ${rev_curr:,.0f}")

            # Net income
            ni_curr = fin.net_income_most_recent_fiscal_year
            ni_prior = fin.net_income_prior_fiscal_year
            if ni_curr < 0:
                if ni_prior < 0 and fin.burn_rate_change:
                    if fin.burn_rate_change < 0:
                        trend = "burn rate increasing"
                    else:
                        trend = "burn rate decreasing"
                    lines.append(f"  Net Income: ${ni_curr:,.0f} ({trend})")
                else:
                    lines.append(f"  Net Income: ${ni_curr:,.0f}")
            else:
                lines.append(f"  Net Income: ${ni_curr:,.0f}")

            # Debt
            total_debt = fin.total_debt_most_recent
            if total_debt > 0:
                debt_str = f"${total_debt:,.0f}"
                if detail == 'full':
                    debt_str += f" (short: ${fin.short_term_debt_most_recent_fiscal_year:,.0f}, "
                    debt_str += f"long: ${fin.long_term_debt_most_recent_fiscal_year:,.0f})"
                lines.append(f"  Total Debt: {debt_str}")

            # Debt-to-asset ratio (standard+)
            if fin.debt_to_asset_ratio is not None and detail in ['standard', 'full']:
                lines.append(f"  Debt-to-Asset Ratio: {fin.debt_to_asset_ratio:.0f}%")

        # Campaign status (always included)
        lines.append(f"\nCAMPAIGN STATUS: {self.campaign_status}")

        # Jurisdictions (full only)
        if self.annual_report_disclosure and detail == 'full':
            if self.annual_report_disclosure.is_offered_in_all_states:
                lines.append("  Offered in: All 50 states")
            else:
                num_states = len(self.annual_report_disclosure.offering_jurisdictions)
                lines.append(f"  Offered in: {num_states} jurisdictions")

        # Signatures (full only)
        if detail == 'full' and self.signature_info:
            num_signers = len(self.signature_info.signers)
            lines.append(f"\nSIGNATURES: {num_signers} officer{'s' if num_signers != 1 else ''}")
            if self.signature_info.issuer_signature:
                lines.append(f"  {self.signature_info.issuer_signature.title}: "
                           f"{self.signature_info.issuer_signature.signature}")

        # Available actions (standard+)
        if detail in ['standard', 'full']:
            lines.append("")
            lines.append("AVAILABLE ACTIONS:")
            lines.append("  - Use .get_offering() for complete campaign lifecycle")
            lines.append("  - Use .issuer for IssuerCompany information")
            if self.offering_information:
                lines.append("  - Use .offering_information for offering terms")
            if self.annual_report_disclosure:
                lines.append("  - Use .annual_report_disclosure for financial data")

        return "\n".join(lines)

    @property
    def docs(self):
        """
        Access comprehensive FormC API documentation.

        Returns:
            Docs: Documentation object that displays FormC class reference,
                  common actions, properties, and usage examples.

        Example:
            >>> filing = company.get_filings(form='C')[0]
            >>> formc = filing.obj()
            >>> formc.docs  # Display comprehensive documentation
        """
        return Docs(self)

    @staticmethod
    def parse_date(date_str) -> date:
        """
        The date is in the format MM-DD-YYYY
        """
        return datetime.strptime(date_str, "%m-%d-%Y").date()

    @staticmethod
    def format_date(date_value: date):
        """
        Format as April 1, 2021
        """
        return date_value.strftime("%B %d, %Y")

    @classmethod
    def from_filing(cls, filing: 'Filing'):
        offering_xml = filing.xml()
        if offering_xml:
            formc = FormC.from_xml(offering_xml, filing.form)
            formc._filing = filing
            return formc

    @classmethod
    def from_xml(cls, offering_xml: str, form: str):
        soup = BeautifulSoup(offering_xml, "xml")
        root = soup.find('edgarSubmission')

        # Header Data
        header_data = root.find('headerData')
        filer_info_el = header_data.find('filerInfo')

        filer_el = filer_info_el.find('filer')

        # Flags
        flags_tag = header_data.find('flags')
        confirming_copy_flag = child_text(flags_tag, 'confirmingCopyFlag') == 'true'
        return_copy_flag = child_text(flags_tag, 'returnCopyFlag') == 'true'
        override_internet_flag = child_text(flags_tag, 'overrideInternetFlag') == 'true'

        period = child_text(header_data, 'period')
        filer_information = FilerInformation(
            cik=filer_el.find('filerCik').text,
            ccc=filer_el.find('filerCik').text,
            confirming_copy_flag=confirming_copy_flag,
            return_copy_flag=return_copy_flag,
            override_internet_flag=override_internet_flag,
            live_or_test=child_text(filer_el, 'testOrLive') == 'LIVE',
            period=FormC.parse_date(period) if period else None
        )

        # Form
        form_data_tag = root.find('formData')

        # Issuer Information
        issuer_information_tag = form_data_tag.find('issuerInformation')
        issuer_info_tag = issuer_information_tag.find('issuerInfo')
        issuer_address_tag = issuer_info_tag.find('issuerAddress')
        address = Address(
            street1=child_text(issuer_address_tag, 'street1'),
            street2=child_text(issuer_address_tag, 'street2'),
            city=child_text(issuer_address_tag, 'city'),
            state_or_country=child_text(issuer_address_tag, 'stateOrCountry'),
            zipcode=child_text(issuer_address_tag, 'zipCode')
        )

        legal_status = child_text(issuer_info_tag, 'legalStatusForm')
        jurisdiction = child_text(issuer_info_tag, 'jurisdictionOrganization')
        date_of_incorporation = child_text(issuer_info_tag, 'dateIncorporation')

        # Funding Portal data
        funding_portal_cik = child_text(issuer_information_tag, 'commissionCik')
        funding_portal = FundingPortal(
            name=child_text(issuer_information_tag, 'companyName'),
            cik=funding_portal_cik,
            file_number=child_text(issuer_information_tag, 'commissionFileNumber'),
            crd=child_text(issuer_information_tag, 'crdNumber')
        ) if funding_portal_cik else None

        issuer_information = IssuerInformation(
            name=child_text(issuer_info_tag, 'nameOfIssuer'),
            address=address,
            website=child_text(issuer_info_tag, 'issuerWebsite'),
            co_issuer=get_bool(child_text(issuer_information_tag, 'isCoIssuer')),
            funding_portal=funding_portal,
            legal_status=legal_status,
            jurisdiction=jurisdiction,
            date_of_incorporation=FormC.parse_date(date_of_incorporation)
        )

        # Offering Information
        offering_info_tag = form_data_tag.find('offeringInformation')
        if offering_info_tag is not None and offering_info_tag.contents and offering_info_tag.get_text(strip=True):

            offering_information = OfferingInformation(
                compensation_amount=child_text(offering_info_tag, 'compensationAmount'),
                financial_interest=child_text(offering_info_tag, 'financialInterest'),
                security_offered_type=child_text(offering_info_tag, 'securityOfferedType'),
                security_offered_other_desc=child_text(offering_info_tag, 'securityOfferedOtherDesc'),
                no_of_security_offered=child_text(offering_info_tag, 'noOfSecurityOffered'),
                price=child_text(offering_info_tag, 'price'),
                price_determination_method=child_text(offering_info_tag, 'priceDeterminationMethod'),
                offering_amount=maybe_float(child_text(offering_info_tag, 'offeringAmount')),
                over_subscription_accepted=child_text(offering_info_tag, 'overSubscriptionAccepted'),
                over_subscription_allocation_type=child_text(offering_info_tag, 'overSubscriptionAllocationType'),
                desc_over_subscription=child_text(offering_info_tag, 'descOverSubscription'),
                maximum_offering_amount=maybe_float(child_text(offering_info_tag, 'maximumOfferingAmount')),
                deadline_date=maybe_date(child_text(offering_info_tag, 'deadlineDate'))
            )
        else:
            offering_information = None

        # Annual Report Disclosure
        annual_report_disclosure_tag = form_data_tag.find('annualReportDisclosureRequirements')
        # If the tag is not None and not Empty e.g. <annualReportDisclosureRequirements/>
        if annual_report_disclosure_tag and annual_report_disclosure_tag.contents:
            annual_report_disclosure = AnnualReportDisclosure(
                current_employees=int(float(child_text(annual_report_disclosure_tag, 'currentEmployees') or "0.00")),
                total_asset_most_recent_fiscal_year=maybe_float(child_text(annual_report_disclosure_tag,
                                                                           'totalAssetMostRecentFiscalYear')),
                total_asset_prior_fiscal_year=maybe_float(
                    child_text(annual_report_disclosure_tag, 'totalAssetPriorFiscalYear')),
                cash_equi_most_recent_fiscal_year=maybe_float(
                    child_text(annual_report_disclosure_tag, 'cashEquiMostRecentFiscalYear')),
                cash_equi_prior_fiscal_year=maybe_float(
                    child_text(annual_report_disclosure_tag, 'cashEquiPriorFiscalYear')),
                act_received_most_recent_fiscal_year=maybe_float(child_text(annual_report_disclosure_tag,
                                                                            'actReceivedMostRecentFiscalYear')),
                act_received_prior_fiscal_year=maybe_float(
                    child_text(annual_report_disclosure_tag, 'actReceivedPriorFiscalYear')),
                short_term_debt_most_recent_fiscal_year=maybe_float(child_text(annual_report_disclosure_tag,
                                                                               'shortTermDebtMostRecentFiscalYear')),
                short_term_debt_prior_fiscal_year=maybe_float(
                    child_text(annual_report_disclosure_tag, 'shortTermDebtPriorFiscalYear')),
                long_term_debt_most_recent_fiscal_year=maybe_float(child_text(annual_report_disclosure_tag,
                                                                              'longTermDebtMostRecentFiscalYear')),
                long_term_debt_prior_fiscal_year=maybe_float(
                    child_text(annual_report_disclosure_tag, 'longTermDebtPriorFiscalYear')),
                revenue_most_recent_fiscal_year=maybe_float(
                    child_text(annual_report_disclosure_tag, 'revenueMostRecentFiscalYear')),
                revenue_prior_fiscal_year=maybe_float(
                    child_text(annual_report_disclosure_tag, 'revenuePriorFiscalYear')),
                cost_goods_sold_most_recent_fiscal_year=maybe_float(child_text(annual_report_disclosure_tag,
                                                                               'costGoodsSoldMostRecentFiscalYear')),
                cost_goods_sold_prior_fiscal_year=maybe_float(
                    child_text(annual_report_disclosure_tag, 'costGoodsSoldPriorFiscalYear')),
                tax_paid_most_recent_fiscal_year=maybe_float(
                    child_text(annual_report_disclosure_tag, 'taxPaidMostRecentFiscalYear')),
                tax_paid_prior_fiscal_year=maybe_float(
                    child_text(annual_report_disclosure_tag, 'taxPaidPriorFiscalYear')),
                net_income_most_recent_fiscal_year=maybe_float(child_text(annual_report_disclosure_tag,
                                                                          'netIncomeMostRecentFiscalYear')),
                net_income_prior_fiscal_year=maybe_float(
                    child_text(annual_report_disclosure_tag, 'netIncomePriorFiscalYear')),
                offering_jurisdictions=[el.text for el in
                                        annual_report_disclosure_tag.find_all('issueJurisdictionSecuritiesOffering')]
            )
        else:
            annual_report_disclosure = None

        # Signature Block
        signature_block_tag = root.find("signatureInfo")

        issuer_signature_tag = signature_block_tag.find("issuerSignature")

        signature_info = SignatureInfo(
            issuer_signature=IssuerSignature(
                issuer=child_text(issuer_signature_tag, "issuer"),
                signature=child_text(issuer_signature_tag, "issuerSignature"),
                title=child_text(issuer_signature_tag, "issuerTitle")
            ),
            signatures=[
                PersonSignature(
                    signature=child_text(person_signature_tag, "personSignature"),
                    title=child_text(person_signature_tag, "personTitle"),
                    date=FormC.parse_date(child_text(person_signature_tag, "signatureDate"))
                ) for person_signature_tag in signature_block_tag.find_all('signaturePerson')
            ]
        )

        return cls(filer_information=filer_information,
                   issuer_information=issuer_information,
                   offering_information=offering_information,
                   annual_report_disclosure=annual_report_disclosure,
                   signature_info=signature_info,
                   form=form)

    def __rich__(self):

        # Filer Panel
        filer_table = Table("Company", "CIK", box=box.SIMPLE)
        if self.filer_information.period:
            filer_table.add_column("Period")
            filer_table.add_row(self.filer_information.company.name, self.filer_information.cik,
                                FormC.format_date(self.filer_information.period))
        else:
            filer_table.add_row(self.filer_information.company.name, self.filer_information.cik)
        filer_panel = Panel(filer_table, title=Text("Filer", style="bold deep_sky_blue1"), box=box.ROUNDED)

        # Issuers
        issuer_table = Table(Column("Issuer", style="bold"), "Legal Status", "Incorporated", "Jurisdiction",
                             box=box.SIMPLE)
        issuer_table.add_row(self.issuer_information.name,
                             self.issuer_information.legal_status,
                             FormC.format_date(self.issuer_information.date_of_incorporation),
                             states.get(self.issuer_information.jurisdiction, self.issuer_information.jurisdiction))

        # Address Panel
        address_panel = Panel(
            Text(str(self.issuer_information.address)),
            title='\U0001F3E2 Business Address', width=40)

        # Address and website
        contact_columns = Columns([address_panel, Panel(Text(self.issuer_information.website), title="Website")])

        issuer_panel = Panel(
            Group(*[issuer_table, contact_columns]),
            title=Text("Issuer", style="bold deep_sky_blue1"),
            box=box.ROUNDED
        )

        # Funding Portal
        funding_portal_panel = None
        if self.issuer_information.funding_portal is not None:
            intermediary_table = Table(Column("Name", style="bold"), "CIK", "CRD Number", "File Number", box=box.SIMPLE)
            intermediary_table.add_row(
                self.issuer_information.funding_portal.name,
                self.issuer_information.funding_portal.cik,
                self.issuer_information.funding_portal.crd or "",
                self.issuer_information.funding_portal.file_number)
            funding_portal_panel = Panel(
                intermediary_table,
                title=Text("CrowdFunding Portal", style="bold deep_sky_blue1"),
                box=box.ROUNDED
            )

        offering_panel = None

        if self.offering_information:
            # Offering Information
            offering_table = Table(Column("", style='bold'), "", box=box.SIMPLE, row_styles=["", "bold"])
            offering_table.add_row("Compensation Amount", self.offering_information.compensation_amount)
            offering_table.add_row("Financial Interest", self.offering_information.financial_interest)
            offering_table.add_row("Type of Security", self.offering_information.security_offered_type)
            offering_table.add_row("Number of Securities", self.offering_information.no_of_security_offered)
            offering_table.add_row("Price", self.offering_information.price)
            offering_table.add_row("Price (or Method for Determining Price)",
                                   self.offering_information.price_determination_method)
            offering_table.add_row("Target Offering Amount", f"${self.offering_information.offering_amount:,.2f}")
            offering_table.add_row("Maximum Offering Amount",
                                   f"${self.offering_information.maximum_offering_amount:,.2f}")
            offering_table.add_row("Over-Subscription Accepted",
                                   yes_no(self.offering_information.over_subscription_accepted == "Y")),
            offering_table.add_row("How will over-subscriptions be allocated",
                                   self.offering_information.over_subscription_allocation_type)
            offering_table.add_row("Describe over-subscription plan",
                                   self.offering_information.desc_over_subscription)
            offering_table.add_row("Deadline Date", FormC.format_date(
                self.offering_information.deadline_date) if self.offering_information.deadline_date else "")

            offering_panel = Panel(
                offering_table,
                title=Text("Offering Information", style="bold deep_sky_blue1"),
                box=box.ROUNDED
            )

        # Annual Report Disclosure
        if self.annual_report_disclosure:
            annual_report_panel = Panel(
                self.annual_report_disclosure.__rich__(),
                title=Text("Annual Report Disclosures", style="bold deep_sky_blue1"),
                box=box.ROUNDED
            )
        else:
            annual_report_panel = None

        # Signature Info
        # The signature of the issuer
        issuer_signature_table = Table(Column("Signature", style="bold"), "Title", "Issuer", box=box.SIMPLE)
        issuer_signature_table.add_row(self.signature_info.issuer_signature.signature,
                                       self.signature_info.issuer_signature.title,
                                       self.signature_info.issuer_signature.issuer)

        # Person Signatures
        person_signature_table = Table(Column("Signature", style="bold"), "Title", "Date", box=box.SIMPLE,
                                       row_styles=["", "bold"])
        for signature in self.signature_info.signatures:
            person_signature_table.add_row(signature.signature, signature.title,
                                           FormC.format_date(signature.date))

        signature_panel = Panel(
            Group(
                Panel(issuer_signature_table, box=box.ROUNDED, title="Issuer"),
                Panel(person_signature_table, box=box.ROUNDED, title="Persons")
            ),
            title=Text("Signatures", style="bold deep_sky_blue1"),
            box=box.ROUNDED
        )

        renderables = [
            filer_panel,
            issuer_panel,
        ]
        if funding_portal_panel is not None:
            renderables.append(funding_portal_panel)
        if self.offering_information is not None:
            renderables.append(offering_panel)
        if self.annual_report_disclosure is not None:
            renderables.append(annual_report_panel)
        renderables.append(signature_panel)

        panel = Panel(
            Group(*renderables),
            title=Text(self.description, style="bold dark_sea_green4"),
        )
        return panel

    def __repr__(self):
        return repr_rich(self.__rich__())
