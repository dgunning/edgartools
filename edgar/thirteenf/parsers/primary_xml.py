"""Parser for 13F primary document XML format."""

from datetime import datetime
from decimal import Decimal

from edgar._party import Address
from edgar.exceptions import ValidationError
from edgar.thirteenf.models import (
    AmendmentInfo,
    CoverPage,
    FilingManager,
    OtherManager,
    PrimaryDocument13F,
    Signature,
    SummaryPage,
)
from edgar.xmltools import child_text, find_all_elements, find_element, local_name
from edgar.xmltools import parse_xml as parse_xml_document

__all__ = ['parse_primary_document_xml']


def _require_element(parent, name: str):
    """Return the required child `name`, or say which one was missing.

    Six sites read a required element and raised the same sentence with a
    different noun in it (bead edgartools-35jj, tranche 1). Collapsing them
    into one helper is what makes the message worth improving: the caller now
    learns the element and that a namespace mismatch is the usual cause, which
    is the failure this parser actually sees (edgartools-07lk.11.3).

    `ValidationError` rather than `ParsingError` because it IS-A `ValueError`,
    so every `except ValueError:` written against the old raise keeps working.
    That additivity is the whole reason this conversion is not a 6.0 break.
    """
    element = find_element(parent, name)
    if element is None:
        raise ValidationError(
            f"Could not find <{name}> in the 13F primary document.",
            parameter="primary_document_xml",
            suggestions=[
                f"the document is missing <{name}>, or is not a 13F primary document",
                "13F primary documents carry a default namespace, so elements are "
                "matched on their local name — a namespace-qualified lookup finds "
                "nothing here",
            ],
        )
    return element


def parse_primary_document_xml(primary_document_xml: str):
    """
    Parse the primary 13F XML document.

    Args:
        primary_document_xml: XML content of the primary document

    Returns:
        PrimaryDocument13F: Parsed primary document data
    """
    # 13F primary documents carry a default namespace
    # (`xmlns="http://www.sec.gov/edgar/thirteenffiler"`) plus a second one for
    # `com:` elements, so every read below has to match on the LOCAL name. A plain
    # lxml `.//headerData` finds nothing here — silently (edgartools-07lk.11.3).
    root = parse_xml_document(primary_document_xml)
    if local_name(root) != "edgarSubmission":
        raise ValidationError(
            f"Expected an edgarSubmission document, got <{local_name(root)}>.",
            parameter="primary_document_xml",
            invalid_value=local_name(root),
            suggestions=["this is the 13F primary document parser; check the attachment "
                         "you passed is the primary document and not an information table"],
        )

    # Header data
    header_data = _require_element(root, "headerData")
    filer_info = _require_element(header_data, "filerInfo")
    report_period = datetime.strptime(child_text(filer_info, "periodOfReport") or "", "%m-%d-%Y")

    # Form Data
    form_data = _require_element(root, "formData")
    cover_page_el = _require_element(form_data, "coverPage")

    report_calendar_or_quarter = child_text(form_data, "reportCalendarOrQuarter")
    report_type = child_text(cover_page_el, "reportType")

    # Amendment metadata (GH #872). RESTATEMENT replaces the original; NEW HOLDINGS
    # only adds previously-confidential positions and must be unioned with the original.
    is_amendment = (child_text(cover_page_el, "isAmendment") or "").strip().lower() == "true"
    amendment_no_text = child_text(cover_page_el, "amendmentNo")
    try:
        amendment_number = int(amendment_no_text) if amendment_no_text else None
    except ValueError:
        amendment_number = None

    amendment_info = None
    amendment_info_el = find_element(cover_page_el, "amendmentInfo")
    if amendment_info_el is not None:
        conf_text = child_text(amendment_info_el, "confDeniedExpired")
        amendment_info = AmendmentInfo(
            amendment_type=child_text(amendment_info_el, "amendmentType"),
            conf_denied_expired=(conf_text.strip().lower() == "true") if conf_text else None,
            date_denied_expired=child_text(amendment_info_el, "dateDeniedExpired"),
            date_reported=child_text(amendment_info_el, "dateReported"),
            reason_for_non_confidentiality=child_text(amendment_info_el, "reasonForNonConfidentiality"),
        )

    # Filing Manager
    filing_manager_el = _require_element(cover_page_el, "filingManager")

    # Address
    address_el = _require_element(filing_manager_el, "address")
    address = Address(
        street1=child_text(address_el, "street1"),
        street2=child_text(address_el, "street2"),
        city=child_text(address_el, "city"),
        state_or_country=child_text(address_el, "stateOrCountry"),
        zipcode=child_text(address_el, "zipCode")
    )
    filing_manager = FilingManager(name=child_text(filing_manager_el, "name") or "", address=address)

    # Summary Page
    summary_page_el = find_element(form_data, "summaryPage")
    other_managers = []
    if summary_page_el is not None:
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

        # Issue #523: Parse other managers from summaryPage instead of coverPage
        other_manager_info_el = find_element(summary_page_el, "otherManagers2Info")
        if other_manager_info_el is not None:
            # New format: otherManagers2Info -> otherManager2 -> sequenceNumber + otherManager
            for other_manager_wrapper in find_all_elements(other_manager_info_el, "otherManager2"):
                seq_raw = child_text(other_manager_wrapper, "sequenceNumber")
                try:
                    sequence_number = int(seq_raw) if seq_raw is not None else None
                except ValueError:
                    sequence_number = None

                other_manager_el = find_element(other_manager_wrapper, "otherManager")
                if other_manager_el is not None:
                    other_managers.append(
                        OtherManager(
                            cik=child_text(other_manager_el, "cik") or "",
                            name=child_text(other_manager_el, "name") or "",
                            file_number=child_text(other_manager_el, "form13FFileNumber") or "",
                            sequence_number=sequence_number
                        )
                    )
    else:
        other_included_managers_count = 0
        total_holdings = 0
        total_value = 0

    # Signature Block
    signature_block_el = find_element(form_data, "signatureBlock")
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
            other_managers=[],  # Deprecated: other_managers now parsed from summaryPage
            is_amendment=is_amendment,
            amendment_number=amendment_number,
            amendment_info=amendment_info,
        ),
        signature=signature,
        summary_page=SummaryPage(
            other_included_managers_count=other_included_managers_count or 0,
            total_holdings=total_holdings or 0,
            total_value=total_value or 0,
            other_managers=other_managers or None  # Issue #523: Parse from summaryPage
        ),
        additional_information=child_text(cover_page_el, "additionalInformation")
    )

    return parsed_primary_doc
