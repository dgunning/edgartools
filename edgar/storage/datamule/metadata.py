"""
Datamule metadata mapping.

Maps fields from datamule's metadata.json to EdgarTools' FilingHeader
structures (FilingMetadata, Filer, CompanyInformation, etc.).

Supports three metadata key conventions:
  - kebab-case with nested filer (real datamule tar format)
  - snake_case (synthetic/flat format)
  - camelCase (alternative flat format)
"""

from typing import Any, Dict, Optional

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
        'form': _get_form(metadata),
        'filing_date': _get_filing_date(metadata),
        'cik': _get_cik(metadata),
        'company': _get_company_name(metadata),
    }


# ---------------------------------------------------------------------------
# Internal helpers — field extraction with multi-format fallback
# ---------------------------------------------------------------------------

def _nested_get(metadata: Dict[str, Any], *keys: str) -> Optional[str]:
    """Walk a dotted key path through nested dicts, returning the first hit."""
    for key_path in keys:
        parts = key_path.split('.')
        obj = metadata
        for part in parts:
            if not isinstance(obj, dict):
                obj = None
                break
            obj = obj.get(part)
        if obj is not None:
            return str(obj)
    return None


def _get_accession(metadata: Dict[str, Any]) -> str:
    """Extract and normalize accession number."""
    accession = (
        _nested_get(metadata, 'accession-number', 'accession_number', 'accessionNumber')
        or ''
    )
    accession = accession.strip()
    if '-' not in accession and len(accession) == 18 and accession.isdigit():
        accession = f"{accession[:10]}-{accession[10:12]}-{accession[12:]}"
    return accession


def _get_form(metadata: Dict[str, Any]) -> str:
    """Extract form type from metadata."""
    return (
        _nested_get(metadata, 'type', 'filer.filing-values.form-type', 'form_type', 'formType')
        or ''
    )


def _get_filing_date(metadata: Dict[str, Any]) -> str:
    """Extract filing date, normalizing YYYYMMDD to YYYY-MM-DD."""
    raw = _nested_get(metadata, 'filing-date', 'filing_date', 'filingDate') or ''
    return _normalize_date(raw)


def _get_period(metadata: Dict[str, Any]) -> str:
    """Extract period of report, normalizing YYYYMMDD to YYYY-MM-DD."""
    raw = _nested_get(metadata, 'period', 'period_of_report', 'periodOfReport') or ''
    return _normalize_date(raw)


def _get_cik(metadata: Dict[str, Any]) -> str:
    """Extract CIK from metadata."""
    return _nested_get(metadata, 'filer.company-data.cik', 'cik') or ''


def _get_company_name(metadata: Dict[str, Any]) -> str:
    """Extract company name from metadata."""
    return (
        _nested_get(metadata, 'filer.company-data.conformed-name', 'company_name', 'companyName')
        or ''
    )


def _normalize_date(raw: str) -> str:
    """Convert YYYYMMDD to YYYY-MM-DD; pass through dates already containing dashes."""
    raw = raw.strip()
    if not raw:
        return ''
    if '-' in raw:
        return raw  # already formatted
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    return raw


def _build_filing_metadata_dict(metadata: Dict[str, Any]) -> Dict[str, str]:
    """Build a metadata dict (SGML-style keys) from datamule metadata fields."""
    meta_dict: Dict[str, str] = {}

    accession = _get_accession(metadata)
    if accession:
        meta_dict['ACCESSION NUMBER'] = accession

    form = _get_form(metadata)
    if form:
        meta_dict['CONFORMED SUBMISSION TYPE'] = form

    # Filing date — store as YYYYMMDD for SGML compatibility
    filing_date_raw = _nested_get(metadata, 'filing-date', 'filing_date', 'filingDate') or ''
    filing_date_raw = filing_date_raw.strip().replace('-', '')
    if filing_date_raw:
        meta_dict['FILED AS OF DATE'] = filing_date_raw

    # Period of report — store as YYYYMMDD
    period_raw = _nested_get(metadata, 'period', 'period_of_report', 'periodOfReport') or ''
    period_raw = period_raw.strip().replace('-', '')
    if period_raw:
        meta_dict['CONFORMED PERIOD OF REPORT'] = period_raw

    # Document count
    doc_count = _nested_get(metadata, 'public-document-count', 'document_count', 'documentCount')
    if doc_count is not None:
        meta_dict['PUBLIC DOCUMENT COUNT'] = doc_count

    # Date of filing date change
    date_change = _nested_get(metadata, 'date-of-filing-date-change')
    if date_change:
        meta_dict['DATE AS OF CHANGE'] = date_change.strip().replace('-', '')

    return meta_dict


def _build_filer(metadata: Dict[str, Any]) -> Filer:
    """Build a Filer from datamule metadata, supporting nested and flat formats."""
    # Company data — nested (real) or flat
    cik = _get_cik(metadata)
    company_name = _get_company_name(metadata)
    sic = (
        _nested_get(metadata, 'filer.company-data.assigned-sic', 'sic', 'standard_industrial_classification')
        or ''
    )
    irs_number = (
        _nested_get(metadata, 'filer.company-data.irs-number', 'irs_number', 'irsNumber')
        or ''
    )
    state_of_inc = (
        _nested_get(metadata, 'filer.company-data.state-of-incorporation', 'state_of_incorporation', 'stateOfIncorporation')
        or ''
    )
    fiscal_year_end = (
        _nested_get(metadata, 'filer.company-data.fiscal-year-end', 'fiscal_year_end', 'fiscalYearEnd')
        or ''
    )

    company_info = CompanyInformation(
        name=company_name,
        cik=cik,
        sic=sic,
        irs_number=irs_number,
        state_of_incorporation=state_of_inc,
        fiscal_year_end=fiscal_year_end,
    )

    # Filing info — nested or flat
    form = _get_form(metadata)
    file_number = (
        _nested_get(metadata, 'filer.filing-values.file-number', 'file_number', 'fileNumber')
        or ''
    )
    sec_act = (
        _nested_get(metadata, 'filer.filing-values.act', 'sec_act', 'act')
        or ''
    )
    film_number = (
        _nested_get(metadata, 'filer.filing-values.film-number', 'film_number', 'filmNumber')
        or ''
    )

    filing_info = FilingInformation(
        form=form,
        file_number=file_number,
        sec_act=sec_act,
        film_number=film_number,
    )

    # Addresses — nested filer paths or flat
    filer_dict = metadata.get('filer')
    if isinstance(filer_dict, dict):
        business_addr_data = filer_dict.get('business-address')
        mailing_addr_data = filer_dict.get('mail-address')
    else:
        business_addr_data = None
        mailing_addr_data = None

    business_address = _build_address(
        business_addr_data
        or metadata.get('business_address')
        or metadata.get('businessAddress')
    )
    mailing_address = _build_address(
        mailing_addr_data
        or metadata.get('mailing_address')
        or metadata.get('mailingAddress')
    )

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
        street1=addr_data.get('street1') or addr_data.get('street_1') or addr_data.get('STREET1'),
        street2=addr_data.get('street2') or addr_data.get('street_2') or addr_data.get('STREET2'),
        city=addr_data.get('city') or addr_data.get('CITY'),
        state_or_country=addr_data.get('state') or addr_data.get('state_or_country') or addr_data.get('STATE'),
        zipcode=addr_data.get('zipcode') or addr_data.get('zip') or addr_data.get('ZIP'),
    )
