"""
HTML extraction from DEF 14A proxy statements.

Extracts structured data from proxy statement HTML where XBRL is not available.
Text-based extractors (proposals, pay ratio) use regex scanning on filing text.
Table-based extractors (SCT, ownership, director comp) use lxml DOM parsing on
a pre-parsed HTML tree shared via ProxyStatement._html_tree.

Lessons from edgartools-workers implementation (20-company eval):
- Proposals: 90% success rate (highest reliability)
- Section headers are NOT reliable DOM anchors alone — every match is a candidate,
  and the best-scoring table after any of them wins (_find_section_table)
- Non-breaking spaces (\\u00a0) break regex — normalize first
- First occurrence of proposal text is often in TOC — retry later occurrences
"""

import logging
import re
from dataclasses import dataclass
from typing import Callable, List, Literal, Optional, Tuple

log = logging.getLogger(__name__)

__all__ = [
    'extract_voting_proposals', 'VotingProposal',
    'extract_ceo_pay_ratio', 'CEOPayRatio',
    'extract_summary_compensation', 'ExecutiveCompEntry',
    'extract_beneficial_ownership', 'BeneficialOwner',
    'extract_director_compensation', 'DirectorCompEntry',
    'extract_audit_fees', 'AuditFees',
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
# The ``(?!\.\d)`` guard stops a decimal sub-item number from being read as a
# proposal: on merger proxies (DEFM14A) the Incorporation-by-Reference section
# cites 8-K items like "Item 2.02 or Item 7.01" \u2014 without the guard "Item 2.02"
# parses as proposal 2 with description "02 or Item 7.01 ..." (edgartools-7pga).
_PROPOSAL_PATTERN = re.compile(
    r'(?:proposal\s+(?:no\.?\s*)?|item\s+)(\d+)(?!\.\d)\s*[:\-\u2014\u2013.\s]+([^\n]{10,200})',
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

        # Skip descriptions that begin with a digit — a real proposal title
        # starts with a word ("Share Issuance Proposal"), never a bare number.
        # This catches decimal-item fragments ("02 or Item 7.01 ...") that slip
        # past the pattern guard (edgartools-7pga).
        if description[0].isdigit():
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

    # Validate numbering: real proxy proposals are numbered from 1. If the
    # lowest captured number is not 1, the anchor for proposal 1 was missed and
    # what remains is almost certainly fragments lifted from elsewhere (e.g. an
    # Incorporation-by-Reference list) — prefer an empty list over garbage
    # (edgartools-7pga). A genuine single proposal is always numbered 1.
    if proposals and proposals[0].number != 1:
        return []

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

# Multi-word patterns allow no space: a dropped <br> glues "Stockawards" (JPM)
# and "Optionawards" (JNJ), which the camel-case split cannot separate.
_SCT_COLUMN_PATTERNS: list[tuple[str, re.Pattern]] = [
    # CAT adds "Total Without Change in Pension Value" after Total: not pension.
    ('total_excluding', re.compile(r'total\s*(?:without|excluding|less)', re.I)),
    ('name', re.compile(r'name|principal\s*position', re.I)),
    ('year', re.compile(r'\byear\b', re.I)),
    ('stock_awards', re.compile(r'stock\s*award', re.I)),
    ('option_awards', re.compile(r'option\s*award', re.I)),
    ('non_equity_incentive', re.compile(r'non[- ]?equity|incentive\s*plan', re.I)),
    ('pension_change', re.compile(r'pension|nqdc|nonqualified\s*deferred', re.I)),
    ('other_compensation', re.compile(r'all\s*other|other\s*comp', re.I)),
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


def _parse_comp_dollar(text: str, scale: int = 1) -> Optional[int]:
    """Parse a dollar amount from an SCT cell. Returns None for dashes/empty.

    ``scale`` applies a table's unit before rounding, so XOM's 37.6 (millions
    of dollars) is 37,600,000 and not 38,000,000.
    """
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
        value = round(float(cleaned) * scale)
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


_TITLE_WORD_RE = re.compile(
    r'\b(?:' + '|'.join(re.escape(kw) for kw in _TITLE_KEYWORDS) + r')\b', re.I)


def _is_title_only(cell: str) -> bool:
    """A cell holding only a job title: it opens with a title word or a joiner."""
    words = cell.split()
    return bool(words) and (bool(_TITLE_WORD_RE.match(cell)) or
                            words[0].lower() in ('and', 'former', 'executive', 'senior', 'vice', 'interim'))


def _split_name_title(cell: str) -> tuple[str, str]:
    """Split 'Tim Cook, Chief Executive Officer' → ('Tim Cook', 'CEO')."""
    cell = cell.replace('\xa0', ' ').replace('\u200b', '').strip()
    # A line break ends the name (AMZN: "Andrew R. Jassy<br>President and Chief
    # Executive Officer"); find it before whitespace is collapsed, or the title
    # keyword search below splits at "Chief" and keeps "President and" in the name.
    # The title keeps its words: abbreviating "Former Senior Vice President,
    # Chief Financial Officer" to "CFO" would drop "Former".
    lines = [' '.join(line.split()).rstrip(',') for line in cell.split('\n') if line.strip()]
    if len(lines) > 1 and len(lines[0].split()) >= 2:   # F breaks "John / T. Lawler"
        title_text = ' '.join(lines[1:])
        if re.search(r'\b(?:' + '|'.join(_TITLE_KEYWORDS) + r'|founder|chair)\b', title_text, re.I):
            return lines[0], title_text
    cell = re.sub(r'\s+', ' ', cell)

    # Try splitting on a comma
    for sep in [',']:
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




# ══════════════════════════════════════════════════════════════════════
# Shared lxml-based table extraction utilities
# ══════════════════════════════════════════════════════════════════════

_HEADING_TAGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'span'}


def _is_inside_table(el) -> bool:
    """Check if an lxml element is inside a <table>."""
    parent = el.getparent()
    while parent is not None:
        if parent.tag == 'table':
            return True
        parent = parent.getparent()
    return False


def _is_inside_link(el) -> bool:
    """Check if an lxml element is inside an <a> tag."""
    if el.tag == 'a':
        return True
    parent = el.getparent()
    while parent is not None:
        if parent.tag == 'a':
            return True
        parent = parent.getparent()
    return False


def _iter_following_tables(el, limit: int = 10):
    """Yield up to `limit` <table> elements following `el` in document order.

    Uses XPath following::table to find tables anywhere after the element,
    regardless of nesting level.
    """
    try:
        tables = el.xpath('following::table')
        for table in tables[:limit]:
            yield table
    except Exception:
        # Fallback: walk siblings and their descendants
        count = 0
        for following in el.itersiblings():
            if following.tag == 'table':
                yield following
                count += 1
                if count >= limit:
                    return
            for desc in following.iter('table'):
                yield desc
                count += 1
                if count >= limit:
                    return


def _cell_span(cell, attr: str) -> int:
    value = (cell.get(attr, '1') or '1').strip()
    return max(int(value), 1) if value.isdigit() else 1


# Superscripts in these tables are footnote markers: PG's "Percent of Class"
# cell for each director holds only <sup>6</sup>, which read as 6%.
_CELL_TEXT_XPATH = './/text()[not(ancestor::sup)]'


def _cell_text(cell) -> str:
    return ''.join(cell.xpath(_CELL_TEXT_XPATH)).strip()


def _skip_spanned(row: list[str], row_filled: list[str], pending: dict[int, int]):
    """Leave empty the columns a rowspan from an earlier row still covers."""
    while pending.get(len(row), 0) > 0:
        pending[len(row)] -= 1
        row.append('')
        row_filled.append('')


def _extract_table_grids(table_el) -> tuple[list[list[str]], list[list[str]]]:
    """A <table> as two text grids, with colspan and rowspan expanded.

    In ``grid`` a cell's text sits in its first column only and the columns and
    rows it spans are empty, so every value keeps its column: AMZN's SCT puts
    each name in a rowspan=3 cell, and ignoring that shifted the 2024 and 2023
    rows three columns left. ``filled`` repeats a cell's text across its
    colspan, which is what a header row needs to label every column it covers.
    """
    grid: list[list[str]] = []
    filled: list[list[str]] = []
    pending: dict[int, int] = {}   # column -> rows a rowspan above still covers
    for tr in table_el.iter('tr'):
        row: list[str] = []
        row_filled: list[str] = []
        for cell in tr:
            if cell.tag not in ('td', 'th'):
                continue
            _skip_spanned(row, row_filled, pending)
            text = _ZERO_WIDTH_RE.sub('', _cell_text(cell)).strip()
            rowspan = _cell_span(cell, 'rowspan')
            for k in range(_cell_span(cell, 'colspan')):
                if rowspan > 1:
                    pending[len(row)] = rowspan - 1
                row.append(text if k == 0 else '')
                row_filled.append(text)
        _skip_spanned(row, row_filled, pending)
        grid.append(row)
        filled.append(row_filled)
    return grid, filled


def _extract_table_grid(table_el) -> list[list[str]]:
    """A <table> as a text grid; see _extract_table_grids."""
    return _extract_table_grids(table_el)[0]


# A data row has a number of three or more digits once footnote markers like
# "(1)" are gone: a year, a share count, a dollar amount.
_DATA_NUMBER_RE = re.compile(r'\d[\d,.]{2,}')
_HEADER_LEVEL_SEP = '\x1f'   # joins the stacked labels of one header column
_HEADER_SCAN_ROWS = 10   # KO stacks its director-comp labels over 6+ rows


def _is_data_row(row: list[str]) -> bool:
    """A row with a value: a number of three or more digits, or a dash for none."""
    return any(_DATA_NUMBER_RE.search(_FOOTNOTE_RE.sub('', c)) or _DASH_RE.match(c) for c in row if c)


def _split_header_data(
    grid: list[list[str]],
    header_keywords: Optional[list[str]] = None,
    filled: Optional[list[list[str]]] = None,
) -> Tuple[list[str], list[list[str]]]:
    """Split a grid into one merged header row and data rows aligned to it.

    The header is a block of rows, not one row: modern proxies stack labels
    ("Shares of Class A Common Stock" over "Number" and "Percentage" on SHAK).
    Each header column holds its labels top to bottom joined by
    _HEADER_LEVEL_SEP, and only at the column where a label starts, so a
    caller reads a label's column as the start of its span.
    """
    if not grid:
        return [], []
    filled = filled or grid
    scan = grid[:_HEADER_SCAN_ROWS]

    header_row_idx = -1
    if header_keywords:
        for i, row in enumerate(scan):
            row_text = ' '.join(row).lower()
            if sum(1 for kw in header_keywords if kw in row_text) >= 2:
                header_row_idx = i
                break
    if header_row_idx < 0:
        for i, row in enumerate(scan):
            if len([c for c in row if c]) >= 3:
                header_row_idx = i
                break
    if header_row_idx < 0:
        return [], grid

    # Extend the block over label rows: upward while a row has text and no
    # data, downward while a row has two or more labels and no data. A row with
    # one label (SHAK's "Named Executive Officers") is a section row of the data.
    first = header_row_idx
    while first > 0 and any(grid[first - 1]) and not _is_data_row(grid[first - 1]):
        first -= 1
    last = header_row_idx
    while (last + 1 < len(grid) and last + 1 <= _HEADER_SCAN_ROWS
           and len([c for c in grid[last + 1] if c]) >= 2 and not _is_data_row(grid[last + 1])):
        last += 1
    block = range(first, last + 1)

    width = max(len(r) for r in grid)
    starts = [col for col in range(width) if any(col < len(grid[r]) and grid[r][col] for r in block)]
    # A row whose one label covers every column is the table's title, not a
    # group label: "Director Compensation" over every column would make each
    # of them the name column.
    level_rows = [r for r in block
                  if len({filled[r][c] for c in starts if c < len(filled[r]) and filled[r][c]}) > 1
                  or not all(c < len(filled[r]) and filled[r][c] for c in starts)]
    headers = [''] * width
    for col in starts:
        levels: list[str] = []
        for r in level_rows:
            label = filled[r][col] if col < len(filled[r]) else ''
            if label and label not in levels:
                levels.append(label)
        headers[col] = _HEADER_LEVEL_SEP.join(levels)
    return headers, [_align_to_headers(headers, row) for row in grid[last + 1:]]


def _align_to_headers(headers: list[str], row: list[str]) -> list[str]:
    """Move each value to the column where its header label starts.

    A label covers the columns from its own up to the next label, and filing
    agents put the value anywhere inside that span, often after a separate "$"
    cell (AMZN's "Salary" spans columns 10-15 and its value sits at 12).
    """
    starts = [i for i, h in enumerate(headers) if h]
    if not starts:
        return row
    out = list(row[:starts[0]]) + [''] * max(0, len(row) - starts[0])
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(row)
        values = [c for c in row[start:end] if c and c != '$']
        if values:
            out[start] = values[0]
    return out


_CAMEL_RE = re.compile(r'(?<=[a-z])(?=[A-Z])')


def _classify_header(header: str, classifier: Callable[[str], Optional[str]]) -> Optional[str]:
    """Classify a stacked header as one label read top to bottom.

    The joined label is what a reader sees ("Percent of Outstanding Shares" on
    KO, "Shares of Class A Common Stock Percentage" on SHAK), and the
    classifiers test their most specific pattern first. A level on its own is
    the fallback.
    """
    # Words glued where a <br> stood ("StockAwards" on FIVE) get their space back.
    levels = [_CAMEL_RE.sub(' ', level.replace('\xa0', ' ')) for level in header.split(_HEADER_LEVEL_SEP)]
    col_type = classifier(' '.join(levels))
    if col_type or len(levels) == 1:
        return col_type
    for label in reversed(levels):
        col_type = classifier(label)
        if col_type:
            return col_type
    return None


def _build_column_map(
    headers: list[str],
    data_rows: list[list[str]],
    classifier: Callable[[str], Optional[str]],
    min_columns: int = 3,
) -> dict[str, int]:
    """Build a column index map from headers, with data-row fallback.

    When several columns get the same type, the first one holding numbers
    wins (the first, for names; a total of beneficial ownership, for shares):
    on a dual-class table (SHAK) that is the first class, and JNJ's text column
    "Role for additional cash retainer" does not take the place of "Fees
    earned or paid in cash".
    """
    by_type: dict[str, list[int]] = {}
    for i, header in enumerate(headers):
        if header:
            col_type = _classify_header(header, classifier)
            if col_type:
                by_type.setdefault(col_type, []).append(i)

    def has_numbers(col: int) -> bool:
        # A dash is a value too: CAT's pension column holds nothing else.
        return any(col < len(row) and (re.search(r'\d', row[col]) or _DASH_RE.match(row[col]))
                   for row in data_rows if col < len(row) and row[col])

    col_map: dict[str, int] = {}
    for col_type, cols in by_type.items():
        numeric = [c for c in cols if has_numbers(c)] if col_type != 'name' else []
        if col_type == 'fees_earned':
            # PG lists "Annual Retainer" and "Committee Chair Fees" before
            # "Total Fees Earned or Paid in Cash", which is the column.
            earned = [c for c in numeric if re.search(r'earned|paid', headers[c], re.I)]
            numeric = earned or numeric
        if col_type == 'shares':
            # A total of beneficial ownership wins: NVDA and CMG split "Shares
            # Owned" from shares acquirable within 60 days, then add them up.
            # A bare "Total" does not: MSFT's adds stock units that are not
            # beneficially owned.
            totals = [c for c in numeric
                      if re.search(r'\btotal\b', headers[c], re.I) and re.search(r'benefic', headers[c], re.I)]
            numeric = totals or numeric
        col_map[col_type] = numeric[0] if numeric else cols[0]

    if len(col_map) < min_columns:
        for row in data_rows[:2]:
            for i, cell in enumerate(row):
                col_type = classifier(cell)
                if col_type and col_type not in col_map:
                    col_map[col_type] = i

    return col_map


# A heading that opens with one of these is a sentence or a footnote that
# mentions the section ("See the Summary Compensation Table below", "(2)Based
# on Summary Compensation Table ..."), not the section's title.
_PROSE_HEADING_RE = re.compile(r'^(?:\(\w{1,3}\)|[*\u2022\u25cf]|see\b|the\b|as\b|based\b|includes?\b|for\b)', re.I)


def _heading_quality(text: str, in_table: bool) -> int:
    """2 for a title, 1 for a long or in-table match, 0 for prose or a footnote."""
    if _PROSE_HEADING_RE.match(text):
        return 0
    if in_table or len(text) > 80:
        return 1
    return 2


_MAX_LABEL_CHARS = 100


def _table_header_text(trs) -> str:
    """Lowercased text of a table's opening rows, for the table scorers.

    The first six rows, then more up to _HEADER_SCAN_ROWS while they carry no
    data. Three rows were too few: KO and PG put a title and blank rows above
    their SCT labels, and an audit-fee table's labels ("Audit Fees") open its
    data rows, below a year row (PG's "FY 2023-24").
    """
    texts = []
    for n, tr in enumerate(trs[:_HEADER_SCAN_ROWS]):
        cells = [(c.text_content() or '').strip() for c in tr if c.tag in ('td', 'th')]
        if n >= 6 and _is_data_row(cells):
            break
        # Labels are short; a long cell is prose, and prose that mentions
        # shares, names and percents (NKE's Q&A table) is not an ownership table.
        texts.extend(t for t in cells if 1 < len(t) <= _MAX_LABEL_CHARS)
    return ' '.join(texts).lower()


def _find_section_table(
    tree,
    heading_anchors: list[str],
    heading_rejects: list[str],
    table_scorer: Callable[[str], Tuple[int, bool]],
    max_tables: int = 10,
):
    """Find a table in a named section of a proxy statement using lxml.

    Every element whose short text names the section is a candidate heading,
    and the best-scoring table within ``max_tables`` after any of them wins.
    Ties go to the better heading, then to the longer table: an ownership
    section often splits 5% holders from directors and officers (PG, UNH), and
    the longer table carries the group total. Taking only the first heading
    lost the table whenever that heading was a table-of-contents row (PG,
    ROKU) or a sentence that mentions the section (FIVE, BJRI, JNJ).

    Args:
        tree: Pre-parsed lxml HTML tree (from ProxyStatement._html_tree).
        heading_anchors: Anchor strings to match in heading text (lowercase).
        heading_rejects: Reject strings — skip headings containing these.
        table_scorer: Function(header_text) -> (score, is_valid).
        max_tables: Maximum tables to examine after each heading.

    Returns:
        lxml table element, or None.
    """
    if tree is None:
        return None

    root = tree.getroottree()
    scored: dict[str, tuple] = {}     # table path -> (score, valid, rows, table)
    best_anchor: dict[str, tuple[int, int]] = {}   # table path -> (heading quality, -distance)
    seen_first: set[tuple[str, int]] = set()   # (first table, quality): nested copies of one heading

    for el in tree.iter(*_HEADING_TAGS):
        text = ' '.join((el.text_content() or '').split())
        if not text or len(text) > 150:
            continue
        text_lower = text.lower()
        if not any(anchor in text_lower for anchor in heading_anchors):
            continue
        if any(reject in text_lower for reject in heading_rejects):
            continue
        if _is_inside_link(el):
            continue
        in_table = _is_inside_table(el)
        if in_table and (re.search(r'\d{2,3}\s*$', text) or '.....' in text):
            continue   # a table-of-contents row with a page number
        quality = _heading_quality(text, in_table)

        # A heading in a table's title row (PG's and SHAK's SCTs) heads that
        # table, which following:: never reaches.
        following = list(_iter_following_tables(el, limit=max_tables))
        if in_table:
            following.insert(0, next(el.iterancestors('table')))
        for distance, table_el in enumerate(following):
            path = root.getpath(table_el)
            if distance == 0:
                if (path, quality) in seen_first:
                    break
                seen_first.add((path, quality))
            if path not in scored:
                trs = list(table_el.iter('tr'))
                if len(trs) < 3:
                    scored[path] = (0, False, len(trs), table_el)
                else:
                    score, is_valid = table_scorer(_table_header_text(trs))
                    scored[path] = (score, is_valid, len(trs), table_el)
            best_anchor[path] = max(best_anchor.get(path, (0, -max_tables)), (quality, -distance))

    candidates = [(score, best_anchor[path][0], rows, best_anchor[path][1], table_el)
                  for path, (score, is_valid, rows, table_el) in scored.items() if is_valid]
    if not candidates:
        return None
    candidates.sort(key=lambda c: c[:4], reverse=True)
    return candidates[0][4]


def _first_text_column(data_rows: list[list[str]]) -> int:
    """The first column whose cells hold words and no numbers: the names.

    For a table with no "Name" header (ROKU's ownership table labels only its
    numbers), where column 0 is often an empty spacer.
    """
    width = max((len(r) for r in data_rows), default=0)
    for col in range(width):
        cells = [r[col] for r in data_rows if col < len(r) and r[col]]
        words = [c for c in cells if re.search(r'[A-Za-z]{2}', c) and not _DATA_NUMBER_RE.search(c)]
        if cells and len(words) * 2 >= len(cells):
            return col
    return 0


def _get_dollar_from_row(row: list[str], col_map: dict[str, int], col_name: str) -> Optional[int]:
    """Get a dollar value from a row aligned by _split_header_data.

    Alignment has already moved each value past any "$" cell to its label's
    column, so an empty cell means no value. Reading the next column instead
    copied SBUX's director total into fees, stock awards and option awards.
    """
    idx = col_map.get(col_name, -1)
    if idx < 0 or idx >= len(row):
        return None
    return _parse_comp_dollar(row[idx])


# ── SCT table scorer ────────────────────────────────────────────────

def _score_sct_table(header_text: str) -> Tuple[int, bool]:
    score = 0
    has_salary = 'salary' in header_text
    if has_salary: score += 3
    if 'total' in header_text: score += 2
    if 'year' in header_text: score += 1
    if 'stock' in header_text and 'award' in header_text: score += 2
    if 'name' in header_text or 'principal' in header_text: score += 1
    if 'bonus' in header_text: score += 1
    if 'option' in header_text: score += 1
    if 'fees earned' in header_text or 'fees paid' in header_text:
        score = 0; has_salary = False
    return score, (score >= 4 and has_salary)


def extract_summary_compensation(tree) -> Optional[List[ExecutiveCompEntry]]:
    """Extract Summary Compensation Table from a pre-parsed lxml HTML tree."""
    if tree is None:
        return None

    table_el = _find_section_table(
        # "Summary Compensation" alone heads SHAK's table; the table scorer, not
        # the heading, decides between candidates.
        tree, ['summary compensation table', 'summary compensation'], [], _score_sct_table)
    if table_el is None:
        return None

    grid, filled = _extract_table_grids(table_el)
    headers, data_rows = _split_header_data(
        grid, header_keywords=['salary', 'total', 'year', 'name'], filled=filled)
    if not data_rows:
        return None

    col_map = _build_column_map(headers, data_rows, _classify_sct_column, min_columns=4)
    if len(col_map) < 4:
        return None

    name_col = col_map['name'] if 'name' in col_map else _first_text_column(data_rows)
    year_col = col_map.get('year', -1)

    entries: list[ExecutiveCompEntry] = []
    current_name = ''
    current_title = ''

    for row in data_rows:
        if name_col < len(row) and row[name_col]:
            cell_text = row[name_col]
            if cell_text and not cell_text.startswith('(') and len(cell_text) > 2:
                name, title = _split_name_title(cell_text)
                if current_name and _is_title_only(' '.join(cell_text.split())):
                    # The title on the executive's next row (FIVE, BJRI):
                    # "Chief Executive Officer and" is not a new executive.
                    current_title = f"{current_title} {' '.join(cell_text.split())}".strip()
                elif name and not any(kw in name.lower() for kw in ['total', 'footnote', 'note']):
                    current_name = name
                    current_title = title

        year = 0
        if 0 <= year_col < len(row):
            try:
                year = int(re.sub(r'[^\d]', '', row[year_col])[:4])
            except (ValueError, IndexError):
                pass
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
            name=current_name, title=current_title, year=year,
            salary=_get_dollar_from_row(row, col_map, 'salary'),
            bonus=_get_dollar_from_row(row, col_map, 'bonus'),
            stock_awards=_get_dollar_from_row(row, col_map, 'stock_awards'),
            option_awards=_get_dollar_from_row(row, col_map, 'option_awards'),
            non_equity_incentive=_get_dollar_from_row(row, col_map, 'non_equity_incentive'),
            pension_change=_get_dollar_from_row(row, col_map, 'pension_change'),
            other_compensation=_get_dollar_from_row(row, col_map, 'other_compensation'),
            total=_get_dollar_from_row(row, col_map, 'total'),
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


_OWNERSHIP_COLUMN_PATTERNS: list[tuple[str, re.Pattern]] = [
    # Percent and shares before name: "Amount and Nature of Beneficial
    # Ownership" is the shares column, though it says "beneficial owner".
    ('class_title', re.compile(r'title\s+of\s+class', re.I)),   # JNJ: not a percent
    # "%" anywhere (ROKU labels a column "Class A" over a bare "%"), but not
    # "of class": stacked labels read "Shares of Class A Common Stock Number".
    ('percent', re.compile(r'percent|%', re.I)),
    # "Total" too: PG's director table splits holdings into direct, right to
    # acquire and family columns and gives the beneficial count under "Total".
    ('shares', re.compile(r'\bshare(?!\s*holder)(?!ing)|\bnumber\b|\bamount\b|^\s*total\b', re.I)),   # not PG's "Profit Sharing Plan"
    ('name', re.compile(r'name|beneficial\s+owner', re.I)),
]

def _classify_ownership_column(header: str) -> Optional[str]:
    for col_name, pattern in _OWNERSHIP_COLUMN_PATTERNS:
        if pattern.search(header):
            return col_name
    return None

def _parse_shares(text: str) -> Optional[int]:
    cleaned = _FOOTNOTE_RE.sub('', text)
    cleaned = _STAR_RE.sub('', cleaned)
    cleaned = _ZERO_WIDTH_RE.sub('', cleaned).strip()
    if not cleaned or _DASH_RE.match(cleaned):
        return None
    cleaned = re.sub(r'\s*shares?$', '', cleaned, flags=re.I)   # JNJ: "243,455,135 shares"
    cleaned = cleaned.replace(',', '').replace('$', '').replace(' ', '')
    try:
        return int(cleaned)
    except ValueError:
        return None

def _parse_percent(text: str) -> Optional[float]:
    raw = text.strip()
    if not raw or _DASH_RE.match(raw):
        return None
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

_GROUP_RE = re.compile(
    r'directors?\s+and\s+(?:executive\s+)?officers?|'
    r'all\s+(?:named\s+)?executive\s+officers?\s+and\s+directors?|'
    r'as\s+a\s+group', re.I)

_SECTION_HEADER_RE = re.compile(
    r'^(?:named\s+executive\s+officers?|'
    r'directors?\s+(?:and|&)\s+(?:director\s+)?nominees?|'
    r'5%\s+(?:stock)?holders?|'
    r'beneficial\s+owners?\s+of\s+5%|'
    r'principal\s+(?:stock)?holders?)', re.I)

_OWNERSHIP_HEADING_ANCHORS = [
    'security ownership of certain beneficial owners',
    'security ownership of certain',
    'stock ownership of certain beneficial owners',
    'beneficial ownership of common stock',
    'beneficial ownership of shares',
    'principal shareholders', 'principal shareowners',
    'stock ownership information',
    'director and executive officer stock ownership',
    'security ownership of management',
    'beneficial ownership',
]
_OWNERSHIP_HEADING_REJECTS = ['guidelines', 'requirements', 'policy', 'robust']

def _score_ownership_table(header_text: str) -> Tuple[int, bool]:
    score = 0
    if 'name' in header_text or 'beneficial owner' in header_text: score += 2
    if 'share' in header_text or 'amount' in header_text or 'number' in header_text: score += 2
    if 'percent' in header_text or '% of' in header_text or 'of class' in header_text: score += 2
    if 'beneficially owned' in header_text: score += 1
    return score, score >= 3

def _parse_cell(row: list[str], col: int, parser) -> Optional:
    """Parse one cell of an aligned row; see _get_dollar_from_row for why not its neighbour."""
    if col < 0 or col >= len(row):
        return None
    return parser(row[col])


def extract_beneficial_ownership(tree) -> Optional[List[BeneficialOwner]]:
    """Extract beneficial ownership table from a pre-parsed lxml HTML tree."""
    if tree is None:
        return None

    table_el = _find_section_table(
        tree, _OWNERSHIP_HEADING_ANCHORS, _OWNERSHIP_HEADING_REJECTS, _score_ownership_table)
    if table_el is None:
        return None

    grid, filled = _extract_table_grids(table_el)
    headers, data_rows = _split_header_data(grid, filled=filled)
    if not data_rows:
        return None

    col_map = _build_column_map(headers, data_rows, _classify_ownership_column, min_columns=2)
    name_col = col_map['name'] if 'name' in col_map else _first_text_column(data_rows)
    shares_col = col_map.get('shares', -1)
    percent_col = col_map.get('percent', -1)

    if shares_col < 0 and percent_col < 0:
        return None

    owners: list[BeneficialOwner] = []
    current_section = '5pct'

    for row in data_rows:
        if name_col >= len(row):
            continue
        name_cell = _ZERO_WIDTH_RE.sub('', row[name_col]).strip()
        name_cell = _FOOTNOTE_RE.sub('', name_cell).strip()
        if not name_cell or len(name_cell) < 2:
            continue

        if _SECTION_HEADER_RE.match(name_cell):
            if re.search(r'director|officer|nominee|executive', name_cell, re.I):
                current_section = 'insider'
            continue

        if _GROUP_RE.search(name_cell):
            shares = _parse_cell(row, shares_col, _parse_shares) if shares_col >= 0 else None
            pct = _parse_cell(row, percent_col, _parse_percent) if percent_col >= 0 else None
            if shares is not None or pct is not None:
                owners.append(BeneficialOwner(name=name_cell, holder_type='group', shares=shares, percent_of_class=pct))
            continue

        shares = _parse_cell(row, shares_col, _parse_shares) if shares_col >= 0 else None
        pct = _parse_cell(row, percent_col, _parse_percent) if percent_col >= 0 else None
        if shares is None and pct is None:
            continue

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

        owners.append(BeneficialOwner(name=name_cell, holder_type=holder_type, shares=shares, percent_of_class=pct))

    return owners if owners else None


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


_DIR_COMP_COLUMN_PATTERNS: list[tuple[str, re.Pattern]] = [
    ('name', re.compile(r'name|director', re.I)),
    # JPM's "Other fees earned or paid in cash" (subsidiary boards) is other pay.
    ('other_compensation', re.compile(r'all\s*other|other\s*comp|other\s*fees', re.I)),
    # Fees before total: PG's "Total Fees Earned or Paid in Cash" is the fees.
    ('fees_earned', re.compile(r'fees?\s*earned|fees?\s*paid|retainer', re.I)),
    # ROKU: "RSU Awards"; CAT: "Restricted Stock Units".
    ('stock_awards', re.compile(r'stock\s*award|rsu\s*award|restricted\s*stock', re.I)),
    ('option_awards', re.compile(r'option\s*award', re.I)),
    ('non_equity_incentive', re.compile(r'non[- ]?equity|incentive\s*plan', re.I)),
    ('pension_change', re.compile(r'pension|nqdc|nonqualified\s*deferred', re.I)),
    ('total', re.compile(r'\btotal\b', re.I)),
]

def _classify_dir_comp_column(header: str) -> Optional[str]:
    for col_name, pattern in _DIR_COMP_COLUMN_PATTERNS:
        if pattern.search(header):
            return col_name
    return None

_DIR_COMP_HEADING_ANCHORS = [
    'director compensation table',
    'director compensation\u2014',
    'director compensation -',
    'director compensation for',
    'director compensation',
]
_DIR_COMP_HEADING_REJECTS = [
    'discussion', 'analysis', 'committee', 'program', 'philosophy',
    'process', 'overview', 'policy', 'guidelines',
]

def _score_dir_comp_table(header_text: str) -> Tuple[int, bool]:
    score = 0
    has_fees = 'fees' in header_text or 'retainer' in header_text
    has_stock = 'stock' in header_text and 'award' in header_text
    if has_fees: score += 3
    if 'total' in header_text: score += 2
    if has_stock: score += 2
    if 'name' in header_text: score += 1
    if 'option' in header_text: score += 1
    if 'salary' in header_text or 'audit' in header_text:   # an SCT, or AMZN's audit-fee table
        return 0, False
    if re.search(r'vesting|vested|acquired on|exercis', header_text):   # NEO stock-vested tables
        return 0, False
    # Directors paid only in stock (AMZN) have no fees column.
    return score, score >= 3 and (has_fees or (has_stock and 'name' in header_text))


def extract_director_compensation(tree) -> Optional[List[DirectorCompEntry]]:
    """Extract Director Compensation Table from a pre-parsed lxml HTML tree."""
    if tree is None:
        return None

    table_el = _find_section_table(
        tree, _DIR_COMP_HEADING_ANCHORS, _DIR_COMP_HEADING_REJECTS, _score_dir_comp_table)
    if table_el is None:
        return None

    grid, filled = _extract_table_grids(table_el)
    headers, data_rows = _split_header_data(grid, filled=filled)
    if not data_rows:
        return None

    col_map = _build_column_map(headers, data_rows, _classify_dir_comp_column, min_columns=3)
    if not {'fees_earned', 'stock_awards', 'total'} & col_map.keys():
        return None   # no compensation column; AMZN's has only Name and Stock Awards

    name_col = col_map['name'] if 'name' in col_map else _first_text_column(data_rows)
    entries: list[DirectorCompEntry] = []

    for row in data_rows:
        if name_col >= len(row):
            continue
        name_cell = _ZERO_WIDTH_RE.sub('', row[name_col]).replace('\xa0', ' ').strip()
        name_cell = _FOOTNOTE_RE.sub('', name_cell).strip()
        if not name_cell or len(name_cell) < 2:
            continue
        if any(kw in name_cell.lower() for kw in ['total', 'footnote', 'note', '(1)', '(2)']):
            continue

        fees = _get_dollar_from_row(row, col_map, 'fees_earned')
        stock = _get_dollar_from_row(row, col_map, 'stock_awards')
        total = _get_dollar_from_row(row, col_map, 'total')
        if fees is None and stock is None and total is None:
            continue

        entries.append(DirectorCompEntry(
            name=name_cell, fees_earned=fees, stock_awards=stock,
            option_awards=_get_dollar_from_row(row, col_map, 'option_awards'),
            non_equity_incentive=_get_dollar_from_row(row, col_map, 'non_equity_incentive'),
            pension_change=_get_dollar_from_row(row, col_map, 'pension_change'),
            other_compensation=_get_dollar_from_row(row, col_map, 'other_compensation'),
            total=total,
        ))

    return entries if entries else None


# ══════════════════════════════════════════════════════════════════════
# Audit Fees Extractor
# ══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AuditFees:
    """Audit fee disclosure data."""
    auditor_name: str = ''
    current_year: int = 0
    prior_year: int = 0
    audit_fees_current: Optional[int] = None
    audit_fees_prior: Optional[int] = None
    audit_related_current: Optional[int] = None
    audit_related_prior: Optional[int] = None
    tax_fees_current: Optional[int] = None
    tax_fees_prior: Optional[int] = None
    other_fees_current: Optional[int] = None
    other_fees_prior: Optional[int] = None
    total_current: Optional[int] = None
    total_prior: Optional[int] = None


def _classify_fee_row(label: str) -> Optional[str]:
    """Classify a fee table row label. Most specific first."""
    lc = label.lower()
    if re.match(r'\s*sub-?\s*total', lc) or (re.match(r'\s*(?:total|aggregate)\b', lc) and re.search(r'audit|tax', lc)):
        return None   # a subtotal: PG's "Subtotal", JNJ's "Total audit and audit-related fees"
    if re.search(r'audit[-\s]*related', lc):   # BJRI: "Audit- Related Fees"
        return 'audit_related'
    if re.search(r'total|aggregate', lc):
        return 'total'
    if 'tax' in lc:
        return 'tax'
    if re.search(r'(?:all\s+)?other', lc) and 'audit' not in lc:
        return 'other'
    if 'audit' in lc and 'non-audit' not in lc:
        return 'audit'
    return None


_YEAR_RE = re.compile(r'\b(20\d{2})\b')


def _detect_year_columns(grid: list[list[str]]) -> Optional[tuple[int, int, int, int, int]]:
    """Find the year header row.

    Returns (row, current_col, prior_col, current_year, prior_year), where the
    columns are those of the year labels; data rows are aligned to them with
    _align_to_headers, so a value after a "$" cell still lands in its column.
    """
    for r, row in enumerate(grid[:_HEADER_SCAN_ROWS]):
        year_map: dict[int, int] = {}
        for i, cell in enumerate(row):
            m = _YEAR_RE.search(cell)
            if m:
                year = int(m.group(1))
                if year not in year_map:
                    year_map[year] = i
        if len(year_map) >= 2:
            sorted_years = sorted(year_map.items(), key=lambda x: -x[0])
            current_year, current_col = sorted_years[0]
            prior_year, prior_col = sorted_years[1]
            return r, current_col, prior_col, current_year, prior_year
    return None


_THOUSANDS_RE = re.compile(r'\bin\s+thousands\b|\bthousands\s+of\s+dollars\b|\(\s*\$?\s*thousands\s*\)', re.I)
_MILLIONS_RE = re.compile(r'\bin\s+millions\b|\bmillions\s+of\s+dollars\b|\(\s*\$?\s*millions\s*\)', re.I)   # XOM: "(millions of dollars)"


def _fee_table_unit(table_el) -> int:
    """A fee table's unit: the first one stated in its context, nearest first."""
    for text in _fee_table_context(table_el):
        unit = _detect_multiplier(text)
        if unit != 1:
            return unit
    return 1


def _fee_table_context(table_el) -> list[str]:
    """Texts that may state a fee table's unit, nearest first.

    The table itself (KO), the end of the three blocks just before it (AAPL's
    "(in thousands)" closes the preceding sentence), then its parent. The
    parent alone missed AAPL, whose parent holds 288k characters of the proxy.
    """
    parts = [table_el.text_content() or '']
    for block in table_el.xpath('preceding::*[self::p or self::div][position() <= 3]'):
        parts.append((block.text_content() or '')[-300:])
    parent = table_el.getparent()
    if parent is not None:
        parts.append((parent.text_content() or '')[:2000])
    return parts


def _detect_multiplier(text: str) -> int:
    if _THOUSANDS_RE.search(text):
        return 1000
    if _MILLIONS_RE.search(text):
        return 1_000_000
    return 1


_AUDITOR_PATTERNS = [
    re.compile(r'fees\s+(?:billed|paid|charged)\s+(?:by|to)\s+([A-Z][A-Za-z &,.\']+?(?:LLP|LLC|Inc\.|P\.?C\.?|PLLC|LP))', re.I),
    re.compile(r'(?:appointed|engaged|retained|selected)\s+([A-Z][A-Za-z &,.\']+?(?:LLP|LLC|Inc\.|P\.?C\.?|PLLC|LP))', re.I),
    re.compile(r'([A-Z][A-Za-z &,.\']+?(?:LLP|LLC|Inc\.|P\.?C\.?|PLLC|LP))\s*,?\s*(?:our|the|has|was|is)\s+(?:independent|principal)', re.I),
]


def _extract_auditor_name(text: str) -> str:
    for pattern in _AUDITOR_PATTERNS:
        m = pattern.search(text)
        if m:
            return m.group(1).strip()
    return ''


_AUDIT_HEADING_ANCHORS = [
    'audit fees',
    'fees paid to auditor',
    'fees billed by',
    'fees paid to',
    'principal accountant fees',
    'audit and non-audit fees',
]
_AUDIT_HEADING_REJECTS = ['pre-approval', 'committee report']


def _score_audit_table(header_text: str) -> Tuple[int, bool]:
    score = 0
    if bool(_YEAR_RE.search(header_text)):
        score += 3
    if 'audit' in header_text:
        score += 2
    if 'total' in header_text:
        score += 1
    if 'tax' in header_text:
        score += 1
    # A year alone is not enough: ETSY's equity-plan table ("Total Number of
    # Shares Cancelled 3,333,880") was read as total audit fees.
    return score, score >= 3 and ('audit' in header_text or 'fee' in header_text)


def extract_audit_fees(tree) -> Optional[AuditFees]:
    """Extract audit fees from a pre-parsed lxml HTML tree."""
    if tree is None:
        return None

    table_el = _find_section_table(
        tree, _AUDIT_HEADING_ANCHORS, _AUDIT_HEADING_REJECTS, _score_audit_table)
    if table_el is None:
        return None

    grid = _extract_table_grid(table_el)
    if not grid or len(grid) < 3:
        return None

    year_info = _detect_year_columns(grid)
    if year_info is None:
        return None
    year_row, current_col, prior_col, current_year, prior_year = year_info

    parent = table_el.getparent()
    context_text = (parent.text_content() or '') if parent is not None else ''
    multiplier = _fee_table_unit(table_el)

    fees: dict[str, tuple[Optional[int], Optional[int]]] = {}
    first_value_col = min(current_col, prior_col)
    for raw in grid[year_row + 1:]:
        row = _align_to_headers(grid[year_row], raw)
        # The label is the first text before the values (column 1 on AMZN).
        label = next((c for c in row[:first_value_col] if c), '')
        category = _classify_fee_row(label)
        if not category:
            continue

        current_val = _parse_comp_dollar(row[current_col], multiplier) if current_col < len(row) else None
        prior_val = _parse_comp_dollar(row[prior_col], multiplier) if prior_col < len(row) else None

        if current_val is not None or prior_val is not None or category not in fees:
            fees[category] = (current_val, prior_val)

    # Years with no fee under them are not a fee disclosure (SHAK and XOM read
    # as an AuditFees of nothing but years).
    if not any(v is not None for pair in fees.values() for v in pair):
        return None

    auditor_name = _extract_auditor_name(context_text[:3000])

    return AuditFees(
        auditor_name=auditor_name,
        current_year=current_year, prior_year=prior_year,
        audit_fees_current=fees.get('audit', (None, None))[0],
        audit_fees_prior=fees.get('audit', (None, None))[1],
        audit_related_current=fees.get('audit_related', (None, None))[0],
        audit_related_prior=fees.get('audit_related', (None, None))[1],
        tax_fees_current=fees.get('tax', (None, None))[0],
        tax_fees_prior=fees.get('tax', (None, None))[1],
        other_fees_current=fees.get('other', (None, None))[0],
        other_fees_prior=fees.get('other', (None, None))[1],
        total_current=fees.get('total', (None, None))[0],
        total_prior=fees.get('total', (None, None))[1],
    )
