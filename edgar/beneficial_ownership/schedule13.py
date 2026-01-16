"""
Main classes for Schedule 13D and Schedule 13G beneficial ownership reports.

This module implements the parsing and representation of SEC Schedule 13D
and Schedule 13G filings using XML-based parsing.
"""
import re
from datetime import date
from typing import TYPE_CHECKING, List, Optional

from bs4 import BeautifulSoup

if TYPE_CHECKING:
    from edgar._filings import Filing

from edgar._party import Address
from edgar.beneficial_ownership.models import IssuerInfo, ReportingPerson, Schedule13DItems, Schedule13GItems, SecurityInfo, Signature
from edgar.core import get_bool
from edgar.xmltools import child_text

__all__ = ['Schedule13D', 'Schedule13G']


def safe_int(value: Optional[str], default: int = 0) -> int:
    """
    Safely convert a string value to an integer.

    Handles empty strings, None, commas, whitespace, and decimal strings.

    Args:
        value: String value to convert
        default: Default value if conversion fails

    Returns:
        Integer value or default
    """
    if not value:
        return default
    try:
        # Remove commas and whitespace, then convert via float to handle decimals
        cleaned = value.strip().replace(',', '')
        return int(float(cleaned)) if cleaned else default
    except (ValueError, AttributeError):
        return default


def safe_float(value: Optional[str], default: float = 0.0) -> float:
    """
    Safely convert a string value to a float.

    Handles empty strings, None, commas, and whitespace.

    Args:
        value: String value to convert
        default: Default value if conversion fails

    Returns:
        Float value or default
    """
    if not value:
        return default
    try:
        # Remove commas and whitespace, then convert
        cleaned = value.strip().replace(',', '')
        return float(cleaned) if cleaned else default
    except (ValueError, AttributeError):
        return default


def extract_amendment_number(form_name: str) -> Optional[int]:
    """
    Extract amendment number from filing form name.

    Handles various amendment number formats:
    - "SCHEDULE 13D/A" with "Amendment No. 9" in title
    - "SC 13D/A #9"
    - Just "/A" with no number (returns None)

    Args:
        form_name: Form name/title from filing (e.g., "SCHEDULE 13D/A")

    Returns:
        Amendment number as integer, or None if not found or not an amendment
    """
    if '/A' not in form_name:
        return None

    # Try to extract number from patterns like:
    # "Amendment No. 9", "Amendment No. 12", etc.
    match = re.search(r'Amendment\s+No\.\s+(\d+)', form_name, re.IGNORECASE)
    if match:
        return int(match.group(1))

    # Try patterns like "/A #9", "/A#12"
    match = re.search(r'/A\s*#?(\d+)', form_name)
    if match:
        return int(match.group(1))

    # Amendment without number
    return None


class Schedule13D:
    """
    Schedule 13D - Active Beneficial Ownership Report.

    Filed when an investor acquires 5% or more of a company's stock with
    potential control intent or activist purposes. Requires detailed
    narrative disclosures about the purpose and intent of the investment.

    Example:
        filing = Filing(form='SCHEDULE 13D', ...)
        schedule = Schedule13D.from_filing(filing)
        print(schedule.issuer_info.name)
        print(schedule.reporting_persons[0].percent_of_class)
    """

    def __init__(
        self,
        filing,
        issuer_info: IssuerInfo,
        security_info: SecurityInfo,
        reporting_persons: List[ReportingPerson],
        items: Schedule13DItems,
        signatures: List[Signature],
        date_of_event: str,
        previously_filed: bool = False,
        amendment_number: Optional[int] = None
    ):
        self._filing = filing
        self.issuer_info = issuer_info
        self.security_info = security_info
        self.reporting_persons = reporting_persons
        self.items = items
        self.signatures = signatures
        self.date_of_event = date_of_event
        self.previously_filed = previously_filed
        self.amendment_number = amendment_number

    @staticmethod
    def parse_xml(xml: str) -> dict:
        """
        Parse Schedule 13D XML and return dict of all fields.

        Args:
            xml: XML content as string

        Returns:
            Dictionary with all parsed fields ready for Schedule13D constructor

        Raises:
            ValueError: If XML structure is invalid
        """
        soup = BeautifulSoup(xml, 'xml')
        root = soup.find('edgarSubmission')

        if not root:
            raise ValueError("Invalid XML: missing <edgarSubmission> root element")

        result = {}
        form_data = root.find('formData')

        # Parse cover page header
        cover = form_data.find('coverPageHeader')
        if not cover:
            raise ValueError("Invalid XML: missing <coverPageHeader>")

        # Security info
        result['security_info'] = SecurityInfo(
            title=child_text(cover, 'securitiesClassTitle') or '',
            cusip=''  # Will be filled from issuerInfo
        )

        result['date_of_event'] = child_text(cover, 'dateOfEvent') or ''
        result['previously_filed'] = get_bool(child_text(cover, 'previouslyFiledFlag'))

        # Parse issuer info
        issuer_el = cover.find('issuerInfo')
        if issuer_el:
            address_el = issuer_el.find('address')
            issuer_address = None
            if address_el:
                issuer_address = Address(
                    street1=child_text(address_el, 'street1'),
                    street2=child_text(address_el, 'street2'),
                    city=child_text(address_el, 'city'),
                    state_or_country=child_text(address_el, 'stateOrCountry'),
                    zipcode=child_text(address_el, 'zipCode')
                )

            cusip = child_text(issuer_el, 'issuerCUSIP') or ''
            result['issuer_info'] = IssuerInfo(
                cik=child_text(issuer_el, 'issuerCIK') or '',
                name=child_text(issuer_el, 'issuerName') or '',
                cusip=cusip,
                address=issuer_address
            )

            # Update security_info cusip
            result['security_info'] = SecurityInfo(
                title=result['security_info'].title,
                cusip=cusip
            )

        # Parse reporting persons (multiple)
        reporting_persons = []
        reporting_persons_el = form_data.find('reportingPersons')
        if reporting_persons_el:
            for person_el in reporting_persons_el.find_all('reportingPersonInfo'):
                reporting_persons.append(ReportingPerson(
                    cik=child_text(person_el, 'reportingPersonCIK') or '',
                    name=child_text(person_el, 'reportingPersonName') or '',
                    fund_type=child_text(person_el, 'fundType'),
                    citizenship=child_text(person_el, 'citizenshipOrOrganization') or '',
                    sole_voting_power=safe_int(child_text(person_el, 'soleVotingPower')),
                    shared_voting_power=safe_int(child_text(person_el, 'sharedVotingPower')),
                    sole_dispositive_power=safe_int(child_text(person_el, 'soleDispositivePower')),
                    shared_dispositive_power=safe_int(child_text(person_el, 'sharedDispositivePower')),
                    aggregate_amount=safe_int(child_text(person_el, 'aggregateAmountOwned')),
                    percent_of_class=safe_float(child_text(person_el, 'percentOfClass')),
                    type_of_reporting_person=child_text(person_el, 'typeOfReportingPerson') or '',
                    comment=child_text(person_el, 'commentContent'),
                    member_of_group=child_text(person_el, 'memberOfGroup'),
                    is_aggregate_exclude_shares=get_bool(child_text(person_el, 'isAggregateExcludeShares')),
                    no_cik=get_bool(child_text(person_el, 'reportingPersonNoCIK'))
                ))
        result['reporting_persons'] = reporting_persons

        # Parse Items 1-7
        items_el = form_data.find('items1To7')
        if items_el:
            # Item 1: Security and Issuer
            item1_el = items_el.find('item1')
            item1_security_title = None
            item1_issuer_name = None
            item1_issuer_address = None
            if item1_el:
                item1_security_title = child_text(item1_el, 'securityTitle')
                item1_issuer_name = child_text(item1_el, 'issuerName')
                # Build address string
                addr_el = item1_el.find('issuerPrincipalAddress')
                if addr_el:
                    addr_parts = [
                        child_text(addr_el, 'street1'),
                        child_text(addr_el, 'city'),
                        child_text(addr_el, 'stateOrCountry'),
                        child_text(addr_el, 'zipCode')
                    ]
                    item1_issuer_address = ', '.join(p for p in addr_parts if p)

            # Item 2: Identity and Background
            item2_el = items_el.find('item2')
            item2_filing_persons = None
            item2_business_address = None
            item2_principal_occupation = None
            item2_convictions = None
            item2_citizenship = None
            if item2_el:
                item2_filing_persons = child_text(item2_el, 'filingPersonName')
                item2_business_address = child_text(item2_el, 'principalBusinessAddress')
                item2_principal_occupation = child_text(item2_el, 'principalJob')
                item2_convictions = child_text(item2_el, 'convictionDescription')
                item2_citizenship = child_text(item2_el, 'citizenship')

            # Item 3: Source and Amount of Funds
            item3_el = items_el.find('item3')
            item3_source = child_text(item3_el, 'fundsSource') if item3_el else None

            # Item 4: Purpose of Transaction (MOST IMPORTANT)
            item4_el = items_el.find('item4')
            item4_purpose = child_text(item4_el, 'transactionPurpose') if item4_el else None

            # Item 5: Interest in Securities
            item5_el = items_el.find('item5')
            item5_percentage = None
            item5_shares = None
            item5_transactions = None
            item5_shareholders = None
            item5_date = None
            if item5_el:
                item5_percentage = child_text(item5_el, 'percentageOfClassSecurities')
                item5_shares = child_text(item5_el, 'numberOfShares')
                item5_transactions = child_text(item5_el, 'transactionDesc')
                item5_shareholders = child_text(item5_el, 'listOfShareholders')
                item5_date = child_text(item5_el, 'date5PercentOwnership')

            # Item 6: Contracts, Arrangements
            item6_el = items_el.find('item6')
            item6_contracts = child_text(item6_el, 'contractDescription') if item6_el else None

            # Item 7: Material to be Filed as Exhibits
            item7_el = items_el.find('item7')
            item7_exhibits = child_text(item7_el, 'filedExhibits') if item7_el else None

            result['items'] = Schedule13DItems(
                item1_security_title=item1_security_title,
                item1_issuer_name=item1_issuer_name,
                item1_issuer_address=item1_issuer_address,
                item2_filing_persons=item2_filing_persons,
                item2_business_address=item2_business_address,
                item2_principal_occupation=item2_principal_occupation,
                item2_convictions=item2_convictions,
                item2_citizenship=item2_citizenship,
                item3_source_of_funds=item3_source,
                item4_purpose_of_transaction=item4_purpose,
                item5_percentage_of_class=item5_percentage,
                item5_number_of_shares=item5_shares,
                item5_transactions=item5_transactions,
                item5_shareholders=item5_shareholders,
                item5_date_5pct_ownership=item5_date,
                item6_contracts=item6_contracts,
                item7_exhibits=item7_exhibits
            )
        else:
            result['items'] = Schedule13DItems()

        # Parse signatures
        signatures = []
        signature_info_el = form_data.find('signatureInfo')
        if signature_info_el:
            for sig_person_el in signature_info_el.find_all('signaturePerson'):
                sig_details_el = sig_person_el.find('signatureDetails')
                if sig_details_el:
                    signatures.append(Signature(
                        reporting_person=child_text(sig_person_el, 'signatureReportingPerson') or '',
                        signature=child_text(sig_details_el, 'signature') or '',
                        title=child_text(sig_details_el, 'title') or '',
                        date=child_text(sig_details_el, 'date') or ''
                    ))
        result['signatures'] = signatures

        return result

    @classmethod
    def from_filing(cls, filing: 'Filing') -> Optional['Schedule13D']:
        """
        Create Schedule13D instance from a Filing object.

        Args:
            filing: Filing object with form 'SCHEDULE 13D', 'SCHEDULE 13D/A', 'SC 13D', or 'SC 13D/A'

        Returns:
            Schedule13D instance or None if no XML found

        Raises:
            AssertionError: If filing is not a Schedule 13D form
        """
        assert filing.form in ['SCHEDULE 13D', 'SCHEDULE 13D/A', 'SC 13D', 'SC 13D/A'], \
            f"Expected Schedule 13D form, got {filing.form}"

        xml = filing.xml()
        if xml:
            parsed = cls.parse_xml(xml)
            # Extract amendment number from filing form name
            amendment_number = extract_amendment_number(filing.form)
            return cls(filing=filing, amendment_number=amendment_number, **parsed)
        return None

    @property
    def is_amendment(self) -> bool:
        """Check if this is an amendment filing"""
        return '/A' in self._filing.form

    @property
    def filing_date(self) -> date:
        """Get the filing date"""
        return self._filing.filing_date

    @property
    def total_shares(self) -> int:
        """
        Total beneficial ownership across all reporting persons.

        Uses the official SEC memberOfGroup field to determine if reporting
        persons are filing jointly or separately:
        - "a" = group member (joint filers) → take unique count
        - "b" or None = separate filers → sum all positions

        Also detects:
        - Undeclared joint filers: when all reporting persons have identical
          share amounts, they are joint filers regardless of member_of_group.
        - Hierarchical ownership: when percentages sum > 100.5%, this indicates
          a corporate control chain where parent entities report beneficial
          ownership of shares held through subsidiaries. In this case, the
          top of the hierarchy has the true total.

        Excludes shares flagged with is_aggregate_exclude_shares == True.
        """
        if not self.reporting_persons:
            return 0

        # Filter out shares excluded from aggregation
        included_persons = [p for p in self.reporting_persons
                           if not p.is_aggregate_exclude_shares]

        if not included_persons:
            return 0

        # Check for group members using official SEC indicator
        group_members = [p for p in included_persons
                        if p.member_of_group == "a"]

        if group_members:
            # Joint filers: all report the same shares
            # Take max in case of any data inconsistencies
            return max(p.aggregate_amount for p in group_members)

        # Check for hierarchical ownership: if percentages sum > 100.5%
        # this indicates overlapping beneficial ownership through control chain
        # (using 100.5% buffer to avoid false positives from rounding)
        total_pct = sum(p.percent_of_class for p in included_persons)
        if total_pct > 100.5:
            # Hierarchical structure: top of chain has the true total
            return max(p.aggregate_amount for p in included_persons)

        # Check for undeclared joint filers: identical values across all persons
        # When XML doesn't specify member_of_group but all persons report same position
        shares_list = [p.aggregate_amount for p in included_persons]
        unique_shares = set(shares_list)

        if len(unique_shares) == 1:
            # All persons have identical share counts - joint filers
            return shares_list[0]

        # Separate filers: sum all positions
        return sum(p.aggregate_amount for p in included_persons)

    @property
    def total_percent(self) -> float:
        """
        Total ownership percentage across all reporting persons.

        Uses the official SEC memberOfGroup field to determine if reporting
        persons are filing jointly or separately:
        - "a" = group member (joint filers) → take unique percentage
        - "b" or None = separate filers → sum all percentages

        Also detects:
        - Undeclared joint filers: when all reporting persons have identical
          percentages, they are joint filers regardless of member_of_group.
        - Hierarchical ownership: when percentages sum > 100.5%, this indicates
          a corporate control chain where parent entities report beneficial
          ownership of shares held through subsidiaries. In this case, the
          top of the hierarchy has the true percentage.

        Excludes shares flagged with is_aggregate_exclude_shares == True.
        """
        if not self.reporting_persons:
            return 0.0

        # Filter out shares excluded from aggregation
        included_persons = [p for p in self.reporting_persons
                           if not p.is_aggregate_exclude_shares]

        if not included_persons:
            return 0.0

        # Check for group members using official SEC indicator
        group_members = [p for p in included_persons
                        if p.member_of_group == "a"]

        if group_members:
            # Joint filers: all report the same percentage
            # Take max in case of any data inconsistencies
            return max(p.percent_of_class for p in group_members)

        # Check for hierarchical ownership: if percentages sum > 100.5%
        # this indicates overlapping beneficial ownership through control chain
        # (using 100.5% buffer to avoid false positives from rounding)
        total_pct = sum(p.percent_of_class for p in included_persons)
        if total_pct > 100.5:
            # Hierarchical structure: top of chain has the true percentage
            return max(p.percent_of_class for p in included_persons)

        # Check for undeclared joint filers: identical values across all persons
        # When XML doesn't specify member_of_group but all persons report same position
        percent_list = [p.percent_of_class for p in included_persons]
        unique_percents = set(percent_list)

        if len(unique_percents) == 1:
            # All persons have identical percentages - joint filers
            return percent_list[0]

        # Separate filers: sum all percentages, capped at 100%
        # (can exceed 100% slightly due to rounding in source data)
        return min(total_pct, 100.0)

    def __rich__(self):
        """Rich console rendering"""
        from edgar.beneficial_ownership.rendering import render_schedule13d
        return render_schedule13d(self)

    def __repr__(self):
        from edgar.richtools import repr_rich
        return repr_rich(self.__rich__())


class Schedule13G:
    """
    Schedule 13G - Passive Beneficial Ownership Report.

    Filed by institutional investors (mutual funds, ETFs, pensions) who
    acquire 5% or more of a company's stock for passive investment purposes
    without control intent. Has simpler disclosures than Schedule 13D.

    Example:
        filing = Filing(form='SCHEDULE 13G', ...)
        schedule = Schedule13G.from_filing(filing)
        print(schedule.issuer_info.name)
        print(schedule.reporting_persons[0].percent_of_class)
    """

    def __init__(
        self,
        filing,
        issuer_info: IssuerInfo,
        security_info: SecurityInfo,
        reporting_persons: List[ReportingPerson],
        items: Schedule13GItems,
        signatures: List[Signature],
        event_date: str,
        rule_designation: Optional[str] = None,
        amendment_number: Optional[int] = None
    ):
        self._filing = filing
        self.issuer_info = issuer_info
        self.security_info = security_info
        self.reporting_persons = reporting_persons
        self.items = items
        self.signatures = signatures
        self.event_date = event_date
        self.rule_designation = rule_designation
        self.amendment_number = amendment_number

    @staticmethod
    def parse_xml(xml: str) -> dict:
        """
        Parse Schedule 13G XML and return dict of all fields.

        Args:
            xml: XML content as string

        Returns:
            Dictionary with all parsed fields ready for Schedule13G constructor

        Raises:
            ValueError: If XML structure is invalid
        """
        soup = BeautifulSoup(xml, 'xml')
        root = soup.find('edgarSubmission')

        if not root:
            raise ValueError("Invalid XML: missing <edgarSubmission> root element")

        result = {}
        form_data = root.find('formData')

        # Parse cover page header
        cover = form_data.find('coverPageHeader')
        if not cover:
            raise ValueError("Invalid XML: missing <coverPageHeader>")

        # Security info
        result['security_info'] = SecurityInfo(
            title=child_text(cover, 'securitiesClassTitle') or '',
            cusip=''  # Will be filled from issuerInfo
        )

        result['event_date'] = child_text(cover, 'eventDateRequiresFilingThisStatement') or ''

        # Rule designation (note: parent is plural "Rules", child is singular "Rule")
        rules_parent_el = cover.find('designateRulesPursuantThisScheduleFiled')
        if rules_parent_el:
            result['rule_designation'] = child_text(rules_parent_el, 'designateRulePursuantThisScheduleFiled')
        else:
            result['rule_designation'] = None

        # Parse issuer info
        issuer_el = cover.find('issuerInfo')
        if issuer_el:
            address_el = issuer_el.find('issuerPrincipalExecutiveOfficeAddress')
            issuer_address = None
            if address_el:
                issuer_address = Address(
                    street1=child_text(address_el, 'street1'),
                    street2=child_text(address_el, 'street2'),
                    city=child_text(address_el, 'city'),
                    state_or_country=child_text(address_el, 'stateOrCountry'),
                    zipcode=child_text(address_el, 'zipCode')
                )

            cusip = child_text(issuer_el, 'issuerCusip') or ''
            result['issuer_info'] = IssuerInfo(
                cik=child_text(issuer_el, 'issuerCik') or '',
                name=child_text(issuer_el, 'issuerName') or '',
                cusip=cusip,
                address=issuer_address
            )

            # Update security_info cusip
            result['security_info'] = SecurityInfo(
                title=result['security_info'].title,
                cusip=cusip
            )

        # Parse reporting persons (different structure than 13D!)
        # In 13G, they're in coverPageHeaderReportingPersonDetails
        reporting_persons = []
        for person_el in form_data.find_all('coverPageHeaderReportingPersonDetails'):
            # Get shares info
            shares_el = person_el.find('reportingPersonBeneficiallyOwnedNumberOfShares')
            sole_voting = 0
            shared_voting = 0
            sole_disp = 0
            shared_disp = 0
            if shares_el:
                sole_voting = safe_int(child_text(shares_el, 'soleVotingPower'))
                shared_voting = safe_int(child_text(shares_el, 'sharedVotingPower'))
                sole_disp = safe_int(child_text(shares_el, 'soleDispositivePower'))
                shared_disp = safe_int(child_text(shares_el, 'sharedDispositivePower'))

            aggregate = child_text(person_el, 'reportingPersonBeneficiallyOwnedAggregateNumberOfShares')
            percent = child_text(person_el, 'classPercent')

            reporting_persons.append(ReportingPerson(
                cik='',  # Not provided in 13G cover page
                name=child_text(person_el, 'reportingPersonName') or '',
                citizenship=child_text(person_el, 'citizenshipOrOrganization') or '',
                sole_voting_power=sole_voting,
                shared_voting_power=shared_voting,
                sole_dispositive_power=sole_disp,
                shared_dispositive_power=shared_disp,
                aggregate_amount=safe_int(aggregate),
                percent_of_class=safe_float(percent),
                type_of_reporting_person=child_text(person_el, 'typeOfReportingPerson') or '',
                fund_type=None,
                comment=None,
                member_of_group=child_text(person_el, 'memberGroup'),  # Note: different element name than 13D!
                is_aggregate_exclude_shares=get_bool(child_text(person_el, 'isAggregateExcludeShares')),
                no_cik=get_bool(child_text(person_el, 'reportingPersonNoCIK'))
            ))
        result['reporting_persons'] = reporting_persons

        # Parse Items 1-10
        items_el = form_data.find('items')
        if items_el:
            # Item 1: Issuer
            item1_el = items_el.find('item1')
            item1_issuer_name = None
            item1_issuer_address = None
            if item1_el:
                item1_issuer_name = child_text(item1_el, 'issuerName')
                item1_issuer_address = child_text(item1_el, 'issuerPrincipalExecutiveOfficeAddress')

            # Item 2: Filer
            item2_el = items_el.find('item2')
            item2_filer_names = None
            item2_filer_addresses = None
            item2_citizenship = None
            if item2_el:
                item2_filer_names = child_text(item2_el, 'filingPersonName')
                item2_filer_addresses = child_text(item2_el, 'principalBusinessOfficeOrResidenceAddress')
                item2_citizenship = child_text(item2_el, 'citizenship')

            # Item 3
            item3_el = items_el.find('item3')
            item3_not_applicable = get_bool(child_text(item3_el, 'notApplicableFlag')) if item3_el else True

            # Item 4: Ownership
            item4_el = items_el.find('item4')
            item4_amount = None
            item4_percent = None
            item4_sole_voting = None
            item4_shared_voting = None
            item4_sole_disp = None
            item4_shared_disp = None
            if item4_el:
                item4_amount = child_text(item4_el, 'amountBeneficiallyOwned')
                item4_percent = child_text(item4_el, 'classPercent')
                shares_el = item4_el.find('numberOfSharesPersonHas')
                if shares_el:
                    item4_sole_voting = child_text(shares_el, 'solePowerOrDirectToVote')
                    item4_shared_voting = child_text(shares_el, 'sharedPowerOrDirectToVote')
                    item4_sole_disp = child_text(shares_el, 'solePowerOrDirectToDispose')
                    item4_shared_disp = child_text(shares_el, 'sharedPowerOrDirectToDispose')

            # Item 5
            item5_el = items_el.find('item5')
            item5_not_applicable = True
            item5_ownership = None
            if item5_el:
                item5_not_applicable = get_bool(child_text(item5_el, 'notApplicableFlag'))
                item5_ownership = child_text(item5_el, 'classOwnership5PercentOrLess')

            # Items 6-9 (typically not applicable)
            item6_el = items_el.find('item6')
            item6_not_applicable = get_bool(child_text(item6_el, 'notApplicableFlag')) if item6_el else True

            item7_el = items_el.find('item7')
            item7_not_applicable = get_bool(child_text(item7_el, 'notApplicableFlag')) if item7_el else True

            item8_el = items_el.find('item8')
            item8_not_applicable = get_bool(child_text(item8_el, 'notApplicableFlag')) if item8_el else True

            item9_el = items_el.find('item9')
            item9_not_applicable = get_bool(child_text(item9_el, 'notApplicableFlag')) if item9_el else True

            # Item 10: Certification
            item10_el = items_el.find('item10')
            item10_not_applicable = False
            item10_cert = None
            if item10_el:
                item10_not_applicable = get_bool(child_text(item10_el, 'notApplicableFlag'))
                item10_cert = child_text(item10_el, 'certifications')

            result['items'] = Schedule13GItems(
                item1_issuer_name=item1_issuer_name,
                item1_issuer_address=item1_issuer_address,
                item2_filer_names=item2_filer_names,
                item2_filer_addresses=item2_filer_addresses,
                item2_citizenship=item2_citizenship,
                item3_not_applicable=item3_not_applicable,
                item4_amount_beneficially_owned=item4_amount,
                item4_percent_of_class=item4_percent,
                item4_sole_voting=item4_sole_voting,
                item4_shared_voting=item4_shared_voting,
                item4_sole_dispositive=item4_sole_disp,
                item4_shared_dispositive=item4_shared_disp,
                item5_not_applicable=item5_not_applicable,
                item5_ownership_5pct_or_less=item5_ownership,
                item6_not_applicable=item6_not_applicable,
                item7_not_applicable=item7_not_applicable,
                item8_not_applicable=item8_not_applicable,
                item9_not_applicable=item9_not_applicable,
                item10_certification=item10_cert
            )
        else:
            result['items'] = Schedule13GItems()

        # Parse signatures
        signatures = []
        for sig_el in form_data.find_all('signatureInformation'):
            sig_details_el = sig_el.find('signatureDetails')
            if sig_details_el:
                signatures.append(Signature(
                    reporting_person=child_text(sig_el, 'reportingPersonName') or '',
                    signature=child_text(sig_details_el, 'signature') or '',
                    title=child_text(sig_details_el, 'title') or '',
                    date=child_text(sig_details_el, 'date') or ''
                ))
        result['signatures'] = signatures

        return result

    @classmethod
    def from_filing(cls, filing: 'Filing') -> Optional['Schedule13G']:
        """
        Create Schedule13G instance from a Filing object.

        Args:
            filing: Filing object with form 'SCHEDULE 13G', 'SCHEDULE 13G/A', 'SC 13G', or 'SC 13G/A'

        Returns:
            Schedule13G instance or None if no XML found

        Raises:
            AssertionError: If filing is not a Schedule 13G form
        """
        assert filing.form in ['SCHEDULE 13G', 'SCHEDULE 13G/A', 'SC 13G', 'SC 13G/A'], \
            f"Expected Schedule 13G form, got {filing.form}"

        xml = filing.xml()
        if xml:
            parsed = cls.parse_xml(xml)
            # Extract amendment number from filing form name
            amendment_number = extract_amendment_number(filing.form)
            return cls(filing=filing, amendment_number=amendment_number, **parsed)
        return None

    @property
    def is_amendment(self) -> bool:
        """Check if this is an amendment filing"""
        return '/A' in self._filing.form

    @property
    def filing_date(self) -> date:
        """Get the filing date"""
        return self._filing.filing_date

    @property
    def total_shares(self) -> int:
        """
        Total beneficial ownership across all reporting persons.

        Uses the official SEC memberGroup field to determine if reporting
        persons are filing jointly or separately:
        - "a" = group member (joint filers) → take unique count
        - "b" or None = separate filers → sum all positions

        Also detects:
        - Undeclared joint filers: when all reporting persons have identical
          share amounts, they are joint filers regardless of member_of_group.
        - Hierarchical ownership: when percentages sum > 100.5%, this indicates
          a corporate control chain where parent entities report beneficial
          ownership of shares held through subsidiaries. In this case, the
          top of the hierarchy has the true total.

        Excludes shares flagged with is_aggregate_exclude_shares == True.
        """
        if not self.reporting_persons:
            return 0

        # Filter out shares excluded from aggregation
        included_persons = [p for p in self.reporting_persons
                           if not p.is_aggregate_exclude_shares]

        if not included_persons:
            return 0

        # Check for group members using official SEC indicator
        group_members = [p for p in included_persons
                        if p.member_of_group == "a"]

        if group_members:
            # Joint filers: all report the same shares
            # Take max in case of any data inconsistencies
            return max(p.aggregate_amount for p in group_members)

        # Check for hierarchical ownership: if percentages sum > 100.5%
        # this indicates overlapping beneficial ownership through control chain
        # (using 100.5% buffer to avoid false positives from rounding)
        total_pct = sum(p.percent_of_class for p in included_persons)
        if total_pct > 100.5:
            # Hierarchical structure: top of chain has the true total
            return max(p.aggregate_amount for p in included_persons)

        # Check for undeclared joint filers: identical values across all persons
        # When XML doesn't specify member_of_group but all persons report same position
        shares_list = [p.aggregate_amount for p in included_persons]
        unique_shares = set(shares_list)

        if len(unique_shares) == 1:
            # All persons have identical share counts - joint filers
            return shares_list[0]

        # Separate filers: sum all positions
        return sum(p.aggregate_amount for p in included_persons)

    @property
    def total_percent(self) -> float:
        """
        Total ownership percentage across all reporting persons.

        Uses the official SEC memberGroup field to determine if reporting
        persons are filing jointly or separately:
        - "a" = group member (joint filers) → take unique percentage
        - "b" or None = separate filers → sum all percentages

        Also detects:
        - Undeclared joint filers: when all reporting persons have identical
          percentages, they are joint filers regardless of member_of_group.
        - Hierarchical ownership: when percentages sum > 100.5%, this indicates
          a corporate control chain where parent entities report beneficial
          ownership of shares held through subsidiaries. In this case, the
          top of the hierarchy has the true percentage.

        Excludes shares flagged with is_aggregate_exclude_shares == True.
        """
        if not self.reporting_persons:
            return 0.0

        # Filter out shares excluded from aggregation
        included_persons = [p for p in self.reporting_persons
                           if not p.is_aggregate_exclude_shares]

        if not included_persons:
            return 0.0

        # Check for group members using official SEC indicator
        group_members = [p for p in included_persons
                        if p.member_of_group == "a"]

        if group_members:
            # Joint filers: all report the same percentage
            # Take max in case of any data inconsistencies
            return max(p.percent_of_class for p in group_members)

        # Check for hierarchical ownership: if percentages sum > 100.5%
        # this indicates overlapping beneficial ownership through control chain
        # (using 100.5% buffer to avoid false positives from rounding)
        total_pct = sum(p.percent_of_class for p in included_persons)
        if total_pct > 100.5:
            # Hierarchical structure: top of chain has the true percentage
            return max(p.percent_of_class for p in included_persons)

        # Check for undeclared joint filers: identical values across all persons
        # When XML doesn't specify member_of_group but all persons report same position
        percent_list = [p.percent_of_class for p in included_persons]
        unique_percents = set(percent_list)

        if len(unique_percents) == 1:
            # All persons have identical percentages - joint filers
            return percent_list[0]

        # Separate filers: sum all percentages, capped at 100%
        # (can exceed 100% slightly due to rounding in source data)
        return min(total_pct, 100.0)

    @property
    def is_passive_investor(self) -> bool:
        """Check if this is a passive investor (13G are passive by definition)"""
        return True

    def __rich__(self):
        """Rich console rendering"""
        from edgar.beneficial_ownership.rendering import render_schedule13g
        return render_schedule13g(self)

    def __repr__(self):
        from edgar.richtools import repr_rich
        return repr_rich(self.__rich__())
