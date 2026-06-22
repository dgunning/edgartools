"""
Registration fee table extraction — orchestration.

Locates the EX-FILING FEES exhibit (or recovers it from an amendment's
file-number family, or falls back to the pre-EX-107 inline body table), parses
it via ``parsing``, and builds a ``RegistrationFeeTable`` from the result.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from edgar.offerings.prospectus._fee_table.parsing import (
    _parse_fee_table_html,
    _parse_inline_fee_table,
)

if TYPE_CHECKING:
    from edgar._filings import Filing

log = logging.getLogger(__name__)


def _get_filing_fees_attachment(filing: 'Filing'):
    """Find the EX-FILING FEES attachment, returns None if not present."""
    for att in filing.attachments:
        doc_type = getattr(att, 'document_type', None)
        if doc_type == 'EX-FILING FEES':
            return att
    return None


# Base registration forms that register capacity (and so carry — or whose
# file-number family carries — a fee exhibit). ASR variants and POS AM are
# handled separately in _is_registration_form.
_FEE_BEARING_BASE_FORMS = {'S-1', 'S-3', 'F-1', 'F-3', 'S-4', 'F-4', 'S-11'}


def _is_registration_form(form: Optional[str]) -> bool:
    """Whether ``form`` registers securities (vs. a takedown/notice/report)."""
    base = (form or '').replace('/A', '')
    return base in _FEE_BEARING_BASE_FORMS or base.endswith('ASR') or base == 'POS AM'


def _resolve_fee_source(filing: 'Filing'):
    """Find the fee-bearing registration for an amendment that omits its exhibit.

    Registration amendments (S-3/A, F-3/A, POS AM) routinely drop the fee
    exhibit because no additional fee is due — the fee was paid with the original
    registration, and the registered capacity still lives in that filing's
    Exhibit 107. Walk the file-number family and return the most recent
    fee-bearing registration filing dated at or before this one (falling back to
    the earliest if all are later). Returns None when ``filing`` is not itself a
    registration form or no such source exists, so non-registration filings
    (424B takedowns, 10-Ks) keep their current None result.
    """
    if not _is_registration_form(filing.form):
        return None
    try:
        related = filing.related_filings()
    except Exception:
        log.debug("related_filings() failed for %s", filing.accession_no)
        return None
    own_date = str(filing.filing_date)
    candidates = [rf for rf in related
                  if rf.accession_no != filing.accession_no
                  and _is_registration_form(rf.form)
                  and _get_filing_fees_attachment(rf) is not None]
    if not candidates:
        return None
    at_or_before = [rf for rf in candidates if str(rf.filing_date) <= own_date]
    return max(at_or_before or candidates, key=lambda rf: str(rf.filing_date))


def _data_to_fee_table(data: dict):
    """Build a RegistrationFeeTable from a parsed-data dict (shared by both the
    EX-107 exhibit path and the pre-2022 inline path)."""
    from edgar.offerings.prospectus import RegistrationFeeTable, FeeTableSecurity

    def _securities(rows):
        return [FeeTableSecurity(
            security_type=r.get('security_type'),
            security_title=r.get('security_title'),
            fee_rule=r.get('fee_rule'),
            amount_registered=r.get('amount_registered'),
            price_per_unit=r.get('price_per_unit'),
            max_aggregate_amount=r.get('max_aggregate_amount'),
            fee_rate=r.get('fee_rate'),
            fee_amount=r.get('fee_amount'),
        ) for r in rows]

    return RegistrationFeeTable(
        total_offering_amount=data.get('total_offering_amount'),
        net_fee_due=data.get('net_fee_due'),
        total_fees_previously_paid=data.get('total_fees_previously_paid'),
        securities=_securities(data.get('securities', [])),
        carry_forwards=_securities(data.get('carry_forwards', [])),
        has_carry_forward=data.get('has_carry_forward', False),
        fee_deferred=data.get('fee_deferred', False),
        exhibit_url=data.get('exhibit_url'),
    )


def _extract_inline_fee_table(filing: 'Filing'):
    """Fee table from a pre-EX-107 registration statement's inline body table."""
    try:
        html = filing.html()
    except Exception:
        log.debug("Failed to load primary document for %s", filing.accession_no)
        return None
    if not html:
        return None
    data = _parse_inline_fee_table(html, form=filing.form)
    if data['total_offering_amount'] is None and not data['fee_deferred']:
        return None
    return _data_to_fee_table(data)


def extract_registration_fee_table(filing: 'Filing'):
    """Extract the registration fee table from a filing's EX-FILING FEES exhibit.

    Works with any filing that has an EX-FILING FEES attachment:
    S-3, S-3ASR, F-3, S-1, S-4, and their amendments.

    Returns a RegistrationFeeTable or None if no exhibit found.

    Usage:
        from edgar import find
        filing = find(form="S-3", ticker="ADCT")
        fee_table = extract_registration_fee_table(filing)
        print(fee_table.total_offering_amount)  # e.g., 79157878.46
    """
    fee_att = _get_filing_fees_attachment(filing)
    if not fee_att:
        # A registration amendment may omit its fee exhibit; recover it from the
        # original registration in the same file-number family.
        source = _resolve_fee_source(filing)
        if source is not None:
            src_att = _get_filing_fees_attachment(source)
            if src_att is not None:
                fee_att, filing = src_att, source
    if not fee_att:
        # No EX-FILING FEES exhibit anywhere in the family. Pre-EX-107 (~pre-2022)
        # registration statements carry the fee table inline in the body instead;
        # fall back to that. Non-registration forms (424B takedowns, reports) have
        # no such table and keep returning None.
        if _is_registration_form(filing.form):
            return _extract_inline_fee_table(filing)
        return None

    try:
        content = fee_att.download()
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='replace')
    except Exception:
        log.debug("Failed to download fee exhibit for %s", filing.accession_no)
        return None

    exhibit_url = getattr(fee_att, 'url', None)
    data = _parse_fee_table_html(content, exhibit_url=exhibit_url)
    return _data_to_fee_table(data)
