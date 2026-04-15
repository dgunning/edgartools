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

__all__ = ['extract_voting_proposals', 'VotingProposal', 'extract_ceo_pay_ratio', 'CEOPayRatio']

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
