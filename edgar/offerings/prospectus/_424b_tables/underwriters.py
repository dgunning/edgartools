"""Underwriter / placement-agent extraction from 424B tables.

Recognizes syndicate firm names (bank-name patterns), validates candidate names
against parser junk (``is_plausible_underwriter_name``), and pulls underwriter
rosters + allocations out of cover grids, allocation tables, and role listings.
"""

from __future__ import annotations

import re

from edgar.offerings.prospectus._424b_tables.helpers import (
    _WS_RE,
    _get_table_cells,
    _get_row_texts,
)


# Labels to skip when extracting underwriter names from allocation tables
_ALLOC_SKIP_LABELS = frozenset({'total', 'subtotal', ''})


# Bank name patterns for recognizing underwriter/agent names in tables
_BANK_PATTERNS = [
    r'\bj\.?\s*p\.?\s*morgan\b', r'\bjpmorgan\b',
    r'\bmorgan stanley\b', r'\bgoldman sachs\b',
    r'\bbofa securities\b', r'\bmerrill lynch\b', r'\bbank of america\b',
    r'\bcitigroup\b', r'\bcitibank\b', r'\bciti(?:group)?\s*global\b',
    r'\bbarclays\b', r'\bwells fargo\b', r'\bdeutsche bank\b',
    r'\bubs\s+(?:securities|investment)\b', r'\brbc\s+capital\b',
    r'\bbnp\s+paribas\b',
    r'\bpiper\s+sandler\b', r'\bjefferies\b', r'\bstifel\b',
    r'\bwilliam\s+blair\b', r'\bneedham\b', r'\bcanaccord\b',
    r'\bleerink\b', r'\bevercore\b', r'\bmizuho\b',
    r'\btd\s+(?:securities|cowen|global)\b', r'\btruist\b', r'\bsmbc\b',
    r'\bbmo\s+capital\b', r'\bmufg\b', r'\bguggenheim\b',
    r'\braymond\s+james\b', r'\boppenheimer\b', r'\bnomura\b',
    r'\bscotiabank\b', r'\bscotia\s+capital\b', r'\bloop\s+capital\b',
    r'\bladenburg\b', r'\bwainwright\b', r'\bh\.c\.\s+wainwright\b',
    r'\ba\.g\.p\.\b', r'\baegis\b', r'\both\s+capital\b',
    r'\bboustead\b', r'\bef\s+hutton\b', r'\btungsten\b',
    r'\bascendiant\b', r'\bthinkequity\b', r'\bcraig.hallum\b', r'\bbtig\b',
    r'\bu\.s\.\s+bancorp\b', r'\bcredit\s+agricole\b', r'\blloyds\b',
    r'\bnatwest\b', r'\bpnc\s+capital\b', r'\bregions\s+securities\b',
    r'\bcitizens\b', r'\bfifth\s+third\b',
    r'\bblackstone\s+(?:capital|securities)\b', r'\brothschild\b',
    r'\bcibc\b', r'\bkeybanc\b', r'\bsantander\b',
    r'\bsociete\s+generale\b', r'\bmacquarie\b',
    r'\bbny\s+(?:mellon|capital)\b', r'\bbank\s+of\s+montreal\b',
    # SPAC-specialist underwriters
    r'\bseaport\s+global\b', r'\bd\.?\s*boral\b',
    r'\bcohen\s+(?:&|and)\s+company\b', r'\bdominari\b',
    r'\bjett\s+capital\b', r'\bbenchmark\s+company\b',
    r'\bstonex\b', r'\bpolaris\s+advisory\b', r'\bwebull\b',
]


def _count_bank_hits(text: str) -> int:
    """Count how many distinct bank name patterns match in text."""
    return sum(1 for p in _BANK_PATTERNS if re.search(p, text, re.IGNORECASE))


def _clean_underwriter_name(name: str) -> str:
    """Clean extracted underwriter name."""
    name = re.sub(r'\n', ' ', name)
    for suffix in [r'\s+structuring\s+advisor', r'\s+lead\s+manager',
                   r'\s+joint\s+book', r'\s+co-?manager', r'\s+\([^)]*\)']:
        name = re.sub(suffix, '', name, flags=re.IGNORECASE)
    return _WS_RE.sub(' ',name).strip()


# Lowercase words allowed mid-name: connectors and corporate-form tokens.
_UW_NAME_LOWER_OK = {
    'and', 'of', 'the', 'de', 'für',
    'llc', 'lp', 'plc', 'sa', 'ag', 'na', 'nv', 'co', 'inc', 'ltd',
}

# Section headers that are never underwriter names (all-caps, so they survive the
# term-fragment check).
_UW_NAME_DENYLIST = {
    'table of contents', 'pricing supplement', 'prospectus supplement',
    'risk factors', 'summary information', 'where you can find more information',
    # Sentence fragments that leak as a single capitalized word.
    'our', 'we', 'the', 'this', 'these', 'those', 'it', 'its', 'such', 'any', 'all',
}


def _looks_like_term_fragment(name: str) -> bool:
    """True if ``name`` reads like a sentence/term fragment, not a firm name.

    Underwriter names are proper nouns — every word is capitalized (or a known
    connector/corporate-form token). A mid-name word that starts lowercase
    ('Upside participation rate', 'Notes due 2030', 'Linked to ...') is the
    signature of a structured-note term leaking from a cover table.
    """
    words = name.split()
    for i, word in enumerate(words):
        if i == 0:
            continue
        token = word.strip('.,&()').lower()
        if token and word.strip('.,&()')[0].islower() and token not in _UW_NAME_LOWER_OK:
            return True
    return False


def is_plausible_underwriter_name(name: str) -> bool:
    """Whether ``name`` looks like an underwriter/agent name rather than parser junk.

    424B2 structured-note and debt covers frequently leak whole legalese
    paragraphs, note titles, table-of-contents blobs, or pricing-term fragments
    into the name slot, plus lone bullets/punctuation. Reject a value that is
    multi-line, implausibly long (> 80 chars — a real firm name is short), has no
    alphabetic character, or reads like a lowercase term fragment.
    """
    if not name:
        return False
    if '\n' in name:
        return False
    stripped = name.strip()
    if len(stripped) < 2 or len(stripped) > 80:
        return False
    if not any(c.isalpha() for c in stripped):
        return False
    if stripped[-1] in ':;':
        # A firm name never ends in a colon/semicolon — this is a term label.
        return False
    if stripped.lower() in _UW_NAME_DENYLIST:
        return False
    return not _looks_like_term_fragment(stripped)


def extract_underwriting_from_tables(document) -> list:
    """
    Find underwriter/agent info from tables in a parsed Document.

    Uses three table patterns:
    - cover_grid: bank names as header cells (large-cap cover page layout)
    - allocation: 'Underwriter' header + bank names in rows
    - role_listing: first row is role label, second row is bank names

    Returns list of dicts with keys: type, names, role_label
    """
    ROLE_KEYWORDS = [
        'joint book', 'book-running', 'sole book', 'co-manager',
        'senior co-manager', 'lead manager', 'underwriter',
        'placement agent', 'sales agent', 'financial advisor',
        'structuring advisor', 'co-lead'
    ]
    results = []

    for i, table in enumerate(document.tables):
        headers_list = [c.text().strip() for h in table.headers for c in h if c.text().strip()]
        header_text = ' '.join(headers_list).lower()
        rows = _get_row_texts(table)
        row_cells = _get_table_cells(table)
        row_text = ' '.join(row_cells).lower()

        bank_hits_headers = _count_bank_hits(header_text)
        bank_hits_rows = _count_bank_hits(row_text)

        # Pattern A: Cover page grid — bank names as header cells
        is_cover_grid = bank_hits_headers >= 2 and len(table.rows) <= 2

        # Pattern B: Allocation table — 'Underwriter' in headers/first row + banks in rows
        has_underwriter_header = any(
            h.lower() in ('underwriter', 'underwriters')
            or 'number of shares' in h.lower()
            or 'principal amount' in h.lower()
            for h in headers_list
        )
        first_data_row = next((r for r in rows if r), None)
        has_row_based_header = False
        if first_data_row:
            # Check if any individual cell in the first row is a header label
            # (not "underwriter" buried in a paragraph about over-allotment, etc.)
            for cell in first_data_row:
                cell_stripped = cell.strip().lower()
                if len(cell_stripped) > 60:
                    continue  # Skip paragraph-length cells
                if cell_stripped in ('underwriter', 'underwriters', 'name of underwriter',
                                     'name of underwriters'):
                    has_row_based_header = True
                    break
                if 'number of shares' in cell_stripped or 'principal amount' in cell_stripped:
                    has_row_based_header = True
                    break

        # When the table explicitly labels itself (e.g. "Underwriters | Number of Shares"),
        # trust the structure even if firm names aren't in _BANK_PATTERNS.
        # This handles SPAC-specialist underwriters not in the whitelist.
        has_numeric_alloc = False
        if has_row_based_header and bank_hits_rows == 0:
            for row in rows[1:]:
                if len(row) >= 2 and re.search(r'\d', row[-1]):
                    has_numeric_alloc = True
                    break
        is_allocation = (
            (has_underwriter_header or has_row_based_header)
            and (bank_hits_rows >= 1 or (has_row_based_header and has_numeric_alloc))
            and len(table.rows) >= 2
        )

        # Pattern C: Role-label listing — role in row[0], banks in row[1]
        is_role_listing = False
        role_label = None
        if rows and len(rows) >= 2:
            first_row_text = ' '.join(rows[0]).lower()
            for kw in ROLE_KEYWORDS:
                if kw in first_row_text:
                    second_row = rows[1] if len(rows) > 1 else []
                    if _count_bank_hits(' '.join(second_row).lower()) >= 1:
                        is_role_listing = True
                        role_label = rows[0][0] if rows[0] else first_row_text
                        break

        if not (is_cover_grid or is_allocation or is_role_listing):
            continue

        table_type = (
            'cover_grid' if is_cover_grid else
            'role_listing' if is_role_listing else
            'allocation'
        )

        names = []
        allocations = []
        if is_cover_grid:
            names = [c for c in headers_list if _count_bank_hits(c.lower()) >= 1]
        elif is_allocation:
            # When table was identified structurally (row-based header + numeric data),
            # accept firm names even if they're not in _BANK_PATTERNS
            trust_structure = has_row_based_header and bank_hits_rows == 0
            start_row = 1 if has_row_based_header else 0
            for row in rows[start_row:]:
                if row and row[0]:
                    cell_lower = row[0].strip().lower()
                    if cell_lower in _ALLOC_SKIP_LABELS:
                        continue
                    # When trusting structure, reject cells that are too long
                    # to be a firm name (likely description text)
                    if trust_structure and len(cell_lower) > 80:
                        continue
                    if trust_structure or _count_bank_hits(cell_lower) >= 1:
                        clean = _clean_underwriter_name(row[0])
                        # The trust_structure branch accepts any row label (to catch
                        # SPAC-specialist firms missing from _BANK_PATTERNS), which
                        # lets a lock-up "Shares Eligible for Future Sale" table leak
                        # its header cell ('Earliest Date Available for Sale in the
                        # Public Market') as a name. Reject non-firm text (gh-868).
                        if not is_plausible_underwriter_name(clean):
                            continue
                        names.append(clean)
                        # Allocation amount is the last cell if numeric-looking
                        if len(row) >= 2 and re.fullmatch(r'[\d,.$\[\] ]+', row[-1].strip()):
                            allocations.append(row[-1])
                        else:
                            allocations.append(None)
        elif is_role_listing:
            if len(rows) > 1:
                for raw_name in rows[1]:
                    names.append(_clean_underwriter_name(raw_name))

        results.append({
            'table_index': i,
            'type': table_type,
            'names': names[:30],
            'allocations': allocations[:30],
            'role_label': role_label,
        })

    return results
