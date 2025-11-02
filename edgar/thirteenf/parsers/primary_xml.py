"""Parser for 13F primary document XML format."""

from datetime import datetime
from decimal import Decimal
from functools import lru_cache

from edgar._party import Address
from edgar.thirteenf.models import (
    FilingManager,
    OtherManager,
    CoverPage,
    SummaryPage,
    Signature,
    PrimaryDocument13F
)
from edgar.xmltools import child_text, find_element

__all__ = ['parse_primary_document_xml']


@lru_cache(maxsize=8)
def parse_primary_document_xml(primary_document_xml: str):
    """
    Parse the primary 13F XML document.

    Args:
        primary_document_xml: XML content of the primary document

    Returns:
        PrimaryDocument13F: Parsed primary document data
    """
    root = find_element(primary_document_xml, "edgarSubmission")
    # Header data
    header_data = root.find("headerData")
    filer_info = header_data.find("filerInfo")
    report_period = datetime.strptime(child_text(filer_info, "periodOfReport"), "%m-%d-%Y")

    # Form Data
    form_data = root.find("formData")
    cover_page_el = form_data.find("coverPage")

    report_calendar_or_quarter = child_text(form_data, "reportCalendarOrQuarter")
    report_type = child_text(cover_page_el, "reportType")

    # Filing Manager
    filing_manager_el = cover_page_el.find("filingManager")

    # Address
    address_el = filing_manager_el.find("address")
    address = Address(
        street1=child_text(address_el, "street1"),
        street2=child_text(address_el, "street2"),
        city=child_text(address_el, "city"),
        state_or_country=child_text(address_el, "stateOrCountry"),
        zipcode=child_text(address_el, "zipCode")
    )
    filing_manager = FilingManager(name=child_text(filing_manager_el, "name"), address=address)
    # Other managers
    other_manager_info_el = cover_page_el.find("otherManagersInfo")
    other_managers = [
        OtherManager(
            cik=child_text(other_manager_el, "cik"),
            name=child_text(other_manager_el, "name"),
            file_number=child_text(other_manager_el, "form13FFileNumber")
        )
        for other_manager_el in other_manager_info_el.find_all("otherManager")
    ] if other_manager_info_el else []

    # Summary Page
    summary_page_el = form_data.find("summaryPage")
    if summary_page_el:
        other_included_managers_count = child_text(summary_page_el,
                                                   "otherIncludedManagersCount")
        if other_included_managers_count:
            other_included_managers_count = int(other_included_managers_count)

        total_holdings = child_text(summary_page_el, "tableEntryTotal")
        if total_holdings:
            total_holdings = int(total_holdings)

        total_value = child_text(summary_page_el, "tableValueTotal")
        if total_value:
            total_value = Decimal(total_value)
    else:
        other_included_managers_count = 0
        total_holdings = 0
        total_value = 0

    # Signature Block
    signature_block_el = form_data.find("signatureBlock")
    signature = Signature(
        name=child_text(signature_block_el, "name"),
        title=child_text(signature_block_el, "title"),
        phone=child_text(signature_block_el, "phone"),
        city=child_text(signature_block_el, "city"),
        signature=child_text(signature_block_el, "signature"),
        state_or_country=child_text(signature_block_el, "stateOrCountry"),
        date=child_text(signature_block_el, "signatureDate")
    )

    parsed_primary_doc = PrimaryDocument13F(
        report_period=report_period,
        cover_page=CoverPage(
            filing_manager=filing_manager,
            report_calendar_or_quarter=report_calendar_or_quarter,
            report_type=report_type,
            other_managers=other_managers
        ),
        signature=signature,
        summary_page=SummaryPage(
            other_included_managers_count=other_included_managers_count or 0,
            total_holdings=total_holdings or 0,
            total_value=total_value or 0
        ),
        additional_information=child_text(cover_page_el, "additionalInformation")
    )

    return parsed_primary_doc
