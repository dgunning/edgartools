"""
Main classes for Schedule 13D and Schedule 13G beneficial ownership reports.

This module implements the parsing and representation of SEC Schedule 13D
and Schedule 13G filings using XML-based parsing.
"""
import re
from datetime import date
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from edgar._filings import Filing

from edgar._party import Address
from edgar.beneficial_ownership.models import IssuerInfo, ReportingPerson, Schedule13DItems, Schedule13GItems, SecurityInfo, Signature
from edgar.core import get_bool
from edgar.xmltools import child_text, find_all_elements, find_element, local_name
from edgar.xmltools import parse_xml as parse_xml_document

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


def _partial_from_header(filing: 'Filing') -> tuple:
    """
    Build ``(issuer_info, reporting_persons)`` from the SGML header.

    Used for Schedule 13D/G filings that predate the SEC structured-XML mandate
    (effective 2024-12-18) and therefore have no machine-readable XML. Only the
    identities are recoverable from the header — the subject company (issuer) and
    the filer(s)/reporting person(s). Beneficial-ownership numerics
    (shares, percentage, voting/dispositive power) are NOT in the header and are
    left as ``0`` / empty; callers must gate on ``has_structured_data``.

    Returns:
        Tuple of (IssuerInfo, List[ReportingPerson]). Falls back to filing-level
        company info when the header has no explicit subject company.
    """
    issuer_info = IssuerInfo(cik='', name='', cusip='')
    reporting_persons: List[ReportingPerson] = []

    header = None
    try:
        header = filing.header
    except Exception:
        header = None

    # Subject company -> issuer
    if header is not None:
        subjects = getattr(header, 'subject_companies', None) or []
        for subject in subjects:
            ci = getattr(subject, 'company_information', None)
            if ci and ci.name:
                issuer_info = IssuerInfo(cik=ci.cik or '', name=ci.name, cusip='')
                break

    # Fall back to the filing-level subject (the issuer is the entity the 13D/G is
    # filed against, which the index records as the filing's company).
    if not issuer_info.name:
        try:
            issuer_info = IssuerInfo(cik=str(filing.cik or ''), name=filing.company or '', cusip='')
        except Exception:
            pass

    # Filer(s) -> reporting person(s). Identity only; numerics unknown from header.
    if header is not None:
        for flr in (getattr(header, 'filers', None) or []):
            ci = getattr(flr, 'company_information', None)
            if ci and ci.name:
                reporting_persons.append(ReportingPerson(
                    cik=ci.cik or '',
                    name=ci.name,
                    citizenship='',
                    sole_voting_power=0,
                    shared_voting_power=0,
                    sole_dispositive_power=0,
                    shared_dispositive_power=0,
                    aggregate_amount=0,
                    percent_of_class=0.0,
                    type_of_reporting_person='',
                ))

    return issuer_info, reporting_persons


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
        amendment_number: Optional[int] = None,
        has_structured_data: bool = True
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
        # False for pre-2025 HTML-only filings parsed from the SGML header alone,
        # where beneficial-ownership numerics are unavailable. See _partial_from_header.
        self.has_structured_data = has_structured_data

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
            lxml.etree.XMLSyntaxError: If the argument carries no markup at all.
                Malformed markup is recovered from, as bs4 did — SEC's own XML is
                not always well-formed. An HTML error page recovers to an <html>
                root and so raises the ValueError above, by name.
        """
        # <edgarSubmission> is the document element, so this is a root check rather
        # than a search: a Schedule 13D carries the default namespace
        # http://www.sec.gov/edgar/schedule13D, which makes its tag read as
        # `{...}edgarSubmission` (edgartools-07lk.11.3).
        root = parse_xml_document(xml)
        if local_name(root) != 'edgarSubmission':
            raise ValueError("Invalid XML: missing <edgarSubmission> root element")

        result = {}
        form_data = find_element(root, 'formData')

        # Parse cover page header
        cover = find_element(form_data, 'coverPageHeader')
        if cover is None:
            raise ValueError("Invalid XML: missing <coverPageHeader>")

        # Security info
        result['security_info'] = SecurityInfo(
            title=child_text(cover, 'securitiesClassTitle') or '',
            cusip=''  # Will be filled from issuerInfo
        )

        result['date_of_event'] = child_text(cover, 'dateOfEvent') or ''
        result['previously_filed'] = get_bool(child_text(cover, 'previouslyFiledFlag'))

        # Parse issuer info
        issuer_el = find_element(cover, 'issuerInfo')
        if issuer_el is not None:
            # The address children are in the `com:` namespace while their parent is
            # in the form's own, so this is one of the documents the helpers' local
            # name fallback exists for. Never reach for a backend here.
            address_el = find_element(issuer_el, 'address')
            issuer_address = None
            if address_el is not None:
                issuer_address = Address(
                    street1=child_text(address_el, 'street1'),
                    street2=child_text(address_el, 'street2'),
                    city=child_text(address_el, 'city'),
                    state_or_country=child_text(address_el, 'stateOrCountry'),
                    zipcode=child_text(address_el, 'zipCode')
                )

            # Check for the legacy flat tag first
            cusip = child_text(issuer_el, 'issuerCUSIP')
            # If missing, check for the new nested SEC schema
            if not cusip:
                cusip = child_text(issuer_el, 'issuerCusipNumber')
            cusip = cusip or ''

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
        reporting_persons_el = find_element(form_data, 'reportingPersons')
        if reporting_persons_el is not None:
            for person_el in find_all_elements(reporting_persons_el, 'reportingPersonInfo'):
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
        items_el = find_element(form_data, 'items1To7')
        if items_el is not None:
            # Item 1: Security and Issuer
            item1_el = find_element(items_el, 'item1')
            item1_security_title = None
            item1_issuer_name = None
            item1_issuer_address = None
            if item1_el is not None:
                item1_security_title = child_text(item1_el, 'securityTitle')
                item1_issuer_name = child_text(item1_el, 'issuerName')
                # Build address string
                addr_el = find_element(item1_el, 'issuerPrincipalAddress')
                if addr_el is not None:
                    addr_parts = [
                        child_text(addr_el, 'street1'),
                        child_text(addr_el, 'city'),
                        child_text(addr_el, 'stateOrCountry'),
                        child_text(addr_el, 'zipCode')
                    ]
                    item1_issuer_address = ', '.join(p for p in addr_parts if p)

            # Item 2: Identity and Background
            item2_el = find_element(items_el, 'item2')
            item2_filing_persons = None
            item2_business_address = None
            item2_principal_occupation = None
            item2_convictions = None
            item2_citizenship = None
            if item2_el is not None:
                item2_filing_persons = child_text(item2_el, 'filingPersonName')
                item2_business_address = child_text(item2_el, 'principalBusinessAddress')
                item2_principal_occupation = child_text(item2_el, 'principalJob')
                item2_convictions = child_text(item2_el, 'convictionDescription')
                item2_citizenship = child_text(item2_el, 'citizenship')

            # Item 3: Source and Amount of Funds
            item3_el = find_element(items_el, 'item3')
            item3_source = child_text(item3_el, 'fundsSource') if item3_el is not None else None

            # Item 4: Purpose of Transaction (MOST IMPORTANT)
            item4_el = find_element(items_el, 'item4')
            item4_purpose = child_text(item4_el, 'transactionPurpose') if item4_el is not None else None

            # Item 5: Interest in Securities
            item5_el = find_element(items_el, 'item5')
            item5_percentage = None
            item5_shares = None
            item5_transactions = None
            item5_shareholders = None
            item5_date = None
            if item5_el is not None:
                item5_percentage = child_text(item5_el, 'percentageOfClassSecurities')
                item5_shares = child_text(item5_el, 'numberOfShares')
                item5_transactions = child_text(item5_el, 'transactionDesc')
                item5_shareholders = child_text(item5_el, 'listOfShareholders')
                item5_date = child_text(item5_el, 'date5PercentOwnership')

            # Item 6: Contracts, Arrangements
            item6_el = find_element(items_el, 'item6')
            item6_contracts = child_text(item6_el, 'contractDescription') if item6_el is not None else None

            # Item 7: Material to be Filed as Exhibits
            item7_el = find_element(items_el, 'item7')
            item7_exhibits = child_text(item7_el, 'filedExhibits') if item7_el is not None else None

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
        signature_info_el = find_element(form_data, 'signatureInfo')
        if signature_info_el is not None:
            for sig_person_el in find_all_elements(signature_info_el, 'signaturePerson'):
                sig_details_el = find_element(sig_person_el, 'signatureDetails')
                if sig_details_el is not None:
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
            Schedule13D instance. Fully populated when the filing has structured XML
            (SEC mandate, 2024-12-18 onward); a partial instance built from the SGML
            header (filer + issuer identities only, ``has_structured_data == False``)
            for older HTML-only filings.

        Raises:
            AssertionError: If filing is not a Schedule 13D form
        """
        assert filing.form in ['SCHEDULE 13D', 'SCHEDULE 13D/A', 'SC 13D', 'SC 13D/A'], \
            f"Expected Schedule 13D form, got {filing.form}"

        amendment_number = extract_amendment_number(filing.form)
        xml = filing.xml()
        if xml:
            parsed = cls.parse_xml(xml)
            return cls(filing=filing, amendment_number=amendment_number, **parsed)
        return cls.from_header(filing)

    @classmethod
    def from_header(cls, filing: 'Filing') -> 'Schedule13D':
        """
        Build a partial Schedule13D from the SGML header (no XML available).

        For Schedule 13D filings that predate the structured-XML mandate, only the
        filer and issuer identities are machine-readable. The returned instance has
        ``has_structured_data == False``; beneficial-ownership numerics are unavailable
        (``total_shares`` / ``total_percent`` return ``None``). Use ``filing.text()``
        or ``filing.markdown()`` for the full document text.
        """
        issuer_info, reporting_persons = _partial_from_header(filing)
        return cls(
            filing=filing,
            issuer_info=issuer_info,
            security_info=SecurityInfo(title='', cusip=''),
            reporting_persons=reporting_persons,
            items=Schedule13DItems(),
            signatures=[],
            date_of_event='',
            amendment_number=extract_amendment_number(filing.form),
            has_structured_data=False,
        )

    @property
    def is_amendment(self) -> bool:
        """Check if this is an amendment filing"""
        return '/A' in self._filing.form

    @property
    def filing_date(self) -> date:
        """Get the filing date"""
        return self._filing.filing_date

    @property
    def event_date(self) -> str:
        """Alias for ``date_of_event`` for API consistency with ``Schedule13G``."""
        return self.date_of_event

    @property
    def total_shares(self) -> Optional[int]:
        """
        Total beneficial ownership across all reporting persons.

        Within a single 13D filing, reporting persons always report overlapping
        beneficial ownership (group formations or control chains). Independent
        filers file separate forms. The correct aggregate is always max().

        Excludes shares flagged with is_aggregate_exclude_shares == True.

        Returns ``None`` when ``has_structured_data`` is False (pre-2025 HTML-only
        filing) — the share count is genuinely unavailable, not zero.
        """
        if not self.has_structured_data:
            return None

        if not self.reporting_persons:
            return 0

        included_persons = [p for p in self.reporting_persons
                           if not p.is_aggregate_exclude_shares]

        if not included_persons:
            return 0

        return max(p.aggregate_amount for p in included_persons)

    @property
    def total_percent(self) -> Optional[float]:
        """
        Total ownership percentage across all reporting persons.

        Within a single 13D filing, reporting persons always report overlapping
        beneficial ownership (group formations or control chains). Independent
        filers file separate forms. The correct aggregate is always max().

        Excludes shares flagged with is_aggregate_exclude_shares == True.

        Returns ``None`` when ``has_structured_data`` is False (pre-2025 HTML-only
        filing) — the percentage is genuinely unavailable, not zero.
        """
        if not self.has_structured_data:
            return None

        if not self.reporting_persons:
            return 0.0

        included_persons = [p for p in self.reporting_persons
                           if not p.is_aggregate_exclude_shares]

        if not included_persons:
            return 0.0

        return max(p.percent_of_class for p in included_persons)

    def to_context(self, detail: str = 'standard') -> str:
        """
        AI-optimized context string.

        Args:
            detail: 'minimal' (~100 tokens), 'standard' (~300 tokens), 'full' (~500+ tokens)
        """
        lines = []

        # === IDENTITY ===
        form_label = "SCHEDULE13D/A" if self.is_amendment else "SCHEDULE13D"
        lines.append(f"{form_label}: {self.issuer_info.name}")
        lines.append("")

        # === CORE METADATA ===
        lines.append(f"Filed: {self.filing_date}")
        if self.date_of_event:
            lines.append(f"Event Date: {self.date_of_event}")
        if self.security_info.title:
            lines.append(f"Security: {self.security_info.title}")
        if self.has_structured_data:
            lines.append(f"Ownership: {self.total_percent:.1f}% ({self.total_shares:,} shares)")
        else:
            lines.append("Ownership: unavailable (pre-2025 HTML filing)")

        # Filer(s)
        if self.reporting_persons:
            names = [p.name for p in self.reporting_persons[:3]]
            filer_str = ", ".join(names)
            if len(self.reporting_persons) > 3:
                filer_str += f" (+{len(self.reporting_persons) - 3} more)"
            lines.append(f"Filer: {filer_str}")

        # Loud notice when only header identities are available.
        if not self.has_structured_data:
            lines.append("")
            lines.append("NOTE: This filing predates the SEC structured-XML mandate "
                         "(2024-12-18); only filer/issuer identities are available. "
                         "Use filing.text() or filing.markdown() for the full document.")

        if detail == 'minimal':
            return "\n".join(lines)

        # === STANDARD ===
        if self.issuer_info.cik:
            lines.append(f"Issuer CIK: {self.issuer_info.cik}")
        if self.issuer_info.cusip:
            lines.append(f"CUSIP: {self.issuer_info.cusip}")

        # Per-person breakdown
        if len(self.reporting_persons) > 0:
            lines.append("")
            lines.append("REPORTING PERSONS:")
            for p in self.reporting_persons[:5]:
                if self.has_structured_data:
                    p_line = f"  {p.name}: {p.percent_of_class:.1f}% ({p.aggregate_amount:,} shares)"
                else:
                    p_line = f"  {p.name}"
                    if p.cik:
                        p_line += f" (CIK {p.cik})"
                if p.type_of_reporting_person:
                    p_line += f" [{p.type_of_reporting_person}]"
                lines.append(p_line)
            if len(self.reporting_persons) > 5:
                lines.append(f"  ... ({len(self.reporting_persons) - 5} more)")

        # Purpose (abbreviated)
        if self.items and self.items.item4_purpose_of_transaction:
            purpose = self.items.item4_purpose_of_transaction[:200]
            lines.append("")
            lines.append(f"PURPOSE: {purpose}")

        # Available actions
        lines.append("")
        lines.append("AVAILABLE ACTIONS:")
        lines.append("  .issuer_info               Subject company details")
        lines.append("  .reporting_persons          All filer details with voting/dispositive power")
        lines.append("  .items                      Narrative items 1-7")
        lines.append("  .total_shares               Aggregate beneficial ownership")
        lines.append("  .total_percent              Ownership percentage")
        lines.append("  .signatures                 Filing signatures")

        if detail == 'standard':
            return "\n".join(lines)

        # === FULL ===
        # Source of funds
        if self.items and self.items.item3_source_of_funds:
            lines.append("")
            lines.append(f"Source of Funds: {self.items.item3_source_of_funds[:150]}")

        # Voting/dispositive power detail for first person
        if self.reporting_persons and self.has_structured_data:
            p = self.reporting_persons[0]
            lines.append("")
            lines.append(f"VOTING/DISPOSITIVE POWER ({p.name}):")
            lines.append(f"  Sole Voting: {p.sole_voting_power:,}")
            lines.append(f"  Shared Voting: {p.shared_voting_power:,}")
            lines.append(f"  Sole Dispositive: {p.sole_dispositive_power:,}")
            lines.append(f"  Shared Dispositive: {p.shared_dispositive_power:,}")

        return "\n".join(lines)

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
        amendment_number: Optional[int] = None,
        has_structured_data: bool = True
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
        # False for pre-2025 HTML-only filings parsed from the SGML header alone,
        # where beneficial-ownership numerics are unavailable. See _partial_from_header.
        self.has_structured_data = has_structured_data

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
            lxml.etree.XMLSyntaxError: If the argument carries no markup at all.
                Malformed markup is recovered from, as bs4 did — SEC's own XML is
                not always well-formed. An HTML error page recovers to an <html>
                root and so raises the ValueError above, by name.
        """
        # As in Schedule13D.parse_xml: <edgarSubmission> is the document element, and
        # a Schedule 13G carries the default namespace
        # http://www.sec.gov/edgar/schedule13g — note the lower-case `g`, where the
        # 13D schema uses `D` (edgartools-07lk.11.3).
        root = parse_xml_document(xml)
        if local_name(root) != 'edgarSubmission':
            raise ValueError("Invalid XML: missing <edgarSubmission> root element")

        result = {}
        form_data = find_element(root, 'formData')

        # Parse cover page header
        cover = find_element(form_data, 'coverPageHeader')
        if cover is None:
            raise ValueError("Invalid XML: missing <coverPageHeader>")

        # Security info
        result['security_info'] = SecurityInfo(
            title=child_text(cover, 'securitiesClassTitle') or '',
            cusip=''  # Will be filled from issuerInfo
        )

        result['event_date'] = child_text(cover, 'eventDateRequiresFilingThisStatement') or ''

        # Rule designation (note: parent is plural "Rules", child is singular "Rule")
        rules_parent_el = find_element(cover, 'designateRulesPursuantThisScheduleFiled')
        if rules_parent_el is not None:
            result['rule_designation'] = child_text(rules_parent_el, 'designateRulePursuantThisScheduleFiled')
        else:
            result['rule_designation'] = None

        # Parse issuer info
        issuer_el = find_element(cover, 'issuerInfo')
        if issuer_el is not None:
            # As in the 13D: the address children are `com:`-namespaced.
            address_el = find_element(issuer_el, 'issuerPrincipalExecutiveOfficeAddress')
            issuer_address = None
            if address_el is not None:
                issuer_address = Address(
                    street1=child_text(address_el, 'street1'),
                    street2=child_text(address_el, 'street2'),
                    city=child_text(address_el, 'city'),
                    state_or_country=child_text(address_el, 'stateOrCountry'),
                    zipcode=child_text(address_el, 'zipCode')
                )

            # Check for the legacy flat tag first
            cusip = child_text(issuer_el, 'issuerCusip')
            # If missing, check for the new nested SEC schema
            if not cusip:
                cusip = child_text(issuer_el, 'issuerCusipNumber')
            cusip = cusip or ''

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
        for person_el in find_all_elements(form_data, 'coverPageHeaderReportingPersonDetails'):
            # Get shares info
            shares_el = find_element(person_el, 'reportingPersonBeneficiallyOwnedNumberOfShares')
            sole_voting = 0
            shared_voting = 0
            sole_disp = 0
            shared_disp = 0
            if shares_el is not None:
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
        items_el = find_element(form_data, 'items')
        if items_el is not None:
            # Item 1: Issuer
            item1_el = find_element(items_el, 'item1')
            item1_issuer_name = None
            item1_issuer_address = None
            if item1_el is not None:
                item1_issuer_name = child_text(item1_el, 'issuerName')
                item1_issuer_address = child_text(item1_el, 'issuerPrincipalExecutiveOfficeAddress')

            # Item 2: Filer
            item2_el = find_element(items_el, 'item2')
            item2_filer_names = None
            item2_filer_addresses = None
            item2_citizenship = None
            if item2_el is not None:
                item2_filer_names = child_text(item2_el, 'filingPersonName')
                item2_filer_addresses = child_text(item2_el, 'principalBusinessOfficeOrResidenceAddress')
                item2_citizenship = child_text(item2_el, 'citizenship')

            # Item 3
            item3_el = find_element(items_el, 'item3')
            item3_not_applicable = get_bool(child_text(item3_el, 'notApplicableFlag')) if item3_el is not None else True

            # Item 4: Ownership
            item4_el = find_element(items_el, 'item4')
            item4_amount = None
            item4_percent = None
            item4_sole_voting = None
            item4_shared_voting = None
            item4_sole_disp = None
            item4_shared_disp = None
            if item4_el is not None:
                item4_amount = child_text(item4_el, 'amountBeneficiallyOwned')
                item4_percent = child_text(item4_el, 'classPercent')
                shares_el = find_element(item4_el, 'numberOfSharesPersonHas')
                if shares_el is not None:
                    item4_sole_voting = child_text(shares_el, 'solePowerOrDirectToVote')
                    item4_shared_voting = child_text(shares_el, 'sharedPowerOrDirectToVote')
                    item4_sole_disp = child_text(shares_el, 'solePowerOrDirectToDispose')
                    item4_shared_disp = child_text(shares_el, 'sharedPowerOrDirectToDispose')

            # Item 5
            item5_el = find_element(items_el, 'item5')
            item5_not_applicable = True
            item5_ownership = None
            if item5_el is not None:
                item5_not_applicable = get_bool(child_text(item5_el, 'notApplicableFlag'))
                item5_ownership = child_text(item5_el, 'classOwnership5PercentOrLess')

            # Items 6-9 (typically not applicable)
            item6_el = find_element(items_el, 'item6')
            item6_not_applicable = get_bool(child_text(item6_el, 'notApplicableFlag')) if item6_el is not None else True

            item7_el = find_element(items_el, 'item7')
            item7_not_applicable = get_bool(child_text(item7_el, 'notApplicableFlag')) if item7_el is not None else True

            item8_el = find_element(items_el, 'item8')
            item8_not_applicable = get_bool(child_text(item8_el, 'notApplicableFlag')) if item8_el is not None else True

            item9_el = find_element(items_el, 'item9')
            item9_not_applicable = get_bool(child_text(item9_el, 'notApplicableFlag')) if item9_el is not None else True

            # Item 10: Certification
            item10_el = find_element(items_el, 'item10')
            item10_not_applicable = False
            item10_cert = None
            if item10_el is not None:
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
        for sig_el in find_all_elements(form_data, 'signatureInformation'):
            sig_details_el = find_element(sig_el, 'signatureDetails')
            if sig_details_el is not None:
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
            Schedule13G instance. Fully populated when the filing has structured XML
            (SEC mandate, 2024-12-18 onward); a partial instance built from the SGML
            header (filer + issuer identities only, ``has_structured_data == False``)
            for older HTML-only filings.

        Raises:
            AssertionError: If filing is not a Schedule 13G form
        """
        assert filing.form in ['SCHEDULE 13G', 'SCHEDULE 13G/A', 'SC 13G', 'SC 13G/A'], \
            f"Expected Schedule 13G form, got {filing.form}"

        amendment_number = extract_amendment_number(filing.form)
        xml = filing.xml()
        if xml:
            parsed = cls.parse_xml(xml)
            return cls(filing=filing, amendment_number=amendment_number, **parsed)
        return cls.from_header(filing)

    @classmethod
    def from_header(cls, filing: 'Filing') -> 'Schedule13G':
        """
        Build a partial Schedule13G from the SGML header (no XML available).

        For Schedule 13G filings that predate the structured-XML mandate, only the
        filer and issuer identities are machine-readable. The returned instance has
        ``has_structured_data == False``; beneficial-ownership numerics are unavailable
        (``total_shares`` / ``total_percent`` return ``None``). Use ``filing.text()``
        or ``filing.markdown()`` for the full document text.
        """
        issuer_info, reporting_persons = _partial_from_header(filing)
        return cls(
            filing=filing,
            issuer_info=issuer_info,
            security_info=SecurityInfo(title='', cusip=''),
            reporting_persons=reporting_persons,
            items=Schedule13GItems(),
            signatures=[],
            event_date='',
            amendment_number=extract_amendment_number(filing.form),
            has_structured_data=False,
        )

    @property
    def is_amendment(self) -> bool:
        """Check if this is an amendment filing"""
        return '/A' in self._filing.form

    @property
    def filing_date(self) -> date:
        """Get the filing date"""
        return self._filing.filing_date

    @property
    def date_of_event(self) -> str:
        """Alias for ``event_date`` for API consistency with ``Schedule13D``."""
        return self.event_date

    @property
    def total_shares(self) -> Optional[int]:
        """
        Total beneficial ownership across all reporting persons.

        Within a single 13G filing, reporting persons always report overlapping
        beneficial ownership (group formations or control chains). Independent
        filers file separate forms. The correct aggregate is always max().

        Excludes shares flagged with is_aggregate_exclude_shares == True.

        Returns ``None`` when ``has_structured_data`` is False (pre-2025 HTML-only
        filing) — the share count is genuinely unavailable, not zero.
        """
        if not self.has_structured_data:
            return None

        if not self.reporting_persons:
            return 0

        included_persons = [p for p in self.reporting_persons
                           if not p.is_aggregate_exclude_shares]

        if not included_persons:
            return 0

        return max(p.aggregate_amount for p in included_persons)

    @property
    def total_percent(self) -> Optional[float]:
        """
        Total ownership percentage across all reporting persons.

        Within a single 13G filing, reporting persons always report overlapping
        beneficial ownership (group formations or control chains). Independent
        filers file separate forms. The correct aggregate is always max().

        Excludes shares flagged with is_aggregate_exclude_shares == True.

        Returns ``None`` when ``has_structured_data`` is False (pre-2025 HTML-only
        filing) — the percentage is genuinely unavailable, not zero.
        """
        if not self.has_structured_data:
            return None

        if not self.reporting_persons:
            return 0.0

        included_persons = [p for p in self.reporting_persons
                           if not p.is_aggregate_exclude_shares]

        if not included_persons:
            return 0.0

        return max(p.percent_of_class for p in included_persons)

    @property
    def is_passive_investor(self) -> bool:
        """Check if this is a passive investor (13G are passive by definition)"""
        return True

    def to_context(self, detail: str = 'standard') -> str:
        """
        AI-optimized context string.

        Args:
            detail: 'minimal' (~100 tokens), 'standard' (~300 tokens), 'full' (~500+ tokens)
        """
        lines = []

        # === IDENTITY ===
        form_label = "SCHEDULE13G/A" if self.is_amendment else "SCHEDULE13G"
        lines.append(f"{form_label}: {self.issuer_info.name} (Passive)")
        lines.append("")

        # === CORE METADATA ===
        lines.append(f"Filed: {self.filing_date}")
        if self.event_date:
            lines.append(f"Event Date: {self.event_date}")
        if self.security_info.title:
            lines.append(f"Security: {self.security_info.title}")
        if self.has_structured_data:
            lines.append(f"Ownership: {self.total_percent:.1f}% ({self.total_shares:,} shares)")
        else:
            lines.append("Ownership: unavailable (pre-2025 HTML filing)")

        if self.reporting_persons:
            names = [p.name for p in self.reporting_persons[:3]]
            filer_str = ", ".join(names)
            if len(self.reporting_persons) > 3:
                filer_str += f" (+{len(self.reporting_persons) - 3} more)"
            lines.append(f"Filer: {filer_str}")

        # Loud notice when only header identities are available.
        if not self.has_structured_data:
            lines.append("")
            lines.append("NOTE: This filing predates the SEC structured-XML mandate "
                         "(2024-12-18); only filer/issuer identities are available. "
                         "Use filing.text() or filing.markdown() for the full document.")

        if detail == 'minimal':
            return "\n".join(lines)

        # === STANDARD ===
        if self.issuer_info.cik:
            lines.append(f"Issuer CIK: {self.issuer_info.cik}")
        if self.issuer_info.cusip:
            lines.append(f"CUSIP: {self.issuer_info.cusip}")
        if self.rule_designation:
            lines.append(f"Rule: {self.rule_designation}")

        # Per-person breakdown
        if len(self.reporting_persons) > 0:
            lines.append("")
            lines.append("REPORTING PERSONS:")
            for p in self.reporting_persons[:5]:
                if self.has_structured_data:
                    p_line = f"  {p.name}: {p.percent_of_class:.1f}% ({p.aggregate_amount:,} shares)"
                else:
                    p_line = f"  {p.name}"
                    if p.cik:
                        p_line += f" (CIK {p.cik})"
                if p.type_of_reporting_person:
                    p_line += f" [{p.type_of_reporting_person}]"
                lines.append(p_line)
            if len(self.reporting_persons) > 5:
                lines.append(f"  ... ({len(self.reporting_persons) - 5} more)")

        # Available actions
        lines.append("")
        lines.append("AVAILABLE ACTIONS:")
        lines.append("  .issuer_info               Subject company details")
        lines.append("  .reporting_persons          All filer details with voting/dispositive power")
        lines.append("  .items                      Structured items data")
        lines.append("  .total_shares               Aggregate beneficial ownership")
        lines.append("  .total_percent              Ownership percentage")
        lines.append("  .is_passive_investor        Always True for 13G")

        if detail == 'standard':
            return "\n".join(lines)

        # === FULL ===
        if self.reporting_persons and self.has_structured_data:
            p = self.reporting_persons[0]
            lines.append("")
            lines.append(f"VOTING/DISPOSITIVE POWER ({p.name}):")
            lines.append(f"  Sole Voting: {p.sole_voting_power:,}")
            lines.append(f"  Shared Voting: {p.shared_voting_power:,}")
            lines.append(f"  Sole Dispositive: {p.sole_dispositive_power:,}")
            lines.append(f"  Shared Dispositive: {p.shared_dispositive_power:,}")

        return "\n".join(lines)

    def __rich__(self):
        """Rich console rendering"""
        from edgar.beneficial_ownership.rendering import render_schedule13g
        return render_schedule13g(self)

    def __repr__(self):
        from edgar.richtools import repr_rich
        return repr_rich(self.__rich__())
