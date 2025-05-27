from collections import defaultdict
from datetime import date, datetime
from functools import lru_cache
from typing import List, Optional

from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict
from rich import box
from rich.columns import Columns
from rich.console import Group, Text
from rich.panel import Panel
from rich.table import Table, Column

from edgar._party import Address
from edgar.richtools import repr_rich
from edgar.xmltools import child_text
from edgar.core import get_bool
from edgar.formatting import yes_no
from edgar.entity import Company
from edgar.reference import states

__all__ = ['FormC', 'Signer', 'FundingPortal']


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
            for index, jurisdictions in enumerate(jurisdiction_lists):
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
