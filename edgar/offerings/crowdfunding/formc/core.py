from __future__ import annotations

from datetime import date, datetime
from functools import cached_property
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from edgar._filings import Filing
    from edgar.offerings.crowdfunding.campaign import Offering

from lxml import etree

from edgar._party import Address
from edgar.core import get_bool
from edgar.entity import Company
from edgar.funds.reports import _strip_namespaces, _text
from edgar.richtools import Docs

from edgar.offerings.crowdfunding.formc.models import (
    FilerInformation,
    FundingPortal,
    IssuerInformation,
    OfferingInformation,
    AnnualReportDisclosure,
    PersonSignature,
    IssuerSignature,
    SignatureInfo,
)
from edgar.offerings.crowdfunding.formc.helpers import (
    maybe_float,
    maybe_date,
    group_offerings_by_file_number,
)
from edgar.offerings.crowdfunding.formc._render import FormCRenderMixin


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

    def latest_offering(self)->Optional['Offering']:
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


class FormC(FormCRenderMixin):

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
        from edgar.offerings.crowdfunding.campaign import Offering
        return Offering(self._filing)

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
        xml_bytes = offering_xml.encode() if isinstance(offering_xml, str) else offering_xml
        try:
            root = etree.fromstring(xml_bytes)
        except etree.XMLSyntaxError:
            parser = etree.XMLParser(recover=True, huge_tree=True)
            root = etree.fromstring(xml_bytes, parser=parser)
        _strip_namespaces(root)

        # Header Data
        header_data = root.find('headerData')
        filer_info_el = header_data.find('filerInfo')
        credentials_el = filer_info_el.find('filer/filerCredentials')

        # Flags
        flags_tag = filer_info_el.find('flags')
        confirming_copy_flag = _text(flags_tag, 'confirmingCopyFlag') == 'true'
        return_copy_flag = _text(flags_tag, 'returnCopyFlag') == 'true'
        override_internet_flag = _text(flags_tag, 'overrideInternetFlag') == 'true'

        period = _text(header_data, './/period')
        # Current schema puts <liveTestFlag> under filerInfo; older versions used <testOrLive>
        live_test_flag = _text(filer_info_el, 'liveTestFlag') or _text(filer_info_el, './/testOrLive')
        filer_information = FilerInformation(
            cik=_text(credentials_el, 'filerCik'),
            ccc=_text(credentials_el, 'filerCcc'),
            confirming_copy_flag=confirming_copy_flag,
            return_copy_flag=return_copy_flag,
            override_internet_flag=override_internet_flag,
            live_or_test=live_test_flag == 'LIVE',
            period=FormC.parse_date(period) if period else None
        )

        # Form
        form_data_tag = root.find('formData')

        # Issuer Information
        issuer_information_tag = form_data_tag.find('issuerInformation')
        issuer_info_tag = issuer_information_tag.find('issuerInfo')
        issuer_address_tag = issuer_info_tag.find('issuerAddress')
        address = Address(
            street1=_text(issuer_address_tag, 'street1'),
            street2=_text(issuer_address_tag, 'street2'),
            city=_text(issuer_address_tag, 'city'),
            state_or_country=_text(issuer_address_tag, 'stateOrCountry'),
            zipcode=_text(issuer_address_tag, 'zipCode')
        )

        # legalStatusForm etc. sit inside a <legalStatus> wrapper; search descendants
        legal_status = _text(issuer_info_tag, './/legalStatusForm')
        jurisdiction = _text(issuer_info_tag, './/jurisdictionOrganization')
        date_of_incorporation = _text(issuer_info_tag, './/dateIncorporation')

        # Funding Portal data
        funding_portal_cik = _text(issuer_information_tag, 'commissionCik')
        funding_portal = FundingPortal(
            name=_text(issuer_information_tag, 'companyName'),
            cik=funding_portal_cik,
            file_number=_text(issuer_information_tag, 'commissionFileNumber'),
            crd=_text(issuer_information_tag, 'crdNumber')
        ) if funding_portal_cik else None

        issuer_information = IssuerInformation(
            name=_text(issuer_info_tag, 'nameOfIssuer'),
            address=address,
            website=_text(issuer_info_tag, 'issuerWebsite'),
            co_issuer=get_bool(_text(issuer_information_tag, 'isCoIssuer')),
            funding_portal=funding_portal,
            legal_status=legal_status,
            jurisdiction=jurisdiction,
            date_of_incorporation=FormC.parse_date(date_of_incorporation)
        )

        # Offering Information
        offering_info_tag = form_data_tag.find('offeringInformation')
        # Skip when missing, self-closing (no children), or containing only empty elements
        if offering_info_tag is not None and len(offering_info_tag) and ''.join(offering_info_tag.itertext()).strip():

            offering_information = OfferingInformation(
                compensation_amount=_text(offering_info_tag, 'compensationAmount'),
                financial_interest=_text(offering_info_tag, 'financialInterest'),
                security_offered_type=_text(offering_info_tag, 'securityOfferedType'),
                security_offered_other_desc=_text(offering_info_tag, 'securityOfferedOtherDesc'),
                no_of_security_offered=_text(offering_info_tag, 'noOfSecurityOffered'),
                price=_text(offering_info_tag, 'price'),
                price_determination_method=_text(offering_info_tag, 'priceDeterminationMethod'),
                offering_amount=maybe_float(_text(offering_info_tag, 'offeringAmount')),
                over_subscription_accepted=_text(offering_info_tag, 'overSubscriptionAccepted'),
                over_subscription_allocation_type=_text(offering_info_tag, 'overSubscriptionAllocationType'),
                desc_over_subscription=_text(offering_info_tag, 'descOverSubscription'),
                maximum_offering_amount=maybe_float(_text(offering_info_tag, 'maximumOfferingAmount')),
                deadline_date=maybe_date(_text(offering_info_tag, 'deadlineDate'))
            )
        else:
            offering_information = None

        # Annual Report Disclosure
        annual_report_disclosure_tag = form_data_tag.find('annualReportDisclosureRequirements')
        # If the tag is not None and not Empty e.g. <annualReportDisclosureRequirements/>
        if annual_report_disclosure_tag is not None and len(annual_report_disclosure_tag):
            annual_report_disclosure = AnnualReportDisclosure(
                current_employees=int(float(_text(annual_report_disclosure_tag, 'currentEmployees') or "0.00")),
                total_asset_most_recent_fiscal_year=maybe_float(_text(annual_report_disclosure_tag,
                                                                           'totalAssetMostRecentFiscalYear')),
                total_asset_prior_fiscal_year=maybe_float(
                    _text(annual_report_disclosure_tag, 'totalAssetPriorFiscalYear')),
                cash_equi_most_recent_fiscal_year=maybe_float(
                    _text(annual_report_disclosure_tag, 'cashEquiMostRecentFiscalYear')),
                cash_equi_prior_fiscal_year=maybe_float(
                    _text(annual_report_disclosure_tag, 'cashEquiPriorFiscalYear')),
                act_received_most_recent_fiscal_year=maybe_float(_text(annual_report_disclosure_tag,
                                                                            'actReceivedMostRecentFiscalYear')),
                act_received_prior_fiscal_year=maybe_float(
                    _text(annual_report_disclosure_tag, 'actReceivedPriorFiscalYear')),
                short_term_debt_most_recent_fiscal_year=maybe_float(_text(annual_report_disclosure_tag,
                                                                               'shortTermDebtMostRecentFiscalYear')),
                short_term_debt_prior_fiscal_year=maybe_float(
                    _text(annual_report_disclosure_tag, 'shortTermDebtPriorFiscalYear')),
                long_term_debt_most_recent_fiscal_year=maybe_float(_text(annual_report_disclosure_tag,
                                                                              'longTermDebtMostRecentFiscalYear')),
                long_term_debt_prior_fiscal_year=maybe_float(
                    _text(annual_report_disclosure_tag, 'longTermDebtPriorFiscalYear')),
                revenue_most_recent_fiscal_year=maybe_float(
                    _text(annual_report_disclosure_tag, 'revenueMostRecentFiscalYear')),
                revenue_prior_fiscal_year=maybe_float(
                    _text(annual_report_disclosure_tag, 'revenuePriorFiscalYear')),
                cost_goods_sold_most_recent_fiscal_year=maybe_float(_text(annual_report_disclosure_tag,
                                                                               'costGoodsSoldMostRecentFiscalYear')),
                cost_goods_sold_prior_fiscal_year=maybe_float(
                    _text(annual_report_disclosure_tag, 'costGoodsSoldPriorFiscalYear')),
                tax_paid_most_recent_fiscal_year=maybe_float(
                    _text(annual_report_disclosure_tag, 'taxPaidMostRecentFiscalYear')),
                tax_paid_prior_fiscal_year=maybe_float(
                    _text(annual_report_disclosure_tag, 'taxPaidPriorFiscalYear')),
                net_income_most_recent_fiscal_year=maybe_float(_text(annual_report_disclosure_tag,
                                                                          'netIncomeMostRecentFiscalYear')),
                net_income_prior_fiscal_year=maybe_float(
                    _text(annual_report_disclosure_tag, 'netIncomePriorFiscalYear')),
                offering_jurisdictions=[el.text for el in
                                        annual_report_disclosure_tag.findall('.//issueJurisdictionSecuritiesOffering')]
            )
        else:
            annual_report_disclosure = None

        # Signature Block (lives under formData; location kept flexible across schema versions)
        signature_block_tag = root.find(".//signatureInfo")

        issuer_signature_tag = signature_block_tag.find("issuerSignature")

        signature_info = SignatureInfo(
            issuer_signature=IssuerSignature(
                issuer=_text(issuer_signature_tag, "issuer"),
                signature=_text(issuer_signature_tag, "issuerSignature"),
                title=_text(issuer_signature_tag, "issuerTitle")
            ),
            signatures=[
                PersonSignature(
                    signature=_text(person_signature_tag, "personSignature"),
                    title=_text(person_signature_tag, "personTitle"),
                    date=FormC.parse_date(_text(person_signature_tag, "signatureDate"))
                ) for person_signature_tag in signature_block_tag.findall('.//signaturePerson')
            ]
        )

        return cls(filer_information=filer_information,
                   issuer_information=issuer_information,
                   offering_information=offering_information,
                   annual_report_disclosure=annual_report_disclosure,
                   signature_info=signature_info,
                   form=form)
