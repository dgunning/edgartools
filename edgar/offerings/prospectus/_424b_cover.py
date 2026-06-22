"""
424B* cover page field extraction.

Extracts 11 fields from the cover page of 424B* filings using
a combination of filing metadata and text regex patterns.

Validation results: 89% overall, near-zero true failures.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edgar._filings import Filing

__all__ = ['extract_cover_page_fields', 'extract_underwriting_from_text']


def extract_cover_page_fields(filing: 'Filing', document=None) -> dict:
    """
    Extract all cover page fields from a 424B* filing.

    Args:
        filing: Filing object (used for metadata and as fallback for parsing).
        document: Pre-parsed Document object. If provided, avoids re-parsing.

    Returns a dict with 11 fields suitable for CoverPageData(**result).
    """
    try:
        doc = document or filing.parse()
        text = doc.text() if doc else ''
    except Exception:
        text = ''
    cover = text[:15000]

    result: dict = {}

    # === METADATA FIELDS (from filing object, never parse text) ===
    result['company_name'] = filing.company

    try:
        file_nums = filing.header.file_numbers
        result['registration_number'] = file_nums[0] if file_nums else None
    except Exception:
        result['registration_number'] = None

    # === BOOLEAN FIELDS (fast keyword detection) ===
    result['is_supplement'] = bool(re.search(
        r'(?:^|\n)\s*PROSPECTUS\s+SUPPLEMENT', cover, re.IGNORECASE))

    result['is_preliminary'] = bool(re.search(
        r'Subject\s+to\s+Completion|not\s+complete\s+and\s+may\s+be\s+changed|PRELIMINARY\s+PROSPECTUS',
        cover[:3000], re.IGNORECASE))

    result['is_atm'] = bool(re.search(
        r'at[\-\s]+the[\-\s]+market\s+offering|equity\s+distribution\s+agreement|"at\s+the\s+market"',
        cover, re.IGNORECASE))

    # === STRUCTURED TEXT FIELDS ===

    # rule_number
    m = re.search(r'Filed\s+[Pp]ursuant\s+to\s+Rule\s+424\(b\)\((\d+)\)', cover, re.IGNORECASE)
    if not m:
        m = re.search(r'Rule\s+424\(b\)\((\d+)\)', cover, re.IGNORECASE)
    if m:
        result['rule_number'] = m.group(1)
    else:
        fm = re.search(r'424B(\d+)', filing.form)
        result['rule_number'] = fm.group(1) if fm else None

    # base_prospectus_date (supplements only)
    m = re.search(
        r'\(To\s+[Pp]rospectus(?:\s+[Ss]upplement)?\s+dated\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})\)',
        cover, re.IGNORECASE)
    result['base_prospectus_date'] = m.group(1) if m else None

    # security_description
    for p in [
        r'(\d[\d,]*\s+(?:Shares|Units|Notes?|Warrants?)\s+of\s+(?:Common|Preferred|Class [AB])?\s*(?:Stock|Shares)?(?:[^\n]{0,80}))',
        r'(Up\s+to\s+\$[\d,\.]+\s*(?:(?:million|billion|aggregate|of)[\s\w]*)?(?:Common\s+Stock|Class\s+[AB]\s+Common\s+Stock|Ordinary\s+Shares))',
        r'(\$[\d,\.]+\s+(?:aggregate principal amount|in principal)\s+[\w\s]+(?:Notes|Debentures))',
    ]:
        m = re.search(p, cover[:6000], re.IGNORECASE)
        if m:
            result['security_description'] = re.sub(r'\s+', ' ', m.group(1)[:120]).strip()
            break
    else:
        result['security_description'] = None

    # exchange_ticker (search wider area)
    for p in [
        r'under\s+the\s+symbol\s+["\u201c\u201d\u2018\u2019"]\s*([A-Z]{1,6})["\u201c\u201d\u2018\u2019".,]',
        r'under\s+the\s+(?:trading\s+)?symbol\s+["\u201c\u201d\u2018\u2019.]?\s*([A-Z]{2,6})\b',
    ]:
        m = re.search(p, text[:50000], re.IGNORECASE)
        if m:
            result['exchange_ticker'] = m.group(1)
            break
    else:
        result['exchange_ticker'] = None

    # offering_amount
    if re.search(r'\bexchange\s+offer\b', cover[:3000], re.IGNORECASE):
        result['offering_amount'] = 'exchange-offer'
    else:
        for p in [
            r'Up\s+to\s+\$([\d,\.]+(?:\s+(?:million|billion))?)\s*\n',
            r'aggregate\s+(?:offering\s+price|gross\s+proceeds)[^\$]*\$([\d,\.]+)',
            r'Total\s+\$([\d,\.]+)',
            r'^\$([\d,\.]+)\s*$',
        ]:
            m = re.search(p, cover[:8000], re.IGNORECASE | re.MULTILINE)
            if m:
                result['offering_amount'] = '$' + m.group(1)
                break
        else:
            result['offering_amount'] = None

    # offering_price
    if result['is_atm']:
        result['offering_price'] = 'at-the-market'
    elif re.search(r'\bexchange\s+offer\b', cover[:3000], re.IGNORECASE):
        result['offering_price'] = 'exchange-offer'
    elif result['is_preliminary']:
        result['offering_price'] = 'preliminary-TBD'
    else:
        for p in [
            r'Offering\s+price\s+\$\s*([\d,\.]+)',
            r'(?:Public\s+)?[Oo]ffering\s+[Pp]rice[^\$\n]{0,30}\$\s*([\d,\.]+)',
            r'Per\s+(?:Share|Note|Unit)[^\$\n]{0,30}\$\s*([\d,\.]+)',
        ]:
            m = re.search(p, text[:15000], re.IGNORECASE)
            if m:
                val = m.group(1).replace(',', '')
                try:
                    if float(val) >= 0.01:
                        result['offering_price'] = '$' + m.group(1)
                        break
                except ValueError:
                    continue
        else:
            if re.search(r'prevailing\s+market\s+price|at\s+various\s+prices', text, re.IGNORECASE):
                result['offering_price'] = 'market-price'
            else:
                result['offering_price'] = None

    return result


# ---------------------------------------------------------------------------
# Text-based underwriter / agent extraction
# ---------------------------------------------------------------------------

# Cover page role label patterns: "Sole Placement Agent\nTungsten Advisors".
# The name capture grabs the grid cell — the label's value plus up to two wrapped
# continuation lines, bounded by the blank line that separates the cell from the
# next content. A firm name in a cover grid often wraps ("Ladenburg\nThalmann");
# whether to stitch those lines is decided in extract_underwriting_from_text.
_CELL = r'([^\n]+(?:\n[^\n]+){0,2})'
_COVER_ROLE_PATTERNS = [
    (r'Sole\s+Book[-\s]Running\s+Manager\s*\n+' + _CELL, 'sole_book_runner'),
    (r'Joint\s+Book[-\s]Running\s+Managers?\s*\n+' + _CELL, 'joint_book_runners'),
    (r'Sole\s+Placement\s+Agent\s*\n+' + _CELL, 'sole_placement_agent'),
    (r'Placement\s+Agent\s*\n+' + _CELL, 'placement_agent'),
    (r'Sole\s+(?:Lead\s+)?Manager\s*\n+' + _CELL, 'sole_manager'),
    (r'(?:Sole\s+)?Underwriter\s*\n+' + _CELL, 'underwriter'),
    (r'Sales\s+Agent\s*\n+' + _CELL, 'sales_agent'),
]

# ATM sales agreement text patterns
_ATM_TEXT_PATTERNS = [
    r'(?:entered\s+into\s+an?\s+)?(?:Sales|Equity\s+Distribution|At[\s\-]+the[\s\-]+Market'
    r'(?:\s+Issuance)?)\s+Agreement[^"]{0,60}with\s+'
    r'([A-Z][^\n\(\)]{3,60}?(?:LLC|Inc\.|Corp\.|L\.P\.|&\s+Co\.))\s*[,\(]',
    r'through\s+([A-Z][^\n\(\)]{3,60}?(?:LLC|Inc\.|Corp\.|L\.P\.|&\s+Co\.))\s*[,\(]',
]

# Best-efforts / agency deals (registered directs, ATMs) name the agent inline in
# prose rather than in an allocation table: "We have engaged <Firm>, which we
# refer to as the placement agent", "engaged <Firm> (the 'placement agent')", or
# "Sales Agreement ... with <Firm> relating to ...". A firm name mid-sentence may
# carry a country parenthetical ("(UK)"), commas, and abbreviation periods, so the
# capture is bounded by the role/clause marker that follows it rather than by a
# fixed suffix list. is_plausible_underwriter_name guards the result downstream.
_AGENT_NAME = r"([A-Z][A-Za-z0-9.,&'()\- ]{3,60}?)"

_AGENCY_TEXT_PATTERNS = [
    # "engaged <Firm>, which we refer to as the placement agent" /
    # "engaged <Firm> (the 'placement agent')" / "engaged <Firm> as our sales agent"
    (re.compile(
        r'\bengaged\s+' + _AGENT_NAME +
        r'(?=\s*,?\s*(?:which\s+we\s+refer'
        r'|\(\s*(?:the\s+)?["“]?\s*(?:placement|sales|selling)'
        r'|(?:as|to\s+act\s+as)\s+(?:our|the)))', re.IGNORECASE),
     'placement_agent'),
    # "Sales Agreement ... with <Firm> relating to ..." / "... as sales agent"
    (re.compile(
        r'(?:Sales|Equity\s+Distribution|At[\s\-]the[\s\-]Market(?:\s+Issuance)?)'
        r'\s+Agreement[^.]{0,90}?\bwith\s+' + _AGENT_NAME +
        r'(?=\s+relating\b|\s+as\s+(?:our\s+)?sales)', re.IGNORECASE),
     'sales_agent'),
]


def _light_clean_agent_name(name: str) -> str:
    """Whitespace-normalize and trim trailing separators, keeping internal
    parentheticals ('(UK)') and abbreviation periods ('Ltd.')."""
    return re.sub(r'\s+', ' ', name).strip().strip(',').strip()


def _clean_agent_name(name: str) -> str:
    """Clean extracted agent name."""
    name = re.sub(r'\n', ' ', name)
    for suffix in [r'\s+structuring\s+advisor', r'\s+lead\s+manager',
                   r'\s+joint\s+book', r'\s+co-?manager', r'\s+\([^)]*\)']:
        name = re.sub(suffix, '', name, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', name).strip()


# Structured-note / debt covers label the distributor inline in a summary box —
# "Selling Agent:   BofAS" — rather than on its own line, and usually as a defined
# abbreviation ('BofA Securities, Inc. ("BofAS")'). The 2+ space gap is the
# table-cell layout: prose "selling agent ..." is lowercase (we stay
# case-sensitive) and the note-title banner is newline-separated, so both are
# excluded. The lead agent is the token before " and " (e.g. "BofAS and UBS").
_SELLING_AGENT_RE = re.compile(
    r'Selling\s+Agents?:?[ \t]{2,}'
    r"([A-Z][A-Za-z0-9&.' ]{1,48}?)"
    r'(?=\s{2,}|[.,;]|\sand\s|\sCUSIP|\sISIN|\n|$)')

# Defined-abbreviation pattern: '<Full Name> ("ABBR")'.
_ABBREV_DEF_RE = re.compile(
    r"([A-Z][A-Za-z0-9 ,.&'-]{3,45}?)\s*\(\s*[\"“]([A-Za-z&.']{2,10})[\"”]\s*\)")


def _resolve_abbreviation(name: str, text: str) -> str:
    """Expand a defined abbreviation to its full name.

    Structured-note covers reference the agent by a short tag ("BofAS") defined
    once as ``BofA Securities, Inc. ("BofAS")``. Resolve the tag to that full
    name; return ``name`` unchanged when it is not a defined abbreviation.
    """
    for m in _ABBREV_DEF_RE.finditer(text):
        if m.group(2).strip() == name:
            return m.group(1).strip()
    return name


def extract_underwriting_from_text(filing: 'Filing', document=None) -> list:
    """
    Extract underwriter/agent names from document text (non-table signals).

    Searches cover page (first 8000 chars) for:
    - Role label + agent name on next line ("Sole Placement Agent\\nTungsten")
    - ATM agreement text mentioning agent name

    Args:
        filing: Filing object (used as fallback for parsing).
        document: Pre-parsed Document object. If provided, avoids re-parsing.

    Returns list of dicts with keys: role, names, source.
    """
    try:
        doc = document or filing.parse()
        text = doc.text()
    except Exception:
        return []

    results = []
    cover = text[:8000]

    # Signal: Cover page role label + agent name
    for pattern, role in _COVER_ROLE_PATTERNS:
        m = re.search(pattern, cover, re.IGNORECASE)
        if m:
            block = m.group(1).strip()
            first_line = block.split('\n', 1)[0].strip()
            # Stitch wrapped continuation lines only when the first line is a
            # single bare word ("Ladenburg" -> "Ladenburg Thalmann"). A multi-word
            # first line is already a complete name — and could be the first firm
            # in a multi-line list — so keep just that line.
            raw = block if (first_line and ' ' not in first_line) else first_line
            name = _clean_agent_name(raw)
            if 2 < len(name) < 100 and not name.lower().startswith('table') \
                    and not name.startswith('The date'):
                results.append({
                    'role': role,
                    'names': [name],
                    'source': 'cover_page',
                })

    # Signal: ATM sales agreement pattern
    for pat in _ATM_TEXT_PATTERNS:
        m = re.search(pat, cover, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            if 3 < len(name) < 80:
                results.append({
                    'role': 'atm_sales_agent',
                    'names': [_clean_agent_name(name)],
                    'source': 'cover_text',
                })
                break

    # Signal: structured-note / debt cover "Selling Agent:" field. Searches the
    # full text (the summary box can sit past the 8000-char cover window) for the
    # specific labeled layout; the first match is the cover field.
    m = _SELLING_AGENT_RE.search(text)
    if m:
        agent = _resolve_abbreviation(_clean_agent_name(m.group(1)), text)
        if 1 < len(agent) < 80:
            results.append({
                'role': 'selling_agent',
                'names': [agent],
                'source': 'cover_selling_agent',
            })

    # Signal: best-efforts / agency deal — agent named inline in cover prose.
    # Tried after the labeled signals so a structured-note "Selling Agent" field
    # stays the lead; the first matching agency phrase wins.
    for pattern, role in _AGENCY_TEXT_PATTERNS:
        m = pattern.search(cover)
        if m:
            name = _light_clean_agent_name(m.group(1))
            if 3 < len(name) < 80:
                results.append({
                    'role': role,
                    'names': [name],
                    'source': 'cover_text',
                })
                break

    return results
