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


# EX-FILING FEES (Exhibit 107) was created by the SEC's filing-fee modernization
# rule — adopted 2021-10-13, effective 2022-01-31 — so no filing made before that
# rule existed can carry one. This constant is deliberately set earlier than the
# effective date: a gate that is too early costs one wasted probe, while a gate
# that is too late would skip a real exhibit, so the error is pushed to the
# harmless side. It matters because probing a sibling is not cheap — see
# _probe_has_fee_exhibit.
_EX107_EARLIEST_FILING_DATE = "2021-10-01"


def _probe_has_fee_exhibit(filing: 'Filing') -> bool:
    """Whether ``filing`` carries a fee exhibit — at the cost of a full download.

    ``filing.attachments`` resolves through ``filing.sgml()``, which fetches the
    complete ``.txt`` submission, so asking this question about one sibling costs
    megabytes. Every caller below is written to ask it as few times as possible.
    """
    try:
        return _get_filing_fees_attachment(filing) is not None
    except Exception:
        log.debug("Could not read attachments for %s", filing.accession_no)
        return False


def _resolve_fee_source(filing: 'Filing'):
    """Find the fee-bearing registration for an amendment that omits its exhibit.

    Registration amendments (S-3/A, F-3/A, POS AM) routinely drop the fee
    exhibit because no additional fee is due — the fee was paid with the original
    registration, and the registered capacity still lives in that filing's
    Exhibit 107. Walk the file-number family and return the most recent
    fee-bearing registration filing dated at or before this one (falling back to
    the latest if all are later). Returns None when ``filing`` is not itself a
    registration form or no such source exists, so non-registration filings
    (424B takedowns, 10-Ks) keep their current None result.

    Both filters exist to keep the walk from downloading the family. Siblings
    filed before the Exhibit 107 regime are dropped without being probed at all,
    which removes the walk entirely for pre-2022 registrations — they have no
    exhibit anywhere in the family by construction, and their fee table is read
    from the inline body table instead. The survivors are then probed in
    priority order and the first hit wins, rather than probing every sibling and
    taking the maximum afterwards.
    """
    if not _is_registration_form(filing.form):
        return None
    try:
        related = filing.related_filings()
    except Exception:
        log.debug("related_filings() failed for %s", filing.accession_no)
        return None
    own_date = str(filing.filing_date)
    eligible = [rf for rf in related
                if rf.accession_no != filing.accession_no
                and _is_registration_form(rf.form)
                and str(rf.filing_date) >= _EX107_EARLIEST_FILING_DATE]
    if not eligible:
        return None

    # Latest at-or-before this filing wins; only if none of those carries an
    # exhibit does a later one, latest first. Probing in that order and stopping
    # at the first hit picks the same filing that taking the maximum over every
    # fee-bearing candidate did, without paying for the ones after it. Sorting is
    # stable, so same-date siblings keep their family order and ties resolve the
    # way max() resolved them.
    def _by_date_desc(filings):
        return sorted(filings, key=lambda rf: str(rf.filing_date), reverse=True)

    at_or_before = _by_date_desc(rf for rf in eligible if str(rf.filing_date) <= own_date)
    after = _by_date_desc(rf for rf in eligible if str(rf.filing_date) > own_date)
    for candidate in (*at_or_before, *after):
        if _probe_has_fee_exhibit(candidate):
            return candidate
    return None


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
