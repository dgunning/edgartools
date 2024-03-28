import re
from dataclasses import dataclass
from typing import List

from bs4 import BeautifulSoup, Tag
from rich import box
from rich.columns import Columns
from rich.console import Group, Text, RenderableType
from rich.panel import Panel
from rich.table import Table

from edgar.core import get_bool
from edgar._party import Issuer, Person, Address
from edgar._rich import repr_rich
from edgar._xml import child_text, child_value


@dataclass(frozen=True)
class Filer:
    cik: str
    ccc: str


@dataclass(frozen=True)
class BusinessCombinationTransaction:
    is_business_combination: bool
    clarification_of_response: str


@dataclass(frozen=True)
class OfferingSalesAmounts:
    total_offering_amount: object
    total_amount_sold: object
    total_remaining: object
    clarification_of_response: str


@dataclass(frozen=True)
class Investors:
    has_non_accredited_investors: bool
    total_already_invested: object


@dataclass(frozen=True)
class SalesCommissionFindersFees:
    sales_commission: object
    finders_fees: object
    clarification_of_response: str


@dataclass(frozen=True)
class InvestmentFundInfo:
    investment_fund_type: str
    is_40_act: bool


@dataclass(frozen=True)
class IndustryGroup:
    industry_group_type: str
    investment_fund_info: InvestmentFundInfo = None


@dataclass(frozen=True)
class UseOfProceeds:
    gross_proceeds_used: object
    clarification_of_response: str


@dataclass(frozen=True)
class Signature:
    issuer_name: str
    signature_name: str
    name_of_signer: str
    title: str
    date: str


@dataclass(frozen=True)
class SignatureBlock:
    authorized_representative: bool
    signatures: List[Signature]


class SalesCompensationRecipient:
    """
     <recipient>
                <recipientName>Charles Harrison</recipientName>
                <recipientCRDNumber>3071551</recipientCRDNumber>
                <associatedBDName>H &amp; L Equities, LLC</associatedBDName>
                <associatedBDCRDNumber>113794</associatedBDCRDNumber>
                <recipientAddress>
                    <street1>1175 Peachtree St. NE, Suite 2200</street1>
                    <city>Atlanta</city>
                    <stateOrCountry>GA</stateOrCountry>
                    <stateOrCountryDescription>GEORGIA</stateOrCountryDescription>
                    <zipCode>30361</zipCode>
                </recipientAddress>
                <statesOfSolicitationList>
                    <state>FL</state>
                    <description>FLORIDA</description>
                    <state>GA</state>
                    <description>GEORGIA</description>
                    <state>TX</state>
                    <description>TEXAS</description>
                </statesOfSolicitationList>
                <foreignSolicitation>false</foreignSolicitation>
            </recipient>
    """

    def __init__(self,
                 name: str,
                 crd: str,
                 associated_bd_name: str,
                 associated_bd_crd: str,
                 address: Address,
                 states_of_solicitation: List[str] = None):
        self.name: str = name
        self.crd: str = crd
        self.associated_bd_name: associated_bd_name
        self.associated_bd_crd: str = associated_bd_crd
        self.address: str = address
        self.states_of_solicitation: List[str] = states_of_solicitation

    @classmethod
    def from_xml(cls,
                 recipient_tag: Tag):
        # Name and Crd can be "None"
        name = re.sub("None", "", child_text(recipient_tag, "recipientName") or "")
        crd = re.sub("None", "", child_text(recipient_tag, "recipientCRDNumber") or "")
        associated_bd_name = re.sub("None", "", child_text(recipient_tag, "associatedBDName") or "", re.IGNORECASE)
        associated_bd_crd = re.sub("None", "", child_text(recipient_tag, "associatedBDCRDNumber") or "", re.IGNORECASE)

        address_tag = recipient_tag.find("recipientAddress")
        address = Address(
            street1=child_text(address_tag, "street1"),
            street2=child_text(address_tag, "street2"),
            city=child_text(address_tag, "city"),
            state_or_country=child_text(address_tag, "stateOrCountry"),
            state_or_country_description=child_text(address_tag, "stateOrCountryDescription"),
            zipcode=child_text(address_tag, "30361")
        ) if address_tag else None

        # States of Solicitation List
        states_of_solicitation_tag = recipient_tag.find("statesOfSolicitationList")
        # Add individual states
        states_of_solicitation = [el.text for el in
                                  states_of_solicitation_tag.find_all("state")] if states_of_solicitation_tag else []
        # Sometimes there are no states but there are values e.g. <value>All States</value>
        solicitation_values = [el.text for el in
                               states_of_solicitation_tag.find_all("value")] if states_of_solicitation_tag else []
        states_of_solicitation += solicitation_values

        return cls(
            name=name,
            crd=crd,
            associated_bd_name=associated_bd_name,
            associated_bd_crd=associated_bd_crd,
            address=address,
            states_of_solicitation=states_of_solicitation
        )


class OfferingData:

    def __init__(self,
                 industry_group: IndustryGroup,
                 revenue_range: str,
                 federal_exemptions: List[str],
                 is_new: bool,
                 date_of_first_sale: str,
                 more_than_one_year: bool,
                 is_equity: bool,
                 is_pooled_investment: bool,
                 business_combination_transaction: BusinessCombinationTransaction,
                 minimum_investment: str,
                 sales_compensation_recipients: List[SalesCompensationRecipient] = None,
                 offering_sales_amounts: OfferingSalesAmounts = None,
                 investors: Investors = None,
                 sales_commission_finders_fees: SalesCommissionFindersFees = None,
                 use_of_proceeds: UseOfProceeds = None):
        self.industry_group: IndustryGroup = industry_group
        self.revenue_range: str = revenue_range
        self.federal_exemptions: List[str] = federal_exemptions
        self.is_new: bool = is_new
        self.date_of_first_sale: str = date_of_first_sale
        self.more_than_one_year: bool = more_than_one_year
        self.is_equity = is_equity
        self.is_pooled_investment = is_pooled_investment
        self.business_combination_transaction: BusinessCombinationTransaction = business_combination_transaction
        self.minimum_investment = minimum_investment
        self.sales_compensation_recipients: List[SalesCompensationRecipient] = sales_compensation_recipients or []
        self.offering_sales_amounts = offering_sales_amounts
        self.investors: Investors = investors
        self.sales_commission_finders_fees: SalesCommissionFindersFees = sales_commission_finders_fees
        self.use_of_proceeds: UseOfProceeds = use_of_proceeds

    @classmethod
    def from_xml(cls, offering_data_el: Tag):
        # industryGroup
        industry_group_el = offering_data_el.find("industryGroup")
        industry_group_type = child_text(industry_group_el, "industryGroupType") if industry_group_el else ""
        investment_fund_info_el = industry_group_el.find("investmentFundInfo")
        investment_fund_info = InvestmentFundInfo(
            investment_fund_type=child_text(investment_fund_info_el, "investmentFundType"),
            is_40_act=child_text(investment_fund_info_el, "is40Act") == "true"
        ) if investment_fund_info_el else None

        industry_group = IndustryGroup(industry_group_type=industry_group_type,
                                       investment_fund_info=investment_fund_info)

        issuer_size_el = offering_data_el.find("issuerSize")
        revenue_range = child_text(issuer_size_el, "revenueRange")

        fed_exemptions_el = offering_data_el.find("federalExemptionsExclusions")
        federal_exemptions = [item_el.text
                              for item_el
                              in fed_exemptions_el.find_all("item")] if fed_exemptions_el else []

        # type of filing
        type_of_filing_el = offering_data_el.find("typeOfFiling")
        new_or_amendment_el = type_of_filing_el.find("newOrAmendment")
        new_or_amendment = new_or_amendment_el and child_text(new_or_amendment_el, "isAmendment") == "true"
        date_of_first_sale = child_value(type_of_filing_el, "dateOfFirstSale")

        # Duration of transaction
        duration_of_offering_el = offering_data_el.find("durationOfOffering")
        more_than_one_year = duration_of_offering_el and child_text(duration_of_offering_el,
                                                                    "moreThanOneYear") == "true"

        # Type of security
        type_of_seurity_el = offering_data_el.find("typesOfSecuritiesOffered")
        is_equity = child_text(type_of_seurity_el, "isEquityType") == "true"
        is_pooled_investment = child_text(type_of_seurity_el, "isPooledInvestmentFundType") == "true"

        # Businss combination
        bus_combination_el = offering_data_el.find("businessCombinationTransaction")
        business_combination_transaction = BusinessCombinationTransaction(
            is_business_combination=bus_combination_el and child_text(bus_combination_el,
                                                                      "isBusinessCombinationTransaction") == "true",
            clarification_of_response=child_text(bus_combination_el, "clarificationOfResponse")
        ) if bus_combination_el else None

        # Minimum investment
        minimum_investment = child_text(offering_data_el, "minimumInvestmentAccepted")

        # Sales Compensation List
        sales_compensation_tag = offering_data_el.find("salesCompensationList")
        sales_compensation_recipients = [
            SalesCompensationRecipient.from_xml(el)
            for el in sales_compensation_tag.find_all("recipient")
        ] if sales_compensation_tag else []

        # Offering Sales Amount
        offering_sales_amount_tag = offering_data_el.find("offeringSalesAmounts")
        offering_sales_amounts = OfferingSalesAmounts(
            total_offering_amount=child_text(offering_sales_amount_tag, "totalOfferingAmount"),
            total_amount_sold=child_text(offering_sales_amount_tag, "totalAmountSold"),
            total_remaining=child_text(offering_sales_amount_tag, "totalRemaining"),
            clarification_of_response=child_text(offering_sales_amount_tag, "clarificationOfResponse")
        ) if offering_sales_amount_tag else None

        # investors
        investors_tag = offering_data_el.find("investors")
        investors = Investors(
            has_non_accredited_investors=child_text(investors_tag, "hasNonAccreditedInvestors") == "true",
            total_already_invested=child_text(investors_tag, "totalNumberAlreadyInvested")
        ) if investors_tag else None

        # salesCommissionsFindersFees
        sales_commission_finders_tag = offering_data_el.find("salesCommissionsFindersFees")
        sales_commission_finders_fees = SalesCommissionFindersFees(
            sales_commission=child_text(sales_commission_finders_tag.find("salesCommissions"), "dollarAmount"),
            finders_fees=child_text(sales_commission_finders_tag.find("findersFees"), "dollarAmount"),
            clarification_of_response=child_text(sales_commission_finders_tag, "clarificationOfResponse")
        ) if sales_commission_finders_tag else None

        # useOfProceeds
        use_of_proceeds_tag = offering_data_el.find("useOfProceeds")
        use_of_proceeds = UseOfProceeds(
            gross_proceeds_used=child_text(use_of_proceeds_tag.find("grossProceedsUsed"), "dollarAmount"),
            clarification_of_response=child_text(use_of_proceeds_tag, "clarificationOfResponse")
        )

        return cls(industry_group=industry_group,
                   revenue_range=revenue_range,
                   federal_exemptions=federal_exemptions,
                   is_new=new_or_amendment,
                   date_of_first_sale=date_of_first_sale,
                   more_than_one_year=more_than_one_year,
                   is_equity=is_equity,
                   is_pooled_investment=is_pooled_investment,
                   business_combination_transaction=business_combination_transaction,
                   minimum_investment=minimum_investment,
                   sales_compensation_recipients=sales_compensation_recipients,
                   offering_sales_amounts=offering_sales_amounts,
                   investors=investors,
                   sales_commission_finders_fees=sales_commission_finders_fees,
                   use_of_proceeds=use_of_proceeds)

    def __rich__(self):
        base_info_table = Table("amount offered", "amount sold", "investors", "minimum investment")
        base_info_table.add_row(self.offering_sales_amounts.total_offering_amount,
                                self.offering_sales_amounts.total_amount_sold,
                                self.investors.total_already_invested,
                                self.minimum_investment or "")
        return Group(
            Panel.fit(base_info_table, title="Offering Info", title_align="left", box=box.SIMPLE)
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


class Offering:
    """
    Represents a Form D Offering. Might require a name change to FormD
    """

    def __init__(self,
                 submission_type: str,
                 is_live: bool,
                 primary_issuer: Issuer,
                 related_persons: List[Person],
                 offering_data: OfferingData,
                 signature_block: SignatureBlock):
        self.submission_type: str = submission_type
        self.is_live: bool = is_live
        self.primary_issuer = primary_issuer
        self.related_persons: List = related_persons
        self.offering_data = offering_data
        self.signature_block = signature_block

    @property
    def is_new(self):
        return self.offering_data.is_new

    @classmethod
    def from_xml(cls, offering_xml: str):
        soup = BeautifulSoup(offering_xml, "xml")
        root = soup.find("edgarSubmission")

        # Parse the issuer
        primary_issuer_el = root.find("primaryIssuer")
        primary_issuer = Issuer.from_xml(primary_issuer_el)
        is_live = child_text(root, 'testOrLive') == 'LIVE'

        # Parse the related party names
        related_party_list = root.find("relatedPersonsList")
        related_persons = []
        for related_person_el in related_party_list.find_all("relatedPersonInfo"):
            related_person_name_el = related_person_el.find("relatedPersonName")
            first_name = child_text(related_person_name_el, "firstName")
            last_name = child_text(related_person_name_el, "lastName")

            related_person_address_el = related_person_el.find("relatedPersonAddress")
            address: Address = Address(
                street1=child_text(related_person_address_el, "street1"),
                street2=child_text(related_person_address_el, "street2"),
                city=child_text(related_person_address_el, "city"),
                state_or_country=child_text(related_person_address_el, "stateOrCountry"),
                state_or_country_description=child_text(related_person_address_el, "stateOrCountryDescription"),
                zipcode=child_text(related_person_address_el, "zipCode")
            )
            related_persons.append(Person(first_name=first_name, last_name=last_name, address=address))

        # Get the offering data
        offering_data = OfferingData.from_xml(root.find("offeringData"))

        # Get the signature
        signature_block_tag = root.find("signatureBlock")
        signatures = [Signature(
            issuer_name=child_text(sig_el, "issuerName"),
            signature_name=child_text(sig_el, "signatureName"),
            name_of_signer=child_text(sig_el, "nameOfSigner"),
            title=child_text(sig_el, "signatureTitle"),
            date=child_text(sig_el, "signatureDate"))
            for sig_el in signature_block_tag.find_all("signature")
        ]
        signature_block = SignatureBlock(
            authorized_representative=child_text(signature_block_tag, "authorizedRepresentative") == "true",
            signatures=signatures
        )

        return cls(submission_type=child_text(root, 'submissionType'),
                   is_live=is_live,
                   primary_issuer=primary_issuer,
                   related_persons=related_persons,
                   offering_data=offering_data,
                   signature_block=signature_block)

    def __rich__(self):
        highlight_col_style = "deep_sky_blue1 bold"
        # Issuer Table
        issuer_table = Table(box=box.SIMPLE)
        issuer_table.add_column("entity", style=highlight_col_style)
        issuer_table.add_column("cik")
        issuer_table.add_column("incorporated")

        issuer_table.add_row(self.primary_issuer.entity_name,
                             self.primary_issuer.cik,
                             f"{self.primary_issuer.year_of_incorporation} ({self.primary_issuer.jurisdiction})",
                             )
        # Offering info table
        offering_detail_table = Table(box=box.SIMPLE)
        offering_detail_table.add_column("amount offered", style=highlight_col_style)
        offering_detail_table.add_column("amount sold")
        offering_detail_table.add_column("investors")
        offering_detail_table.add_column("minimum investment")
        offering_detail_table.add_row(self.offering_data.offering_sales_amounts.total_offering_amount,
                                      self.offering_data.offering_sales_amounts.total_amount_sold,
                                      self.offering_data.investors.total_already_invested,
                                      self.offering_data.minimum_investment or "")

        # related person table
        related_persons_table = Table(box=box.SIMPLE)
        related_persons_table.add_column("related person", style=highlight_col_style)

        for index, person in enumerate(self.related_persons):
            related_persons_table.add_row(f"{person.first_name} {person.last_name}")

        # Sales compensation recipients
        sales_recipients_table = Table(box=box.SIMPLE)
        sales_recipients_table.add_column("name", style=highlight_col_style)
        sales_recipients_table.add_column("crd")
        sales_recipients_table.add_column("states")

        # dislay for states

        for index, sales_recipient in enumerate(self.offering_data.sales_compensation_recipients):
            max_states_to_display = 10
            if len(sales_recipient.states_of_solicitation) > max_states_to_display:
                states = ",".join(sales_recipient.states_of_solicitation[:max_states_to_display]) + " ..."
            else:
                states = ",".join(sales_recipient.states_of_solicitation)
            sales_recipients_table.add_row(sales_recipient.name or "",
                                           sales_recipient.crd or "",
                                           states)

        # Signature Block
        signature_table = Table(box=box.SIMPLE)
        signature_table.add_column(" ")
        signature_table.add_column("signature", style=highlight_col_style)
        signature_table.add_column("signer")
        signature_table.add_column("title")
        signature_table.add_column("date")
        signature_table.add_column("issuer")

        for index, signature in enumerate(self.signature_block.signatures):
            signature_table.add_row(str(index + 1),
                                    signature.signature_name,
                                    signature.name_of_signer,
                                    signature.title,
                                    signature.date,
                                    signature.issuer_name
                                    )

        def panel_fit(renderable: RenderableType, title: str = None):
            if title:
                return Panel.fit(renderable, title=title, title_align="left", box=box.SIMPLE,
                                 style="bold")
            else:
                return Panel.fit(renderable, box=box.SIMPLE, style="bold")

                # This is the final group of rich renderables

        return Group(
            panel_fit(issuer_table, title=f"Form {self.submission_type} Offering"),
            panel_fit(offering_detail_table, title="Offering Detail"),
            panel_fit(Columns([Group(Text("Related Persons"), related_persons_table),
                               Group(Text("Sales Compensation"), sales_recipients_table)]
                              )),
            panel_fit(signature_table, title="Signatures")
        )

    def __repr__(self):
        """
        Render __rich__ to a string and use that as __repr__
        :return:
        """
        return repr_rich(self.__rich__())


@dataclass(frozen=True)
class FilerInformation:
    cik: str
    ccc: str
    confirming_copy_flag: bool
    return_copy_flag: bool
    override_internet_flag: bool
    live_or_test: bool


@dataclass(frozen=True)
class IssuerInformation:
    name: str
    address: Address
    website: str
    co_issuer: bool
    company_name: str
    commission_cik: str
    commission_file_number: str
    crd_number: str
    legal_status: str
    jurisdiction: str
    date_of_incorporation: str

    @property
    def incorporated(self):
        return f"{self.date_of_incorporation or ''} {self.jurisdiction or ''}"


@dataclass(frozen=True)
class OfferingInformation:
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
      <maximumOfferingAmount>950000.00</maximumOfferingAmount>
      <deadlineDate>12-31-2024</deadlineDate>
    </offeringInformation>
    """
    compensation_amount: str
    financial_interest: str
    security_offered_type: str
    security_offered_other_desc: str
    no_of_security_offered: str
    price: str
    price_determination_method: str
    offering_amount: str
    over_subscription_accepted: str
    over_subscription_allocation_type: str
    maximum_offering_amount: str
    deadline_date: str


@dataclass(frozen=True)
class AnnualReportDisclosure:
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
    current_employees: str
    total_asset_most_recent_fiscal_year: str
    total_asset_prior_fiscal_year: str
    cash_equi_most_recent_fiscal_year: str
    cash_equi_prior_fiscal_year: str
    act_received_most_recent_fiscal_year: str
    act_received_prior_fiscal_year: str
    short_term_debt_most_recent_fiscal_year: str
    short_term_debt_prior_fiscal_year: str
    long_term_debt_most_recent_fiscal_year: str
    long_term_debt_prior_fiscal_year: str
    revenue_most_recent_fiscal_year: str
    revenue_prior_fiscal_year: str
    cost_goods_sold_most_recent_fiscal_year: str
    cost_goods_sold_prior_fiscal_year: str
    tax_paid_most_recent_fiscal_year: str
    tax_paid_prior_fiscal_year: str
    net_income_most_recent_fiscal_year: str
    net_income_prior_fiscal_year: str

    offering_jurisdictions: List[str]


@dataclass(frozen=True)
class PersonSignature:
    signature: str
    title: str
    date: str


@dataclass(frozen=True)
class IssuerSignature:
    issuer: str
    issuer_title: str
    signature: str


@dataclass(frozen=True)
class SignatureInfo:
    issuer_signature: IssuerSignature
    signatures: List[PersonSignature]


class FormCOffering:

    def __init__(self,
                 filer_information: FilerInformation,
                 issuer_information: IssuerInformation,
                 offering_information: OfferingInformation,
                 annual_report_disclosure: AnnualReportDisclosure,
                 signature_info: SignatureInfo):
        self.filer_information: FilerInformation = filer_information
        self.issuer_information: IssuerInformation = issuer_information
        self.offering_information: OfferingInformation = offering_information
        self.annual_report_disclosure: AnnualReportDisclosure = annual_report_disclosure
        self.signature_info: SignatureInfo = signature_info

    @classmethod
    def from_xml(cls, offering_xml: str):
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

        filer_information = FilerInformation(
            cik=filer_el.find('filerCik').text,
            ccc=filer_el.find('filerCik').text,
            confirming_copy_flag=confirming_copy_flag,
            return_copy_flag=return_copy_flag,
            override_internet_flag=override_internet_flag,
            live_or_test=child_text(filer_el, 'testOrLive') == 'LIVE'
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

        issuer_information = IssuerInformation(
            name=child_text(issuer_info_tag, 'nameOfIssuer'),
            address=address,
            website=child_text(issuer_info_tag, 'issuerWebsite'),
            co_issuer=get_bool(child_text(issuer_information_tag, 'isCoIssuer')),
            company_name=child_text(issuer_information_tag, 'companyName'),
            commission_cik=child_text(issuer_information_tag, 'commissionCik'),
            commission_file_number=child_text(issuer_information_tag, 'commissionFileNumber'),
            crd_number=child_text(issuer_information_tag, 'crdNumber'),
            legal_status=legal_status,
            jurisdiction=jurisdiction,
            date_of_incorporation=date_of_incorporation,
        )

        # Offering Information
        offering_info_tag = form_data_tag.find('offeringInformation')
        offering_information = OfferingInformation(
            compensation_amount=child_text(offering_info_tag, 'compensationAmount'),
            financial_interest=child_text(offering_info_tag, 'financialInterest'),
            security_offered_type=child_text(offering_info_tag, 'securityOfferedType'),
            security_offered_other_desc=child_text(offering_info_tag, 'securityOfferedOtherDesc'),
            no_of_security_offered=child_text(offering_info_tag, 'noOfSecurityOffered'),
            price=child_text(offering_info_tag, 'price'),
            price_determination_method=child_text(offering_info_tag, 'priceDeterminationMethod'),
            offering_amount=child_text(offering_info_tag, 'offeringAmount'),
            over_subscription_accepted=child_text(offering_info_tag, 'overSubscriptionAccepted'),
            over_subscription_allocation_type=child_text(offering_info_tag, 'overSubscriptionAllocationType'),
            maximum_offering_amount=child_text(offering_info_tag, 'maximumOfferingAmount'),
            deadline_date=child_text(offering_info_tag, 'deadlineDate')
        )

        # Annual Report Disclosure
        annual_report_disclosure_tag = form_data_tag.find('annualReportDisclosureRequirements')
        annual_report_disclosure = AnnualReportDisclosure(
            current_employees=child_text(annual_report_disclosure_tag, 'currentEmployees'),
            total_asset_most_recent_fiscal_year=child_text(annual_report_disclosure_tag,
                                                           'totalAssetMostRecentFiscalYear'),
            total_asset_prior_fiscal_year=child_text(annual_report_disclosure_tag, 'totalAssetPriorFiscalYear'),
            cash_equi_most_recent_fiscal_year=child_text(annual_report_disclosure_tag, 'cashEquiMostRecentFiscalYear'),
            cash_equi_prior_fiscal_year=child_text(annual_report_disclosure_tag, 'cashEquiPriorFiscalYear'),
            act_received_most_recent_fiscal_year=child_text(annual_report_disclosure_tag,
                                                            'actReceivedMostRecentFiscalYear'),
            act_received_prior_fiscal_year=child_text(annual_report_disclosure_tag, 'actReceivedPriorFiscalYear'),
            short_term_debt_most_recent_fiscal_year=child_text(annual_report_disclosure_tag,
                                                               'shortTermDebtMostRecentFiscalYear'),
            short_term_debt_prior_fiscal_year=child_text(annual_report_disclosure_tag, 'shortTermDebtPriorFiscalYear'),
            long_term_debt_most_recent_fiscal_year=child_text(annual_report_disclosure_tag,
                                                              'longTermDebtMostRecentFiscalYear'),
            long_term_debt_prior_fiscal_year=child_text(annual_report_disclosure_tag, 'longTermDebtPriorFiscalYear'),
            revenue_most_recent_fiscal_year=child_text(annual_report_disclosure_tag, 'revenueMostRecentFiscalYear'),
            revenue_prior_fiscal_year=child_text(annual_report_disclosure_tag, 'revenuePriorFiscalYear'),
            cost_goods_sold_most_recent_fiscal_year=child_text(annual_report_disclosure_tag,
                                                               'costGoodsSoldMostRecentFiscalYear'),
            cost_goods_sold_prior_fiscal_year=child_text(annual_report_disclosure_tag, 'costGoodsSoldPriorFiscalYear'),
            tax_paid_most_recent_fiscal_year=child_text(annual_report_disclosure_tag, 'taxPaidMostRecentFiscalYear'),
            tax_paid_prior_fiscal_year=child_text(annual_report_disclosure_tag, 'taxPaidPriorFiscalYear'),
            net_income_most_recent_fiscal_year=child_text(annual_report_disclosure_tag,
                                                          'netIncomeMostRecentFiscalYear'),
            net_income_prior_fiscal_year=child_text(annual_report_disclosure_tag, 'netIncomePriorFiscalYear'),
            offering_jurisdictions=[el.text for el in
                                    annual_report_disclosure_tag.find_all('issueJurisdictionSecuritiesOffering')]
        )

        # Signature Block
        signature_block_tag = root.find("signatureInfo")

        issuer_signature_tag = signature_block_tag.find("issuerSignature")

        signature_info = SignatureInfo(
            issuer_signature=IssuerSignature(
                issuer=child_text(issuer_signature_tag, "issuer"),
                signature=child_text(issuer_signature_tag, "issuerSignature"),
                issuer_title=child_text(issuer_signature_tag, "issuerTitle")
            ),
            signatures=[
                PersonSignature(
                    child_text(person_signature_tag, "personSignature"),
                    child_text(person_signature_tag, "personTitle"),
                    child_text(person_signature_tag, "signatureDate")
                ) for person_signature_tag in signature_block_tag.find_all('signaturePerson')
            ]
        )

        return cls(filer_information=filer_information,
                   issuer_information=issuer_information,
                   offering_information=offering_information,
                   annual_report_disclosure=annual_report_disclosure,
                   signature_info=signature_info)

    def __rich__(self):
        filer_table = Table("CIK",  box=box.SIMPLE )
        filer_table.add_row(self.filer_information.cik)
        filer_panel = Panel(filer_table, title="Filer", box=box.ROUNDED)

        # Issuers
        issuer_table = Table("Issuer", "Legal Status", "Incorporated", box=box.SIMPLE)
        issuer_table.add_row(self.issuer_information.name,
                             self.issuer_information.legal_status,
                             self.issuer_information.incorporated)
        issuer_panel = Panel(
            issuer_table,
            title="Issuer Information",
            box=box.ROUNDED
        )
        panel = Panel(
            Group(
                filer_panel,
                issuer_panel
            ),
            title="Form C Offering",
        )
        return panel

    def __repr__(self):
        return repr_rich(self.__rich__())




