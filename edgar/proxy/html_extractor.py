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
from dataclasses import dataclass, field
from typing import List, Literal, Optional

log = logging.getLogger(__name__)

__all__ = ['extract_voting_proposals', 'VotingProposal']

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
    # Remove markdown table artifacts (pipes from table rendering)
    desc = re.sub(r'\|', ' ', desc)
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
