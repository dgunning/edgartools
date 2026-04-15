"""
HTML extraction from DEF 14A proxy statements.

Extracts structured data from proxy statement HTML where XBRL is not available.
Each extractor operates on the filing's full text representation and uses
regex/text scanning rather than DOM traversal — SEC filing agents have enormous
formatting latitude, making DOM-based approaches fragile.

Lessons from edgartools-workers implementation (20-company eval):
- Proposals: 85% success rate (highest reliability)
- Section headers are NOT reliable DOM anchors — use text scanning
- Non-breaking spaces (\\u00a0) break regex — normalize first
- First occurrence of proposal text is often in TOC — retry later occurrences
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Literal, Optional

log = logging.getLogger(__name__)

__all__ = [
    'extract_voting_proposals', 'VotingProposal',
    'extract_ceo_pay_ratio', 'CEOPayRatio',
    'extract_summary_compensation', 'ExecutiveCompEntry',
    'extract_beneficial_ownership', 'BeneficialOwner',
    'extract_director_compensation', 'DirectorCompEntry',
]

# ── Types ────────────────────────────────────────────────────────────

ProposalType = Literal[
    'director_election',
    'say_on_pay',
    'say_on_pay_frequency',
    'auditor_ratification',
    'equity_plan',
    'shareholder_proposal',
    'company_proposal',
]


@dataclass(frozen=True)
class VotingProposal:
    """A single voting proposal from a proxy statement."""
    number: int
    description: str
    board_recommendation: Optional[str] = None  # 'FOR', 'AGAINST', 'ABSTAIN', or None
    proposal_type: ProposalType = 'company_proposal'


# ── Proposal type classification ─────────────────────────────────────

_PROPOSAL_TYPE_PATTERNS: list[tuple[re.Pattern, ProposalType]] = [
    (re.compile(r'elect(?:ion)?\s+(?:of\s+)?(?:\d+\s+)?director', re.I), 'director_election'),
    (re.compile(r'say[- ]on[- ]pay\s+frequency|frequency\s+of.*advisory\s+vote', re.I), 'say_on_pay_frequency'),
    (re.compile(r'say[- ]on[- ]pay|advisory\s+vote.*(?:executive\s+)?compensation|approve.*(?:executive\s+)?compensation', re.I), 'say_on_pay'),
    (re.compile(r'ratif(?:y|ication)\s+.*(?:account|audit|appoint)|appoint.*(?:account|audit)', re.I), 'auditor_ratification'),
    (re.compile(r'equity\s+(?:incentive\s+)?plan|stock\s+(?:incentive\s+)?plan|omnibus\s+incentive', re.I), 'equity_plan'),
    (re.compile(r'shareholder\s+proposal|stockholder\s+proposal', re.I), 'shareholder_proposal'),
]


def _classify_proposal(description: str) -> ProposalType:
    """Classify a proposal description into a type. Most specific patterns first."""
    for pattern, proposal_type in _PROPOSAL_TYPE_PATTERNS:
        if pattern.search(description):
            return proposal_type
    return 'company_proposal'


# ── Board recommendation extraction ──────────────────────────────────

_RECOMMENDATION_PATTERNS = [
    re.compile(r'board\s+(?:of\s+directors\s+)?recommends\s+(?:that\s+(?:you|shareholders?|stockholders?)\s+vote\s+|a\s+vote\s+)?["\u201c]?(FOR|AGAINST|ABSTAIN)\b', re.I),
    re.compile(r'(?:our|the)\s+board\s+recommends\s+["\u201c]?(FOR|AGAINST|ABSTAIN)\b', re.I),
    re.compile(r'recommendation[:\s]+["\u201c]?(FOR|AGAINST|ABSTAIN)\b', re.I),
    re.compile(r'vote\s+["\u201c]?(FOR|AGAINST|ABSTAIN)["\u201d]?\s+(?:this|the|each)\s+(?:proposal|nominee|director)', re.I),
    # Proxy card patterns — "FOR  Against  Abstain" column header followed by checkbox-like layout
    re.compile(r'\b(FOR)\s+Against\s+Abstain\b', re.I),
]


def _extract_recommendation(text: str) -> Optional[str]:
    """Extract board recommendation from text near a proposal heading."""
    # Normalize non-breaking spaces so \\s patterns match
    normalized = text.replace('\u00a0', ' ')
    for pattern in _RECOMMENDATION_PATTERNS:
        m = pattern.search(normalized)
        if m:
            return m.group(1).upper()
    return None


# ── Description cleaning ─────────────────────────────────────────────

def _clean_description(desc: str) -> str:
    """Clean raw proposal description text."""
    # Collapse multiple spaces
    desc = re.sub(r'\s{2,}', ' ', desc)
    # Remove trailing page numbers
    desc = re.sub(r'\s+\d{1,3}\s*$', '', desc)
    # Remove TOC dot leaders ("...... 42")
    desc = re.sub(r'\s*\.{2,}\s*\d+\s*$', '', desc)
    # Remove concatenated section numbers from TOC ("12Proposal", "38Executive")
    desc = re.sub(r'\d+Proposal\s+', '', desc, flags=re.I)
    # Clean concatenated page-number+word boundaries ("38Executive" → "Executive")
    desc = re.sub(r'\d+([A-Z][a-z])', r'\1', desc)

    desc = desc.strip()

    # Truncate at first natural sentence boundary if reasonable
    sentence_end = re.search(r'\.\s+[A-Z]', desc)
    if sentence_end and 20 < sentence_end.start() < 150:
        desc = desc[:sentence_end.start() + 1]

    # Hard truncate if still too long
    if len(desc) > 120:
        space_idx = desc.rfind(' ', 0, 120)
        desc = desc[:space_idx if space_idx > 40 else 120]

    return desc.strip()


# ── Main extraction function ─────────────────────────────────────────

# "Proposal 1", "Proposal No. 1", "PROPOSAL 1:", "Item 1", etc.
_PROPOSAL_PATTERN = re.compile(
    r'(?:proposal\s+(?:no\.?\s*)?|item\s+)(\d+)\s*[:\-\u2014\u2013.\s]+([^\n]{10,200})',
    re.I
)


def extract_voting_proposals(text: str) -> List[VotingProposal]:
    """
    Extract voting proposals from proxy statement text.

    Scans the full document text for "Proposal N" headings, extracts the
    description and board recommendation from surrounding context.
    Handles TOC vs body duplicates by retrying recommendation search
    across later occurrences of the same proposal.

    Args:
        text: Full text content of the proxy statement (from filing.text()
              or filing.markdown() or similar).

    Returns:
        List of VotingProposal, sorted by proposal number.
    """
    if not text:
        return []

    # Normalize whitespace: non-breaking spaces, zero-width spaces, and collapse runs
    text_normalized = text.replace('\u00a0', ' ').replace('\u200b', '').replace('\u200e', '')
    text_normalized = re.sub(r' {2,}', ' ', text_normalized)
    text_lower = text_normalized.lower()

    proposals: list[VotingProposal] = []
    seen_numbers: set[int] = set()
    seen_descriptions: set[str] = set()

    for match in _PROPOSAL_PATTERN.finditer(text_normalized):
        num = int(match.group(1))
        # Skip invalid: 0, already seen, or unreasonably high (page numbers in TOC)
        if not num or num in seen_numbers or num > 30:
            continue

        description = _clean_description(match.group(2))

        # Skip very short descriptions (likely TOC fragments)
        if len(description) < 15:
            continue

        # Skip descriptions that start with lowercase or connective words
        # (indicates mid-sentence match, not a heading)
        if description[0].islower() or re.match(r'^(?:was|is|are|has|the|a|an|and|or|but|requires?|shall|will|may)\s', description, re.I):
            # Try to find a better description from a later occurrence
            later_match = re.search(
                rf'proposal\s+(?:no\.?\s*)?{num}\s*[:\-\u2014\u2013.\s]+([^\n]{{15,200}})',
                text_normalized[match.end():],
                re.I
            )
            if later_match:
                description = _clean_description(later_match.group(1))
                if len(description) < 15 or description[0].islower():
                    continue
            else:
                continue

        # Skip duplicate descriptions (TOC + body both match)
        desc_key = description.lower()[:40]
        if desc_key in seen_descriptions:
            continue

        # Extract recommendation: search context after this match, and retry
        # at later occurrences (first match is often in TOC where recommendation
        # is absent — the actual recommendation is near the body section)
        recommendation = None
        search_pos = match.start()
        search_terms = [
            f'proposal {num}',
            f'proposal no. {num}',
            description.lower()[:30],
        ]

        for _attempt in range(4):
            context_end = min(len(text_normalized), search_pos + 5000)
            context = text_normalized[search_pos:context_end]
            recommendation = _extract_recommendation(context)
            if recommendation is not None:
                break

            # Find next occurrence for retry
            next_idx = -1
            for term in search_terms:
                idx = text_lower.find(term, search_pos + max(len(term), 10))
                if idx >= 0 and (next_idx < 0 or idx < next_idx):
                    next_idx = idx
            if next_idx < 0:
                break
            search_pos = next_idx

        seen_numbers.add(num)
        seen_descriptions.add(desc_key)
        proposals.append(VotingProposal(
            number=num,
            description=description,
            board_recommendation=recommendation,
            proposal_type=_classify_proposal(description),
        ))

    proposals.sort(key=lambda p: p.number)
    return proposals


# ══════════════════════════════════════════════════════════════════════
# CEO Pay Ratio Extractor
# ══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CEOPayRatio:
    """CEO pay ratio disclosure data."""
    ceo_compensation: Optional[int] = None
    median_employee_compensation: Optional[int] = None
    ratio: Optional[int] = None


def _parse_dollar_amount(text: str) -> Optional[int]:
    """Parse a dollar amount, stripping trailing footnote superscripts.

    SEC filings often embed footnote references directly after numbers
    (e.g., "$40,644,7231" where the trailing "1" is a footnote).
    We detect this by checking if the last digits make the number
    implausibly large relative to the magnitude.
    """
    # Remove dollar sign, commas, spaces
    cleaned = text.replace('$', '').replace(',', '').replace(' ', '').strip()
    if not cleaned or not cleaned[0].isdigit():
        return None
    try:
        value = int(cleaned)
    except ValueError:
        return None

    # Heuristic for footnote superscripts: SEC filings embed footnote references
    # directly after numbers (e.g., "$40,644,7231" where trailing "1" is a footnote).
    # Individual compensation is virtually never above $200M, so if stripping
    # the last digit brings us into a reasonable range, do it.
    if value > 200_000_000 and len(cleaned) > 7:
        stripped = int(cleaned[:-1])
        if stripped < 200_000_000:
            return stripped

    return value


def _find_pay_ratio_section(text: str) -> Optional[str]:
    """Find the pay ratio section, skipping TOC entries.

    The first occurrence of "pay ratio" is usually in the Table of Contents.
    The real section has "median" nearby. We scan forward until we find one
    with substantive content.
    """
    text_lower = text.lower()
    pos = 0
    while True:
        idx = text_lower.find('pay ratio', pos)
        if idx < 0:
            return None
        section = text[idx:idx + 3000]
        if 'median' in section.lower():
            return section
        pos = idx + 10


# ── Ratio patterns ──────────────────────────────────────────────────

_RATIO_PATTERNS = [
    # "ratio of these amounts is 533 to 1", "ratio was approximately 480 to 1"
    re.compile(r'ratio\s+(?:of\s+(?:those|these)\s+amounts\s+)?(?:is|was)\s+(?:approximately\s+)?(\d[\d,]*)\s*(?:to|:)\s*1', re.I),
    # "ratio...480 to 1" (broader)
    re.compile(r'ratio\s+.*?(\d[\d,]*)\s*(?:to|:)\s*1', re.I),
    # "125:1" standalone
    re.compile(r'(\d[\d,]*)\s*:\s*1(?=[\s.,;)]|$)', re.I),
    # "588 times that of" (CBRL style)
    re.compile(r'(\d[\d,]*)\s+times\s+that\s+of', re.I),
    # AMZN inverted: "1-to-51", "ratio of those amounts of 1-to-51"
    re.compile(r'1\s*-\s*to\s*-?\s*(\d[\d,]*)', re.I),
]

# ── CEO compensation patterns ───────────────────────────────────────

_CEO_COMP_PATTERNS = [
    # "compensation of our CEO was $X", "compensation of Mr. Dimon was $X"
    re.compile(r'compensation\s+of\s+(?:our\s+)?(?:CEO|Mr\.\s+\w+|Ms\.\s+\w+)\s+was\s+\$([\d,]+)', re.I),
    # "annual total compensation of the CEO was $X" (PG style)
    re.compile(r'(?:annual\s+total\s+)?compensation\s+of\s+(?:the\s+|our\s+)?CEO\s+was\s+\$([\d,]+)', re.I),
    # "annual total CEO compensation...was $X" / "is $X"
    re.compile(r'(?:annual\s+total\s+)?CEO\s+compensation\s+.*?(?:was|is)\s+\$([\d,]+)', re.I),
    # "CEO total compensation  $X" (table format, PBPB style)
    re.compile(r'CEO\s+total\s+compensation\s+\$([\d,]+)', re.I),
    # "total compensation of our CEO was $X"
    re.compile(r'total\s+compensation\s+of\s+(?:our\s+)?(?:CEO|Chief\s+Executive\s+Officer)\s+was\s+\$([\d,]+)', re.I),
    # "Mr./Ms. Name's annual total compensation...was $X" (KO/ETSY/AMZN style)
    re.compile(r'(?:Mr\.|Ms\.)\s+\w+[\u2019\']?s?\s+(?:\d{4}\s+)?(?:annual\s+)?total\s+compensation.*?(?:was|is)\s+\$([\d,]+)', re.I),
    # "compensation of our CEO...was $X" (with intervening text)
    re.compile(r'compensation\s+of\s+(?:our\s+)?CEO.*?was\s+\$([\d,]+)', re.I),
    # "Chief Executive Officer...was $X"
    re.compile(r'Chief\s+Executive\s+Officer.*?(?:was|is)\s+\$([\d,]+)', re.I),
]

# ── Median employee compensation patterns ────────────────────────────

_MEDIAN_COMP_PATTERNS = [
    # "median compensated employee...was $X" — constrain gap to avoid matching CEO line
    re.compile(r'median\s+(?:compensated\s+)?employee\s+(?:\([^)]*\)\s+)?was\s+\$([\d,]+)', re.I),
    # "compensation of our median compensated employee was $X"
    re.compile(r'compensation\s+of\s+(?:our\s+)?(?:estimated\s+)?median\s+(?:compensated\s+)?employee\s+was\s+\$([\d,]+)', re.I),
    # "median of the annual total compensation of all employees...was $X"
    re.compile(r'median\s+(?:of\s+the\s+)?(?:annual\s+total\s+)?compensation\s+of\s+all\s+(?:other\s+)?employees.*?was\s+\$([\d,]+)', re.I),
    # "median annual total compensation of all employees...was $X"
    re.compile(r'median\s+annual\s+total\s+compensation\s+of\s+all\s+employees.*?was\s+\$([\d,]+)', re.I),
    # "Median employee total compensation $X" (table format)
    re.compile(r'[Mm]edian\s+employee\s+total\s+compensation\s+\$([\d,]+)', re.I),
    # "median-paid employee...was $X" (JNJ style)
    re.compile(r'median[- ]paid\s+employee.*?was\s+\$([\d,]+)', re.I),
    # "median crew member...was $X" (FIVE style)
    re.compile(r'median\s+crew\s+member.*?was\s+\$([\d,]+)', re.I),
    # Fallback: "median" near "$X" within ~100 chars
    re.compile(r'median\s+(?:\w+\s+){0,10}?\$([\d,]+)', re.I),
]


def extract_ceo_pay_ratio(text: str) -> Optional[CEOPayRatio]:
    """
    Extract CEO pay ratio from proxy statement text.

    Finds the pay ratio section (skipping TOC), then extracts:
    - CEO annual total compensation
    - Median employee annual total compensation
    - The ratio (e.g., 533 to 1)

    Returns None if no pay ratio section found. Returns CEOPayRatio
    with None fields for any values that couldn't be extracted.

    Args:
        text: Full text content of the proxy statement.
    """
    if not text:
        return None

    # Normalize whitespace
    text = text.replace('\u00a0', ' ').replace('\u200b', '')

    section = _find_pay_ratio_section(text)
    if not section:
        return None

    # Collapse whitespace to handle line breaks in mid-sentence
    section = ' '.join(section.split())

    # Extract ratio
    ratio = None
    for pattern in _RATIO_PATTERNS:
        m = pattern.search(section)
        if m:
            ratio = int(m.group(1).replace(',', ''))
            break

    # Extract CEO compensation
    ceo_comp = None
    for pattern in _CEO_COMP_PATTERNS:
        m = pattern.search(section)
        if m:
            ceo_comp = _parse_dollar_amount(m.group(1))
            break

    # Extract median employee compensation
    median_comp = None
    for pattern in _MEDIAN_COMP_PATTERNS:
        m = pattern.search(section)
        if m:
            median_comp = _parse_dollar_amount(m.group(1))
            break

    # Sanity check: CEO comp should always be larger than median employee comp.
    # If they're swapped or equal, fix the assignment.
    if ceo_comp is not None and median_comp is not None:
        if ceo_comp < median_comp:
            ceo_comp, median_comp = median_comp, ceo_comp
        elif ceo_comp == median_comp:
            # Both patterns matched the same value — try to find the other
            # by looking for all dollar amounts in the section
            amounts = sorted(set(
                int(m.replace(',', ''))
                for m in re.findall(r'\$([\d,]+)', section)
                if int(m.replace(',', '')) > 0
            ), reverse=True)
            if len(amounts) >= 2:
                ceo_comp = amounts[0]
                median_comp = amounts[1]

    # Cross-check against ratio to detect footnote contamination.
    # If ceo_comp / median_comp is ~10x the stated ratio, the median
    # likely has an embedded footnote digit (e.g., $111,9052 → $1,119,052
    # when it should be $111,905).
    if ratio and ceo_comp and median_comp and median_comp > 0:
        computed_ratio = ceo_comp / median_comp
        if computed_ratio > 0 and (computed_ratio / ratio > 5 or ratio / computed_ratio > 5):
            # The ratio is way off — try stripping last digit from median
            median_stripped = int(str(median_comp)[:-1]) if median_comp > 10 else median_comp
            if median_stripped > 0:
                stripped_ratio = ceo_comp / median_stripped
                if 0.5 < stripped_ratio / ratio < 2.0:
                    median_comp = median_stripped

    return CEOPayRatio(
        ceo_compensation=ceo_comp,
        median_employee_compensation=median_comp,
        ratio=ratio,
    )


# ══════════════════════════════════════════════════════════════════════
# Summary Compensation Table Extractor
# ══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ExecutiveCompEntry:
    """One row of the Summary Compensation Table (one executive, one year)."""
    name: str
    title: str
    year: int
    salary: Optional[int] = None
    bonus: Optional[int] = None
    stock_awards: Optional[int] = None
    option_awards: Optional[int] = None
    non_equity_incentive: Optional[int] = None
    pension_change: Optional[int] = None
    other_compensation: Optional[int] = None
    total: Optional[int] = None


# ── Column classification ────────────────────────────────────────────

_SCT_COLUMN_PATTERNS: list[tuple[str, re.Pattern]] = [
    ('name', re.compile(r'name|principal\s+position', re.I)),
    ('year', re.compile(r'\byear\b', re.I)),
    ('stock_awards', re.compile(r'stock\s+award', re.I)),
    ('option_awards', re.compile(r'option\s+award', re.I)),
    ('non_equity_incentive', re.compile(r'non[- ]equity|incentive\s+plan', re.I)),
    ('pension_change', re.compile(r'pension|nqdc|nonqualified\s+deferred|change\s+in\s+pension', re.I)),
    ('other_compensation', re.compile(r'all\s+other|other\s+comp', re.I)),
    ('total', re.compile(r'\btotal\b', re.I)),
    ('salary', re.compile(r'\bsalary\b', re.I)),
    ('bonus', re.compile(r'\bbonus\b', re.I)),
]


def _classify_sct_column(header: str) -> Optional[str]:
    """Classify a column header to a compensation field. Most specific first."""
    for col_name, pattern in _SCT_COLUMN_PATTERNS:
        if pattern.search(header):
            return col_name
    return None


# ── Dollar parsing for table cells ───────────────────────────────────

_FOOTNOTE_RE = re.compile(r'(?:\(\d+\))+\s*$')
_STAR_RE = re.compile(r'\*+\s*$')
_DASH_RE = re.compile(r'^[\s\u2014\u2013\u2015\u2012\u2212\-]+$')
_ZERO_WIDTH_RE = re.compile(r'[\u200b\u00ad\ufeff]')


def _parse_comp_dollar(text: str) -> Optional[int]:
    """Parse a dollar amount from an SCT cell. Returns None for dashes/empty."""
    # Strip footnotes and zero-width chars
    cleaned = _FOOTNOTE_RE.sub('', text)
    cleaned = _STAR_RE.sub('', cleaned)
    cleaned = _ZERO_WIDTH_RE.sub('', cleaned).strip()
    if not cleaned or _DASH_RE.match(cleaned):
        return None

    # Handle accounting negatives: (1,234)
    negative = False
    if cleaned.startswith('(') and cleaned.endswith(')'):
        cleaned = cleaned[1:-1]
        negative = True

    # Remove $, commas, spaces
    cleaned = cleaned.replace('$', '').replace(',', '').replace(' ', '').strip()
    if not cleaned:
        return None

    try:
        value = round(float(cleaned))
        return -value if negative else value
    except ValueError:
        return None


# ── Name/title splitting ─────────────────────────────────────────────

_TITLE_KEYWORDS = [
    'officer', 'president', 'chairman', 'director', 'counsel', 'secretary',
    'treasurer', 'controller', 'ceo', 'cfo', 'coo', 'cto', 'clo', 'svp', 'evp',
    'vice president', 'general counsel', 'chief',
]

_TITLE_ABBREVIATIONS = {
    'chief executive officer': 'CEO',
    'chief financial officer': 'CFO',
    'chief operating officer': 'COO',
    'chief technology officer': 'CTO',
    'president and chief executive officer': 'President & CEO',
    'executive vice president': 'EVP',
    'senior vice president': 'SVP',
    'general counsel': 'General Counsel',
    'principal executive officer': 'PEO',
    'principal financial officer': 'PFO',
}


def _split_name_title(cell: str) -> tuple[str, str]:
    """Split 'Tim Cook, Chief Executive Officer' → ('Tim Cook', 'CEO')."""
    # Normalize whitespace
    cell = cell.replace('\xa0', ' ').replace('\u200b', '').strip()
    cell = re.sub(r'\s+', ' ', cell)

    # Try splitting on comma or newline
    for sep in [',', '\n']:
        idx = cell.find(sep)
        if idx == -1:
            continue
        before = cell[:idx].strip()
        after = cell[idx + 1:].strip()
        after_lower = after.lower()
        if any(kw in after_lower for kw in _TITLE_KEYWORDS) and before:
            # Abbreviate title
            for full, abbrev in sorted(_TITLE_ABBREVIATIONS.items(), key=lambda x: -len(x[0])):
                if full in after_lower:
                    return before, abbrev
            return before, after

    # No separator — check if title is concatenated (common in SEC filings)
    # "Tim CookChief Executive Officer" → split at case boundary before title keyword
    for kw in ['Chief ', 'President', 'Senior Vice', 'Executive Vice', 'General Counsel']:
        idx = cell.find(kw)
        if idx > 3:
            name = cell[:idx].strip()
            title_text = cell[idx:].strip()
            title_lower = title_text.lower()
            for full, abbrev in sorted(_TITLE_ABBREVIATIONS.items(), key=lambda x: -len(x[0])):
                if full in title_lower:
                    return name, abbrev
            return name, title_text

    return cell, ''


# ── SCT table finding ────────────────────────────────────────────────

def _find_sct_table(html: str):
    """Find the Summary Compensation Table in HTML.

    Returns the BeautifulSoup table element, or None if not found.

    Strategy: find heading elements containing "summary compensation table"
    that are NOT inside a <table> (to skip TOC entries), then examine
    subsequent tables for SCT-like column structure.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        log.warning("BeautifulSoup not available for SCT extraction")
        return None

    soup = BeautifulSoup(html, 'lxml')

    # Find the SCT section heading
    # Pass 1: headings NOT in tables (ideal — skips TOC)
    # Pass 2: headings IN tables (layout-table documents like JNJ, PG)
    heading_tag = None
    for allow_in_table in [False, True]:
        for tag in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'span']):
            text = tag.get_text(strip=True)
            if not text or 'summary compensation table' not in text.lower():
                continue
            if len(text) > 100:
                continue
            if tag.name == 'a' or tag.find_parent('a'):
                continue
            in_table = tag.find_parent('table') is not None
            if not allow_in_table and in_table:
                continue
            # In pass 2 (inside tables), require it to look like a heading
            # not a TOC entry — must NOT contain page numbers or "....." patterns
            if allow_in_table and in_table:
                if re.search(r'\d{2,3}\s*$', text):  # ends with page number
                    continue
                if '.....' in text:
                    continue
                # Must be a relatively short, standalone heading
                if len(text) > 60 and 'summary compensation table' not in text.lower()[:50]:
                    continue
            heading_tag = tag
            break
        if heading_tag:
            break

    if not heading_tag:
        return None

    # Search up to 10 tables after the heading for the best SCT candidate
    candidates = []
    for table in heading_tag.find_all_next('table', limit=10):
        rows = table.find_all('tr')
        if len(rows) < 3:
            continue

        # Check if this table has SCT-like columns
        all_cells = []
        for row in rows[:3]:
            for cell in row.find_all(['td', 'th']):
                text = cell.get_text(strip=True)
                if text and len(text) > 2:
                    all_cells.append(text)

        header_text = ' '.join(all_cells).lower()
        score = 0
        has_salary = 'salary' in header_text
        if has_salary:
            score += 3
        if 'total' in header_text:
            score += 2
        if 'year' in header_text:
            score += 1
        if 'stock' in header_text and 'award' in header_text:
            score += 2
        if 'name' in header_text or 'principal' in header_text:
            score += 1
        if 'bonus' in header_text:
            score += 1
        if 'option' in header_text:
            score += 1
        # Reject tables that look like Director Compensation (fees, not salary)
        if 'fees earned' in header_text or 'fees paid' in header_text:
            score = 0

        if score >= 4 and has_salary:
            candidates.append((table, score, len(rows)))

    if not candidates:
        return None

    # Pick best: highest score, then most rows
    candidates.sort(key=lambda x: (x[1], x[2]), reverse=True)
    return candidates[0][0]


def _extract_table_data(table) -> tuple[list[str], list[list[str]]]:
    """Extract headers and rows from an HTML table, handling colspan."""
    rows = table.find_all('tr')
    if not rows:
        return [], []

    grid = []
    for row in rows:
        cells = row.find_all(['td', 'th'])
        row_data = []
        for cell in cells:
            text = cell.get_text(strip=True)
            text = _ZERO_WIDTH_RE.sub('', text).strip()
            colspan = int(cell.get('colspan', 1) or 1)
            row_data.append(text)
            # Add empty cells for colspan
            for _ in range(colspan - 1):
                row_data.append('')
        grid.append(row_data)

    if not grid:
        return [], []

    # Find the header row: look for one containing 'Salary' or 'Year' or 'Total'
    header_row_idx = -1
    for i, row in enumerate(grid[:4]):
        row_text = ' '.join(row).lower()
        if ('salary' in row_text or 'year' in row_text) and 'total' in row_text:
            header_row_idx = i
            break

    if header_row_idx < 0:
        # Fallback: first row with multiple non-empty cells
        for i, row in enumerate(grid[:4]):
            non_empty = [c for c in row if c]
            if len(non_empty) >= 3:
                header_row_idx = i
                break

    if header_row_idx < 0:
        return [], grid

    headers = grid[header_row_idx]
    data_rows = grid[header_row_idx + 1:]

    return headers, data_rows


def extract_summary_compensation(html: str) -> Optional[List[ExecutiveCompEntry]]:
    """
    Extract Summary Compensation Table from proxy statement HTML.

    Finds the SEC-mandated SCT and extracts per-executive, per-year
    compensation data including salary, bonus, stock awards, option awards,
    non-equity incentive, pension/NQDC changes, other compensation, and total.

    Args:
        html: Raw HTML of the proxy statement filing.

    Returns:
        List of ExecutiveCompEntry, or None if the SCT was not found.
    """
    if not html:
        return None

    table_el = _find_sct_table(html)
    if table_el is None:
        return None

    headers, data_rows = _extract_table_data(table_el)
    if not data_rows:
        return None

    # Build column map from headers
    col_map: dict[str, int] = {}
    for i, header in enumerate(headers):
        col_type = _classify_sct_column(header)
        if col_type:
            col_map[col_type] = i

    # If header-based classification failed, try scanning first data rows
    if len(col_map) < 4:
        for row in data_rows[:2]:
            for i, cell in enumerate(row):
                col_type = _classify_sct_column(cell)
                if col_type and col_type not in col_map:
                    col_map[col_type] = i

    if len(col_map) < 4:
        return None

    name_col = col_map.get('name', 0)
    year_col = col_map.get('year', -1)

    def _get_dollar(row: list[str], col_name: str) -> Optional[int]:
        """Get a dollar value from a row, handling split-cell patterns."""
        idx = col_map.get(col_name, -1)
        if idx < 0 or idx >= len(row):
            return None
        val = _parse_comp_dollar(row[idx])
        if val is not None:
            return val
        # Split-cell: "$" in this cell, number in next
        if row[idx].strip() == '$' and idx + 1 < len(row):
            return _parse_comp_dollar('$' + row[idx + 1])
        # Try next cell if current is empty
        if not row[idx].strip() and idx + 1 < len(row):
            return _parse_comp_dollar(row[idx + 1])
        return None

    # Parse rows
    entries: list[ExecutiveCompEntry] = []
    current_name = ''
    current_title = ''

    for row in data_rows:
        # Check for name in name column
        if name_col < len(row) and row[name_col]:
            cell_text = row[name_col]
            if cell_text and not cell_text.startswith('(') and len(cell_text) > 2:
                name, title = _split_name_title(cell_text)
                if name and not any(kw in name.lower() for kw in ['total', 'footnote', 'note']):
                    current_name = name
                    current_title = title

        # Extract year
        year = 0
        if year_col >= 0 and year_col < len(row):
            try:
                year = int(re.sub(r'[^\d]', '', row[year_col])[:4])
            except (ValueError, IndexError):
                pass
            # Split-cell: try next column
            if (not year or year < 2000) and year_col + 1 < len(row):
                try:
                    year = int(re.sub(r'[^\d]', '', row[year_col + 1])[:4])
                except (ValueError, IndexError):
                    pass

        if not year or year < 2000 or year > 2100:
            continue
        if not current_name:
            continue

        entries.append(ExecutiveCompEntry(
            name=current_name,
            title=current_title,
            year=year,
            salary=_get_dollar(row, 'salary'),
            bonus=_get_dollar(row, 'bonus'),
            stock_awards=_get_dollar(row, 'stock_awards'),
            option_awards=_get_dollar(row, 'option_awards'),
            non_equity_incentive=_get_dollar(row, 'non_equity_incentive'),
            pension_change=_get_dollar(row, 'pension_change'),
            other_compensation=_get_dollar(row, 'other_compensation'),
            total=_get_dollar(row, 'total'),
        ))

    return entries if entries else None


# ══════════════════════════════════════════════════════════════════════
# Beneficial Ownership Table Extractor
# ══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class BeneficialOwner:
    """One row of the beneficial ownership table."""
    name: str
    holder_type: str  # '5pct_holder', 'director_officer', or 'group'
    shares: Optional[int] = None
    percent_of_class: Optional[float] = None


# ── Ownership column classification ──────────────────────────────────

_OWNERSHIP_COLUMN_PATTERNS: list[tuple[str, re.Pattern]] = [
    ('name', re.compile(r'name|beneficial\s+owner', re.I)),
    # Shares before percent — but patterns must not cross-match.
    # "Number of Shares" → shares; "Percentage of Class" → percent
    ('shares', re.compile(r'\bshare|\bnumber\b|\bamount\b', re.I)),
    ('percent', re.compile(r'percent|%\s*of|of\s+class', re.I)),
]


def _classify_ownership_column(header: str) -> Optional[str]:
    """Classify an ownership table column header."""
    for col_name, pattern in _OWNERSHIP_COLUMN_PATTERNS:
        if pattern.search(header):
            return col_name
    return None


# ── Share and percent parsing ────────────────────────────────────────

def _parse_shares(text: str) -> Optional[int]:
    """Parse a share count, stripping footnotes and zero-width chars."""
    cleaned = _FOOTNOTE_RE.sub('', text)
    cleaned = _STAR_RE.sub('', cleaned)
    cleaned = _ZERO_WIDTH_RE.sub('', cleaned).strip()
    if not cleaned or _DASH_RE.match(cleaned):
        return None
    cleaned = cleaned.replace(',', '').replace('$', '').replace(' ', '')
    try:
        return int(cleaned)
    except ValueError:
        return None


def _parse_percent(text: str) -> Optional[float]:
    """Parse a percentage. Handles '9.63%', 'less than 1%', '*'."""
    raw = text.strip()
    if not raw or _DASH_RE.match(raw):
        return None
    # "less than 1%" or "*" → 0.5 (conventional representation)
    if re.search(r'less\s+than\s+1\s*%', raw, re.I) or raw == '*':
        return 0.5
    cleaned = _FOOTNOTE_RE.sub('', raw)
    cleaned = _ZERO_WIDTH_RE.sub('', cleaned).strip()
    if not cleaned:
        return None
    cleaned = cleaned.replace('%', '').replace(',', '').strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


# ── Holder type classification ───────────────────────────────────────

_GROUP_RE = re.compile(
    r'directors?\s+and\s+(?:executive\s+)?officers?|'
    r'all\s+(?:named\s+)?executive\s+officers?\s+and\s+directors?|'
    r'as\s+a\s+group',
    re.I
)

_SECTION_HEADER_RE = re.compile(
    r'^(?:named\s+executive\s+officers?|'
    r'directors?\s+(?:and|&)\s+(?:director\s+)?nominees?|'
    r'5%\s+(?:stock)?holders?|'
    r'beneficial\s+owners?\s+of\s+5%|'
    r'principal\s+(?:stock)?holders?)',
    re.I
)


# ── Ownership table finding ──────────────────────────────────────────

_OWNERSHIP_HEADING_ANCHORS = [
    # Most specific first
    'security ownership of certain beneficial owners',
    'security ownership of certain',
    'stock ownership of certain beneficial owners',
    'beneficial ownership of common stock',
    'beneficial ownership of shares',
    'principal shareholders',
    'principal shareowners',
    'stock ownership information',
    'director and executive officer stock ownership',
    'security ownership of management',
    'beneficial ownership',
]

# Reject headings containing these (ownership guidelines, not the table)
_OWNERSHIP_HEADING_REJECTS = [
    'guidelines', 'requirements', 'policy', 'robust',
]


def _find_ownership_table(html: str):
    """Find the beneficial ownership table in HTML.

    Returns the BeautifulSoup table element, or None.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        log.warning("BeautifulSoup not available for ownership extraction")
        return None

    soup = BeautifulSoup(html, 'lxml')

    heading_tag = None
    for allow_in_table in [False, True]:
        for tag in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'span']):
            text = tag.get_text(strip=True)
            if not text or len(text) > 150:
                continue
            text_lower = text.lower()
            if not any(anchor in text_lower for anchor in _OWNERSHIP_HEADING_ANCHORS):
                continue
            # Reject "stock ownership guidelines" and similar
            if any(reject in text_lower for reject in _OWNERSHIP_HEADING_REJECTS):
                continue
            if tag.name == 'a' or tag.find_parent('a'):
                continue
            in_table = tag.find_parent('table') is not None
            if not allow_in_table and in_table:
                continue
            if allow_in_table and in_table:
                if re.search(r'\d{2,3}\s*$', text):
                    continue
                if '.....' in text:
                    continue
            heading_tag = tag
            break
        if heading_tag:
            break

    if not heading_tag:
        return None

    # Find the best ownership table candidate
    candidates = []
    for table in heading_tag.find_all_next('table', limit=10):
        rows = table.find_all('tr')
        if len(rows) < 3:
            continue

        all_cells = []
        for row in rows[:3]:
            for cell in row.find_all(['td', 'th']):
                text = cell.get_text(strip=True)
                if text and len(text) > 1:
                    all_cells.append(text)

        header_text = ' '.join(all_cells).lower()
        score = 0
        if 'name' in header_text or 'beneficial owner' in header_text:
            score += 2
        if 'share' in header_text or 'amount' in header_text or 'number' in header_text:
            score += 2
        if 'percent' in header_text or '% of' in header_text or 'of class' in header_text:
            score += 2
        if 'beneficially owned' in header_text:
            score += 1

        if score >= 3:
            candidates.append((table, score, len(rows)))

    if not candidates:
        return None

    candidates.sort(key=lambda x: (x[1], x[2]), reverse=True)
    return candidates[0][0]


def extract_beneficial_ownership(html: str) -> Optional[List[BeneficialOwner]]:
    """
    Extract beneficial ownership table from proxy statement HTML.

    Finds the "Security Ownership" section and extracts 5%+ holders,
    directors, and officers with their share counts and percentages.

    Args:
        html: Raw HTML of the proxy statement filing.

    Returns:
        List of BeneficialOwner, or None if the table was not found.
    """
    if not html:
        return None

    table_el = _find_ownership_table(html)
    if table_el is None:
        return None

    headers, data_rows = _extract_table_data(table_el)
    if not data_rows:
        return None

    # Build column map
    col_map: dict[str, int] = {}
    for i, header in enumerate(headers):
        col_type = _classify_ownership_column(header)
        if col_type:
            col_map[col_type] = i

    # Fallback: scan first data rows for column names
    if len(col_map) < 2:
        for row in data_rows[:2]:
            for i, cell in enumerate(row):
                col_type = _classify_ownership_column(cell)
                if col_type and col_type not in col_map:
                    col_map[col_type] = i

    name_col = col_map.get('name', 0)
    shares_col = col_map.get('shares', -1)
    percent_col = col_map.get('percent', -1)

    if shares_col < 0 and percent_col < 0:
        return None

    owners: list[BeneficialOwner] = []
    current_section = '5pct'  # Assume 5%+ holders listed first

    for row in data_rows:
        if name_col >= len(row):
            continue
        name_cell = _ZERO_WIDTH_RE.sub('', row[name_col]).strip()
        name_cell = _FOOTNOTE_RE.sub('', name_cell).strip()
        if not name_cell or len(name_cell) < 2:
            continue

        # Check for sub-section headers
        if _SECTION_HEADER_RE.match(name_cell):
            if re.search(r'director|officer|nominee|executive', name_cell, re.I):
                current_section = 'insider'
            continue

        # Check for group summary row
        if _GROUP_RE.search(name_cell):
            shares = _parse_shares_with_adjacent(row, shares_col) if shares_col >= 0 else None
            pct = _parse_percent_with_adjacent(row, percent_col) if percent_col >= 0 else None
            if shares is not None or pct is not None:
                owners.append(BeneficialOwner(
                    name=name_cell, holder_type='group',
                    shares=shares, percent_of_class=pct,
                ))
            continue

        # Parse data
        shares = _parse_shares_with_adjacent(row, shares_col) if shares_col >= 0 else None
        pct = _parse_percent_with_adjacent(row, percent_col) if percent_col >= 0 else None

        if shares is None and pct is None:
            continue

        # Classify holder type
        if current_section == '5pct' and pct is not None and pct >= 5:
            holder_type = '5pct_holder'
        elif current_section == 'insider':
            holder_type = 'director_officer'
        elif pct is not None and pct < 5:
            holder_type = 'director_officer'
            current_section = 'insider'
        elif pct is None and any(o.holder_type == '5pct_holder' for o in owners):
            holder_type = 'director_officer'
            current_section = 'insider'
        else:
            holder_type = '5pct_holder'

        owners.append(BeneficialOwner(
            name=name_cell, holder_type=holder_type,
            shares=shares, percent_of_class=pct,
        ))

    return owners if owners else None


def _parse_shares_with_adjacent(row: list[str], col: int) -> Optional[int]:
    """Parse shares, trying adjacent cell for split-cell pattern."""
    if col < 0 or col >= len(row):
        return None
    val = _parse_shares(row[col])
    if val is not None:
        return val
    if col + 1 < len(row):
        return _parse_shares(row[col + 1])
    return None


def _parse_percent_with_adjacent(row: list[str], col: int) -> Optional[float]:
    """Parse percentage, trying adjacent cell for split-cell pattern."""
    if col < 0 or col >= len(row):
        return None
    val = _parse_percent(row[col])
    if val is not None:
        return val
    if col + 1 < len(row):
        return _parse_percent(row[col + 1])
    return None


# ══════════════════════════════════════════════════════════════════════
# Director Compensation Table Extractor
# ══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class DirectorCompEntry:
    """One row of the Director Compensation Table (one non-employee director)."""
    name: str
    fees_earned: Optional[int] = None
    stock_awards: Optional[int] = None
    option_awards: Optional[int] = None
    non_equity_incentive: Optional[int] = None
    pension_change: Optional[int] = None
    other_compensation: Optional[int] = None
    total: Optional[int] = None


# ── Director comp column classification ──────────────────────────────

_DIR_COMP_COLUMN_PATTERNS: list[tuple[str, re.Pattern]] = [
    ('name', re.compile(r'name|director', re.I)),
    ('stock_awards', re.compile(r'stock\s+award', re.I)),
    ('option_awards', re.compile(r'option\s+award', re.I)),
    ('non_equity_incentive', re.compile(r'non[- ]equity|incentive\s+plan', re.I)),
    ('pension_change', re.compile(r'pension|nqdc|nonqualified\s+deferred|change\s+in\s+pension', re.I)),
    ('other_compensation', re.compile(r'all\s+other|other\s+comp', re.I)),
    ('total', re.compile(r'\btotal\b', re.I)),
    ('fees_earned', re.compile(r'fees?\s+earned|fees?\s+paid|retainer', re.I)),
]


def _classify_dir_comp_column(header: str) -> Optional[str]:
    """Classify a director compensation table column header."""
    for col_name, pattern in _DIR_COMP_COLUMN_PATTERNS:
        if pattern.search(header):
            return col_name
    return None


# ── Director comp heading anchors ────────────────────────────────────

_DIR_COMP_HEADING_ANCHORS = [
    'director compensation table',
    'director compensation—',
    'director compensation -',
    'director compensation for',
]

_DIR_COMP_HEADING_REJECTS = [
    'discussion', 'analysis', 'committee', 'program', 'philosophy',
    'process', 'overview', 'policy', 'guidelines',
]


def _find_director_comp_table(html: str):
    """Find the Director Compensation Table in HTML.

    Returns the BeautifulSoup table element, or None.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return None

    soup = BeautifulSoup(html, 'lxml')

    heading_tag = None
    for allow_in_table in [False, True]:
        for tag in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'span']):
            text = tag.get_text(strip=True)
            if not text or len(text) > 100:
                continue
            text_lower = text.lower()
            if not any(anchor in text_lower for anchor in _DIR_COMP_HEADING_ANCHORS):
                # Also match "YYYY Director Compensation" (year-prefixed)
                if not re.match(r'(?:fiscal\s+(?:year\s+)?)?\d{4}\s+director\s+compensation\b', text_lower):
                    continue
            if any(reject in text_lower for reject in _DIR_COMP_HEADING_REJECTS):
                continue
            if tag.name == 'a' or tag.find_parent('a'):
                continue
            in_table = tag.find_parent('table') is not None
            if not allow_in_table and in_table:
                continue
            if allow_in_table and in_table:
                if re.search(r'\d{2,3}\s*$', text):
                    continue
            heading_tag = tag
            break
        if heading_tag:
            break

    if not heading_tag:
        return None

    # Find the best director comp table candidate
    candidates = []
    for table in heading_tag.find_all_next('table', limit=10):
        rows = table.find_all('tr')
        if len(rows) < 3:
            continue

        all_cells = []
        for row in rows[:3]:
            for cell in row.find_all(['td', 'th']):
                text = cell.get_text(strip=True)
                if text and len(text) > 1:
                    all_cells.append(text)

        header_text = ' '.join(all_cells).lower()
        score = 0
        has_fees = 'fees' in header_text or 'retainer' in header_text
        if has_fees:
            score += 3
        if 'total' in header_text:
            score += 2
        if 'stock' in header_text and 'award' in header_text:
            score += 2
        if 'name' in header_text:
            score += 1
        if 'option' in header_text:
            score += 1
        # Reject SCT-like tables (salary column = executive comp, not director)
        if 'salary' in header_text:
            score = 0

        if score >= 3 and has_fees:
            candidates.append((table, score, len(rows)))

    if not candidates:
        return None

    candidates.sort(key=lambda x: (x[1], x[2]), reverse=True)
    return candidates[0][0]


def extract_director_compensation(html: str) -> Optional[List[DirectorCompEntry]]:
    """
    Extract Director Compensation Table from proxy statement HTML.

    Covers non-employee director compensation including fees earned,
    stock awards, option awards, and total. SEC Item 402(k) mandates
    this disclosure.

    Args:
        html: Raw HTML of the proxy statement filing.

    Returns:
        List of DirectorCompEntry, or None if the table was not found.
    """
    if not html:
        return None

    table_el = _find_director_comp_table(html)
    if table_el is None:
        return None

    headers, data_rows = _extract_table_data(table_el)
    if not data_rows:
        return None

    # Build column map
    col_map: dict[str, int] = {}
    for i, header in enumerate(headers):
        col_type = _classify_dir_comp_column(header)
        if col_type:
            col_map[col_type] = i

    # Fallback: scan first data rows
    if len(col_map) < 3:
        for row in data_rows[:2]:
            for i, cell in enumerate(row):
                col_type = _classify_dir_comp_column(cell)
                if col_type and col_type not in col_map:
                    col_map[col_type] = i

    if len(col_map) < 3:
        return None

    name_col = col_map.get('name', 0)

    def _get_dollar(row: list[str], col_name: str) -> Optional[int]:
        idx = col_map.get(col_name, -1)
        if idx < 0 or idx >= len(row):
            return None
        val = _parse_comp_dollar(row[idx])
        if val is not None:
            return val
        if row[idx].strip() == '$' and idx + 1 < len(row):
            return _parse_comp_dollar('$' + row[idx + 1])
        if not row[idx].strip() and idx + 1 < len(row):
            return _parse_comp_dollar(row[idx + 1])
        return None

    entries: list[DirectorCompEntry] = []
    for row in data_rows:
        if name_col >= len(row):
            continue
        name_cell = _ZERO_WIDTH_RE.sub('', row[name_col]).replace('\xa0', ' ').strip()
        name_cell = _FOOTNOTE_RE.sub('', name_cell).strip()
        if not name_cell or len(name_cell) < 2:
            continue
        # Skip total/summary rows and footnotes
        if any(kw in name_cell.lower() for kw in ['total', 'footnote', 'note', '(1)', '(2)']):
            continue

        # Need at least one dollar value to be a valid row
        fees = _get_dollar(row, 'fees_earned')
        stock = _get_dollar(row, 'stock_awards')
        total = _get_dollar(row, 'total')
        if fees is None and stock is None and total is None:
            continue

        entries.append(DirectorCompEntry(
            name=name_cell,
            fees_earned=fees,
            stock_awards=stock,
            option_awards=_get_dollar(row, 'option_awards'),
            non_equity_incentive=_get_dollar(row, 'non_equity_incentive'),
            pension_change=_get_dollar(row, 'pension_change'),
            other_compensation=_get_dollar(row, 'other_compensation'),
            total=total,
        ))

    return entries if entries else None
