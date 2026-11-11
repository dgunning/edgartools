"""
424B* EX-FILING FEES XBRL extraction.

Parses the EX-FILING FEES Inline XBRL exhibit attached to some 424B filings.
This exhibit provides machine-readable offering amounts, security types,
and fee calculations.

Coverage: ~43% of 424B2, ~23% of 424B5, ~7% of 424B3, 0% of 424B1/424B4.
Available from early 2022 onwards (SEC Rule 408).

See xbrl-filing-fees-extraction research for implementation details.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Optional

from lxml import etree

from edgar.xmltools import parse_xml_boolean

if TYPE_CHECKING:
    from edgar._filings import Filing

__all__ = ['extract_filing_fees_xbrl']

# iXBRL fact tags, matched case-insensitively on the local name so both the
# ix:nonNumeric / ix:nonFraction source casing and the libxml2-lowercased
# parse survive.
_IX_FACT_TAGS = ('nonnumeric', 'nonfraction')

# Flags whose value is an xs:boolean, read from the transformed value.
_BOOLEAN_FACTS = frozenset({'ffd:FnlPrspctsFlg'})


def _get_filing_fees_attachment(filing: 'Filing'):
    """Find the EX-FILING FEES attachment, returns None if not present."""
    for att in filing.attachments:
        doc_type = getattr(att, 'document_type', None)
        if doc_type == 'EX-FILING FEES':
            return att
    return None


def _local_name(tag) -> str:
    """Lowercased local name, stripping any namespace or ix: prefix."""
    if not isinstance(tag, str):  # comments / PIs have non-str tags
        return ''
    return tag.rsplit('}', 1)[-1].rsplit(':', 1)[-1].lower()


def _transformed_value(elem, display: str) -> Optional[str]:
    """The fact value its inline-XBRL ``format`` gives the display text.

    None when there is no format, or the registry does not implement it or
    rejects the text; the caller then keeps the display text.
    """
    format_attr = elem.get('format')
    if not format_attr:
        return None
    # Imported here: the registry lives in edgar.documents, whose package
    # import is not needed by the rest of this module.
    from edgar.documents.strategies.ixbrl_transforms import TransformError, apply_transform, expand_format
    try:
        return apply_transform(expand_format(elem, format_attr), display)
    except TransformError:
        return None


def _get_row_num(ctx: str) -> Optional[int]:
    """Extract 1-based row number from iXBRL context ID."""
    m = re.search(r'offrl_(\d+)', ctx)
    if m:
        return int(m.group(1))
    m = re.search(r'_(\d+)TypedMember', ctx)
    if m:
        return int(m.group(1))
    return None


_ROW_CONTEXT_PATTERNS = ('TypedMemberffdOfferingAxis', 'offrl_', 'offt_')
_SUMMARY_PREFIXES = ('ffd:Ttl', 'ffd:Net', 'ffd:Nrrtv')


def _parse_exhibit(fee_att):
    """Parse the exhibit's HTML, or None when it cannot be read."""
    try:
        content = fee_att.download()
        if isinstance(content, str):
            # lxml rejects unicode strings carrying an XML encoding
            # declaration, which iXBRL exhibits routinely include.
            content = content.encode('utf-8', 'replace')
        parser = etree.HTMLParser(recover=True, huge_tree=True)
        return etree.fromstring(content, parser)
    except Exception:
        return None


def _fact_value(elem, name: str, boolean_values: dict[str, str]) -> str:
    """The value of one inline fact, recording boolean flags as a side effect."""
    # itertext() preserves whitespace between nested inline elements;
    # the prior get_text(strip=True) mashed multi-span titles together
    # (e.g. "Series APerpetual Stride" -> "Series A Perpetual Stride").
    value = ''.join(elem.itertext()).strip()

    # The ``format`` attribute turns display text into the fact value
    # (GH #1681). Amounts keep their display text ("4,200,000,000"), which
    # callers parse, unless it has no digits to parse: ixt:fixed-zero over
    # an em dash means 0. Booleans are read from the transformed value,
    # because ixt:booleantrue may sit over any sentence.
    transformed = _transformed_value(elem, value)
    if transformed is None:
        return value
    if name in _BOOLEAN_FACTS:
        boolean_values.setdefault(name, transformed)
    if _local_name(elem.tag) == 'nonfraction' and not any(ch.isdigit() for ch in value):
        return transformed
    return value


def _collect_facts(root):
    """Sort the exhibit's facts into metadata, summary and per-row values."""
    metadata: dict[str, str] = {}
    summary: dict[str, str] = {}
    rows: dict[str, dict[str, str]] = {}
    boolean_values: dict[str, str] = {}
    seen_keys: set = set()

    for elem in root.iter():
        if _local_name(elem.tag) not in _IX_FACT_TAGS:
            continue
        name = elem.get('name', '')
        # The HTML parser lowercases attribute names, so contextRef -> contextref.
        ctx = elem.get('contextref') or ''
        if not name or parse_xml_boolean(elem.get('xsi:nil')):
            continue

        value = _fact_value(elem, name, boolean_values)

        key = (name, ctx)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        if any(p in ctx for p in _ROW_CONTEXT_PATTERNS):
            row_num = _get_row_num(ctx)
            row_key = str(row_num) if row_num is not None else ctx
            rows.setdefault(row_key, {})[name] = value
        elif name.startswith(_SUMMARY_PREFIXES):
            summary[name] = value
        else:
            metadata[name] = value

    return metadata, summary, rows, boolean_values


def _row_sort_key(k):
    try:
        return (0, int(k))
    except ValueError:
        return (1, k)


def _build_offering_rows(rows: dict[str, dict[str, str]]) -> list[dict]:
    offering_rows = []
    for row_key in sorted(rows.keys(), key=_row_sort_key):
        row = rows[row_key]
        offering_rows.append({
            'security_type': row.get('ffd:OfferingSctyTp'),
            'security_title': row.get('ffd:OfferingSctyTitl'),
            'max_aggregate_offering_price': row.get('ffd:MaxAggtOfferingPric'),
            'fee_rate': row.get('ffd:FeeRate'),
            'fee_amount': row.get('ffd:FeeAmt'),
            'fee_rule': row.get('ffd:Rule457rFlg') or row.get('ffd:Rule457oFlg')
                        or row.get('ffd:FeesOthrRuleFlg'),
        })
    return offering_rows


def extract_filing_fees_xbrl(filing: 'Filing') -> dict:
    """
    Extract structured data from EX-FILING FEES Inline XBRL exhibit.

    Returns dict with:
      - has_exhibit: bool
      - exhibit_url: str | None
      - form_type: str | None (e.g. 'S-3')
      - registration_file_number: str | None
      - total_offering_amount: str | None
      - total_fee_amount: str | None
      - offering_rows: list[dict] — per-row security type, title, amount, fee
      - is_final_prospectus: bool
    """
    fee_att = _get_filing_fees_attachment(filing)
    if not fee_att:
        return {'has_exhibit': False}

    root = _parse_exhibit(fee_att)
    if root is None:
        return {'has_exhibit': False}

    metadata, summary, rows, boolean_values = _collect_facts(root)

    is_final = parse_xml_boolean(
        boolean_values.get('ffd:FnlPrspctsFlg', metadata.get('ffd:FnlPrspctsFlg'))) is True

    return {
        'has_exhibit': True,
        'exhibit_url': fee_att.url,
        'form_type': metadata.get('ffd:FormTp'),
        'registration_file_number': metadata.get('ffd:RegnFileNb'),
        'total_offering_amount': summary.get('ffd:TtlOfferingAmt')
                                 or summary.get('ffd:NrrtvMaxAggtOfferingPric'),
        'total_fee_amount': summary.get('ffd:TtlFeeAmt'),
        'offering_rows': _build_offering_rows(rows),
        'is_final_prospectus': is_final,
    }
