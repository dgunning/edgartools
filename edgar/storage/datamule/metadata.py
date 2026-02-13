"""
Datamule metadata mapping.

Maps fields from datamule's metadata.json to EdgarTools' FilingHeader
structures (FilingMetadata, Filer, CompanyInformation, etc.).
"""

from typing import Any, Dict

from edgar._party import Address
from edgar.sgml.sgml_header import (
    CompanyInformation,
    Filer,
    FilingHeader,
    FilingInformation,
)

__all__ = ['filing_header_from_metadata', 'filing_args_from_metadata']


def filing_header_from_metadata(metadata: Dict[str, Any]) -> FilingHeader:
    """
    Build a FilingHeader from a datamule metadata.json dict.

    Args:
        metadata: Parsed contents of metadata.json from a datamule tar.

    Returns:
        FilingHeader populated with the available metadata fields.
    """
    meta_dict = _build_filing_metadata_dict(metadata)
    filer = _build_filer(metadata)

    return FilingHeader(
        text='',
        filing_metadata=meta_dict,
        filers=[filer] if filer else [],
        reporting_owners=[],
        subject_companies=[],
    )


def filing_args_from_metadata(metadata: Dict[str, Any]) -> dict:
    """
    Extract common filing constructor args from datamule metadata.

    Returns a dict with keys matching Filing constructor parameters.
    """
    return {
        'accession_no': _get_accession(metadata),
        'form': metadata.get('form_type') or metadata.get('formType') or '',
        'filing_date': metadata.get('filing_date') or metadata.get('filingDate') or '',
        'cik': str(metadata.get('cik') or ''),
        'company': metadata.get('company_name') or metadata.get('companyName') or '',
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_accession(metadata: Dict[str, Any]) -> str:
    """Extract and normalize accession number."""
    accession = metadata.get('accession_number') or metadata.get('accessionNumber') or ''
    accession = accession.strip()
    if '-' not in accession and len(accession) == 18 and accession.isdigit():
        accession = f"{accession[:10]}-{accession[10:12]}-{accession[12:]}"
    return accession


def _build_filing_metadata_dict(metadata: Dict[str, Any]) -> Dict[str, str]:
    """Build a metadata dict (SGML-style keys) from datamule metadata fields."""
    meta_dict: Dict[str, str] = {}

    accession = _get_accession(metadata)
    if accession:
        meta_dict['ACCESSION NUMBER'] = accession

    form = metadata.get('form_type') or metadata.get('formType')
    if form:
        meta_dict['CONFORMED SUBMISSION TYPE'] = form

    filing_date = metadata.get('filing_date') or metadata.get('filingDate')
    if filing_date:
        # Normalize to YYYYMMDD
        meta_dict['FILED AS OF DATE'] = filing_date.replace('-', '')

    period_of_report = metadata.get('period_of_report') or metadata.get('periodOfReport')
    if period_of_report:
        meta_dict['CONFORMED PERIOD OF REPORT'] = period_of_report.replace('-', '')

    doc_count = metadata.get('document_count') or metadata.get('documentCount')
    if doc_count is not None:
        meta_dict['PUBLIC DOCUMENT COUNT'] = str(doc_count)

    return meta_dict


def _build_filer(metadata: Dict[str, Any]) -> Filer:
    """Build a Filer from datamule metadata."""
    cik = str(metadata.get('cik') or '')
    company_name = metadata.get('company_name') or metadata.get('companyName') or ''
    sic = str(metadata.get('sic') or metadata.get('standard_industrial_classification') or '')
    irs_number = str(metadata.get('irs_number') or metadata.get('irsNumber') or '')
    state_of_inc = metadata.get('state_of_incorporation') or metadata.get('stateOfIncorporation') or ''
    fiscal_year_end = metadata.get('fiscal_year_end') or metadata.get('fiscalYearEnd') or ''

    company_info = CompanyInformation(
        name=company_name,
        cik=cik,
        sic=sic,
        irs_number=irs_number,
        state_of_incorporation=state_of_inc,
        fiscal_year_end=fiscal_year_end,
    )

    form = metadata.get('form_type') or metadata.get('formType') or ''
    file_number = metadata.get('file_number') or metadata.get('fileNumber') or ''
    sec_act = metadata.get('sec_act') or metadata.get('act') or ''
    film_number = metadata.get('film_number') or metadata.get('filmNumber') or ''

    filing_info = FilingInformation(
        form=form,
        file_number=file_number,
        sec_act=sec_act,
        film_number=film_number,
    )

    # Addresses — datamule may or may not include them
    business_address = _build_address(metadata.get('business_address') or metadata.get('businessAddress'))
    mailing_address = _build_address(metadata.get('mailing_address') or metadata.get('mailingAddress'))

    return Filer(
        company_information=company_info,
        filing_information=filing_info,
        business_address=business_address,
        mailing_address=mailing_address,
    )


def _build_address(addr_data) -> Address:
    """Build an Address from a dict, or return an empty Address."""
    if not addr_data or not isinstance(addr_data, dict):
        return Address()
    return Address(
        street1=addr_data.get('street1') or addr_data.get('street_1'),
        street2=addr_data.get('street2') or addr_data.get('street_2'),
        city=addr_data.get('city'),
        state_or_country=addr_data.get('state') or addr_data.get('state_or_country'),
        zipcode=addr_data.get('zipcode') or addr_data.get('zip'),
    )
