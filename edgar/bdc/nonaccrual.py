"""
Non-accrual investment extraction from BDC filings.

Extracts non-accrual status data using three layered approaches:

1. **XBRL footnotes** — richest source. Scans footnote text for non-accrual patterns,
   follows related_fact_ids to identify specific investments with fair values.
2. **Custom XBRL concepts** — 6/11 BDCs use proprietary taxonomy extensions
   (rate only, no investment-level detail).
3. **Standard us-gaap aggregate** — single concept fallback (dollar amount only).
4. **A tagged zero** — an amount or count of non-accruals tagged as 0, with no
   non-accrual footnote, reads as a 0% rate (``extraction_method='tagged_zero'``).

Usage::

    from edgar import Company
    from edgar.bdc.nonaccrual import extract_nonaccrual

    filing = Company("ARCC").get_filings(form="10-K").latest()
    result = extract_nonaccrual(filing)
    print(result.nonaccrual_rate)       # e.g. 0.012
    print(result.num_nonaccrual)        # e.g. 20, or None when the filing gives only a total
    print(result.evidence_level)        # 'investment' | 'aggregate' | 'none'
    for inv in result.investments:
        print(inv.company_name, inv.fair_value)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Union

import pandas as pd

from edgar.bdc.investments import (
    PortfolioInvestment,
    _exclude_restated_rows,
    _get_investment_member_candidates,
    _parse_investment_identifier,
    _reported_total_fair_value,
)

if TYPE_CHECKING:
    from edgar._filings import Filing
    from edgar.bdc.reference import BDCEntity

log = logging.getLogger(__name__)

# Dimension key for individual investments
DIM_KEY = 'dim_us-gaap_InvestmentIdentifierAxis'

# Concepts for portfolio data
CONCEPT_FAIR_VALUE = 'us-gaap:InvestmentOwnedAtFairValue'
CONCEPT_COST = 'us-gaap:InvestmentOwnedAtCost'

# Standard aggregate concept (works for ~1/11 BDCs)
CONCEPT_NONACCRUAL_LOANS_FV = (
    'us-gaap:FairValueOptionLoansHeldAsAssetsAggregateAmountInNonaccrualStatus'
)

# "Non-accrual", or the participle BlackRock's BDCs use: "Non-accruing debt
# investment." (edgartools-tfhpl).
_NA = r'non[- ]?accru(?:al|ing)'

# Negation patterns — footnotes that explicitly deny non-accrual status.
# These must be checked BEFORE affirmative patterns.
# Examples: "there were no investments on non-accrual status",
#           "the Company had no portfolio company investment on non-accrual"
NEGATION_PATTERNS = [
    rf'\bno\s+(?:investments?|loans?|portfolio\s+company).{{0,40}}{_NA}',
    rf'\bnone\b.{{0,40}}{_NA}',
    rf'(?:were|was|is|are)\s+not\s+(?:on\s+)?{_NA}',
    rf'did\s+not\s+have\s+any.{{0,40}}{_NA}',
    rf'\bzero\b.{{0,40}}{_NA}',
    rf'there\s+were\s+no.{{0,40}}{_NA}',
]

# Affirmative patterns — footnotes that directly state an investment is on non-accrual.
# These are the high-precision sentence/label forms observed across BDC filings
# (ARCC "Loan was on non-accrual status...", FSK "Asset is on non-accrual status.",
# MAIN "Non-accrual and/or non-income producing debt investment.").
#
# They are NOT the whole story: the classifier below also accepts short,
# investment-linked footnotes that mention non-accrual but don't match a
# sentence pattern (e.g. PSEC "Investment on non-accrual status as of the
# reporting date"). See _classify_nonaccrual_footnote for the full decision.
AFFIRMATIVE_PATTERNS = [
    rf'(?:was|were)\s+(?:on|placed\s+on)\s+{_NA}\s+status',
    rf'(?:was|were)\s+(?:on|placed\s+on)\s+{_NA}(?:\s|[,.])',
    rf'(?:is|are)\s+(?:on|currently\s+on)\s+{_NA}\s+status',
    rf'(?:is|are)\s+(?:on|currently\s+on)\s+{_NA}(?:\s|[,.])',
    rf'(?:loan|debt|investment)\s+was\s+(?:on|placed\s+on)\s+{_NA}',
    rf'(?:loan|debt|investment)\s+is\s+(?:on|currently\s+on)\s+{_NA}',
    rf'^{_NA}\s+(?:and|or)\s+non[- ]?income',
    rf'the\s+investment\s+is\s+on\s+{_NA}',
]

# A bare non-accrual mention (adjacency required, so "non-cash ... accrual" in a
# narrative paragraph does not count).
_NONACCRUAL_RE = re.compile(_NA)

# Schedule-of-investments non-accrual markers are short labels (observed range:
# 5-25 words across ARCC/FSK/GBDC/MAIN/PSEC). Footnotes that merely *mention*
# non-accrual in passing — rollforward tables, policy notes — run 100+ words.
# This threshold separates label-shaped footnotes from narrative ones.
_LABEL_MAX_WORDS = 30

# What a flag looks like, beyond mentioning non-accrual (edgartools-t75ot).
# A footnote that holds two or more numbered notes is a bundle: some filers put
# their whole "(1) ... (22) Investment is on non-accrual status" list in one
# footnote linked to every holding that carries any of them, and XBRL does not
# say which holding carries which note.
_NUMBERED_NOTE = re.compile(r'(?:^|[.;:]\s*|\s)\(\s*\d{1,2}\s*\)\s*[a-z]')
# A leading footnote mark: "(14)", "[a]", "3."
_LEADING_MARK = re.compile(r'^\s*(?:\(\s*[0-9a-z]{1,3}\s*\)|\[[0-9a-z]{1,3}\]|[0-9]{1,2}[.)]\s)\s*')
# First sentences that mention non-accrual without saying the holding is on it:
# policy notes and portfolio-level counts.
_NOT_A_FLAG_PATTERNS = [
    r'except\s+(?:for\s+)?non[- ]?accru',                                     # Logan Ridge
    r'recogni[sz]ed\s+on\s+non[- ]?accru',                                    # Oxford Square
    r'may\s+be\s+(?:placed\s+)?on\s+non[- ]?accru',
    r'\bhad\s+(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\b.{0,80}non[- ]?accru',  # AGL
]
# A later sentence about the holding itself ("Our debt investment in this
# portfolio company is on non-accrual status", after a liquidation note).
_THIS_INVESTMENT_ON_NONACCRUAL = re.compile(
    r'\b(?:our|this|the)\s+(?:debt\s+)?(?:investment|loan)\b.{0,60}?'
    r'\b(?:is|was)\s+(?:currently\s+)?(?:on|placed\s+on)\s+non[- ]?accru'
)


def _first_sentence(text: str) -> str:
    lead = _LEADING_MARK.sub('', text, count=1)
    m = re.match(r'^(.*?[.;])(?:\s|$)', lead)
    return m.group(1) if m else lead


def _is_about_the_linked_holding(text_lower: str) -> bool:
    """Whether a non-accrual footnote says its own holding is on non-accrual.

    It must not be a bundle of numbered notes, and its first sentence must
    mention non-accrual without being a policy note or a portfolio-level count,
    unless a later sentence names the investment itself.
    """
    text = re.sub(r'\s+', ' ', text_lower).strip()
    if len(_NUMBERED_NOTE.findall(text)) >= 2:
        return False
    first = _first_sentence(text)
    if _NONACCRUAL_RE.search(first) and not any(re.search(p, first) for p in _NOT_A_FLAG_PATTERNS):
        return True
    return bool(_THIS_INVESTMENT_ON_NONACCRUAL.search(text))


def _classify_nonaccrual_footnote(text_lower: str, linked_to_investments: bool) -> bool:
    """Decide whether a footnote flags non-accrual status for its linked investments.

    Layered decision (precision first, then a structure-corroborated net):

    1. Must mention non-accrual at all (adjacency-checked). Else not a flag.
    2. An explicit denial (NEGATION_PATTERNS) always wins → not a flag.
       Checked before any affirmative signal so "no investments on non-accrual"
       is never read as a flag.
    3. An explicit affirmative sentence/label (AFFIRMATIVE_PATTERNS) → flag.
       Handles the long, well-formed forms (e.g. GBDC's 25-word sentence).
    4. Structure-corroborated short label → flag. A footnote that annotates
       specific investment facts (``linked_to_investments``) *and* is short
       enough to be a marker label rather than a narrative is treated as a
       non-accrual flag regardless of exact phrasing. This is what makes the
       classifier robust to wording drift — it caught neither MAIN's and→or
       change nor PSEC's verb-less "Investment on non-accrual status" via the
       sentence patterns, but both are short, linked labels.

    The short-label rule is safe precisely because it requires investment
    linkage: long rollforward/policy footnotes that mention non-accrual are
    excluded by length, and unlinked footnotes contribute nothing to Layer-1
    extraction anyway (it resolves investments by following the linkage).

    Steps 3 and 4 also require the footnote to be about the holding it is
    linked to (``_is_about_the_linked_holding``). Short policy notes ("All debt
    investments are income producing except for non-accrual investments"),
    portfolio-level counts ("the Company had one portfolio company investment
    on non-accrual status") and bundles of numbered notes all passed 3 or 4 and
    flagged every linked holding: Runway's FY2026 Q3 rate read 98.8%
    (edgartools-t75ot).
    """
    if not _NONACCRUAL_RE.search(text_lower):
        return False
    if any(re.search(p, text_lower) for p in NEGATION_PATTERNS):
        return False
    if not _is_about_the_linked_holding(text_lower):
        return False
    if any(re.search(p, text_lower) for p in AFFIRMATIVE_PATTERNS):
        return True
    if linked_to_investments and len(text_lower.split()) <= _LABEL_MAX_WORDS:
        return True
    return False


@dataclass(frozen=True)
class NonAccrualInvestment:
    """A single investment identified as non-accrual via XBRL footnote linkage."""

    identifier: str
    company_name: str
    investment_type: str
    fair_value: Optional[Decimal]
    cost: Optional[Decimal]
    footnote_text: str


@dataclass(frozen=True)
class NonAccrualResult:
    """Non-accrual extraction result for a single BDC filing."""

    cik: int
    entity_name: str
    period: str
    source_filing: str

    # Investments identified as non-accrual
    investments: List[NonAccrualInvestment]

    # Computed metrics
    nonaccrual_fair_value: Optional[Decimal]
    total_portfolio_fair_value: Optional[Decimal]

    # Extraction metadata
    extraction_method: str  # 'footnote' | 'custom_concept' | 'aggregate_concept' | 'tagged_zero' | 'none'
    custom_concept_rate: Optional[float] = None
    aggregate_concept_value: Optional[Decimal] = None

    # Non-fatal diagnostics — populated when the result looks suspicious
    # (e.g. a portfolio with no non-accrual signal, or recognized non-accrual
    # footnotes that resolved no investments). Lets callers distinguish
    # "genuinely zero non-accruals" from "we may have failed to parse".
    warnings: List[str] = field(default_factory=list)

    # Where total_portfolio_fair_value came from: 'balance_sheet' (the filer's
    # undimensioned total or its affiliation lines), 'identifier_total' (a
    # grand-total row the filer tags as an identifier member), 'schedule_sum'
    # (the schedule's identifier rows added up, which can count subtotals), or
    # None when there is no total.
    total_source: Optional[str] = None

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)

    @property
    def nonaccrual_rate(self) -> Optional[float]:
        """Non-accrual rate at fair value. Primary metric."""
        if self.nonaccrual_fair_value is None or self.total_portfolio_fair_value is None:
            return None
        if self.total_portfolio_fair_value == 0:
            return 0.0
        return float(self.nonaccrual_fair_value / self.total_portfolio_fair_value)

    @property
    def evidence_level(self) -> str:
        """What the filing gave as non-accrual evidence.

        * ``'investment'`` — footnotes resolved individual investments, so they can be counted.
        * ``'aggregate'`` — only a portfolio-level rate or amount (a custom or us-gaap
          concept); nothing says which investments, or how many, unless the
          filer tags its non-accruals as zero (``extraction_method`` ``'tagged_zero'``).
        * ``'none'`` — no signal at all. That means unknown, not zero: a BDC can
          disclose non-accruals only in prose.
        """
        if self.investments:
            return 'investment'
        if self.extraction_method in ('custom_concept', 'aggregate_concept', 'tagged_zero'):
            return 'aggregate'
        return 'none'

    @property
    def num_nonaccrual(self) -> Optional[int]:
        """Count of non-accrual investment rows, or None when the filing does not identify them.

        Counts rows as the schedule lists them, so a company with two non-accrual
        loans counts twice. 0 when the filer tags its non-accruals as zero
        (``extraction_method`` ``'tagged_zero'``). None otherwise when
        ``evidence_level`` is ``'aggregate'`` or ``'none'``: an aggregate rate
        proves non-accruals exist without saying how many.
        """
        if self.extraction_method == 'tagged_zero':
            return 0
        if self.evidence_level != 'investment':
            return None
        return len(self.investments)

    @property
    def has_investment_detail(self) -> bool:
        """Whether individual non-accrual investments were identified."""
        return len(self.investments) > 0

    @property
    def unique_footnote_texts(self) -> List[str]:
        """Distinct footnote texts that flagged non-accrual status."""
        seen: set = set()
        texts: list = []
        for inv in self.investments:
            if inv.footnote_text not in seen:
                seen.add(inv.footnote_text)
                texts.append(inv.footnote_text)
        return texts

    def to_context(self, detail: str = 'standard') -> str:
        """
        AI-optimized context string for LLM consumption.

        Includes raw footnote text at all detail levels so the LLM can
        validate parsed data and extract information that structured
        parsing may miss.

        Args:
            detail: 'minimal' (~100 tokens), 'standard' (~300 tokens),
                    'full' (~600+ tokens with per-investment detail)
        """
        lines: list = []

        # Identity line
        rate_pct = f'{self.nonaccrual_rate * 100:.2f}%' if self.nonaccrual_rate is not None else 'unknown'
        lines.append(
            f'NON-ACCRUAL ANALYSIS: {self.entity_name}'
        )
        lines.append('')

        # Key metrics
        lines.append(f'Period: {self.period}')
        lines.append(f'Filing: {self.source_filing}')
        lines.append(f'Non-Accrual Rate: {rate_pct}')
        if self.num_nonaccrual is not None:
            lines.append(f'Non-Accrual Investments: {self.num_nonaccrual}')
        elif self.evidence_level == 'aggregate':
            lines.append('Non-Accrual Investments: not itemized (the filing gives only a portfolio-level figure)')
        else:
            lines.append('Non-Accrual Investments: unknown (no non-accrual data in the XBRL)')
        if self.nonaccrual_fair_value is not None:
            lines.append(f'Non-Accrual Fair Value: ${self.nonaccrual_fair_value:,.0f}')
        if self.total_portfolio_fair_value is not None:
            source = ' (sum of schedule rows)' if self.total_source == 'schedule_sum' else ''
            lines.append(f'Total Portfolio Fair Value: ${self.total_portfolio_fair_value:,.0f}{source}')
        lines.append(f'Evidence Level: {self.evidence_level}')
        lines.append(f'Extraction Method: {self.extraction_method}')

        # Data-quality warnings — surfaced at all detail levels so an LLM never
        # mistakes a parsing gap for a confirmed zero.
        if self.warnings:
            for w in self.warnings:
                lines.append(f'⚠ Warning: {w}')

        # Cross-validation: if we have both computed and stated rates
        if self.custom_concept_rate is not None:
            stated_pct = f'{self.custom_concept_rate * 100:.2f}%'
            lines.append(f'Stated Rate (custom XBRL concept): {stated_pct}')
            if self.nonaccrual_rate is not None:
                gap = abs(self.nonaccrual_rate - self.custom_concept_rate)
                if gap > 0.001:
                    note = f'Note: Computed rate differs from stated by {gap * 100:.2f}pp'
                    if self.custom_concept_rate > 0:
                        coverage = 100 - gap / self.custom_concept_rate * 100
                        note += f' (XBRL fact coverage is ~{coverage:.0f}%)'
                    lines.append(note)
        if self.aggregate_concept_value is not None:
            lines.append(f'Aggregate Non-Accrual (us-gaap): ${self.aggregate_concept_value:,.0f}')

        if detail == 'minimal':
            return '\n'.join(lines)

        # Footnote source text — always included at standard+ for LLM validation
        footnote_texts = self.unique_footnote_texts
        if footnote_texts:
            lines.append('')
            lines.append('SOURCE FOOTNOTE TEXT:')
            for ft in footnote_texts:
                lines.append(f'  "{ft}"')

        if detail == 'standard':
            # At standard, show investment names without full detail
            if self.investments:
                lines.append('')
                lines.append('NON-ACCRUAL INVESTMENTS:')
                for inv in self.investments:
                    fv_str = f'FV=${inv.fair_value:,.0f}' if inv.fair_value is not None else 'FV=unknown'
                    lines.append(f'  {inv.company_name} ({inv.investment_type}) — {fv_str}')

            lines.append('')
            lines.append('AVAILABLE ACTIONS:')
            lines.append('  .investments         List of NonAccrualInvestment objects')
            lines.append('  .nonaccrual_rate     Computed non-accrual rate at fair value')
            lines.append('  .num_nonaccrual      Count of non-accrual investments (None unless itemized)')
            lines.append('  .evidence_level      investment | aggregate | none')
            lines.append('  .nonaccrual_fair_value   Sum of non-accrual fair values')
            return '\n'.join(lines)

        # Full detail: include cost, identifier, and footnote per investment
        if self.investments:
            lines.append('')
            lines.append('NON-ACCRUAL INVESTMENTS (FULL DETAIL):')
            for inv in self.investments:
                lines.append(f'  Investment: {inv.company_name}')
                lines.append(f'    Type: {inv.investment_type}')
                lines.append(f'    Identifier: {inv.identifier}')
                if inv.fair_value is not None:
                    lines.append(f'    Fair Value: ${inv.fair_value:,.0f}')
                if inv.cost is not None:
                    lines.append(f'    Cost: ${inv.cost:,.0f}')
                    if inv.fair_value is not None and inv.cost > 0:
                        unrealized = inv.fair_value - inv.cost
                        lines.append(f'    Unrealized Gain/Loss: ${unrealized:,.0f}')
                lines.append(f'    Footnote: "{inv.footnote_text}"')

        lines.append('')
        lines.append('AVAILABLE ACTIONS:')
        lines.append('  .investments         List of NonAccrualInvestment objects')
        lines.append('  .nonaccrual_rate     Computed non-accrual rate at fair value')
        lines.append('  .num_nonaccrual      Count of non-accrual investments (None unless itemized)')
        lines.append('  .evidence_level      investment | aggregate | none')
        lines.append('  .nonaccrual_fair_value   Sum of non-accrual fair values')
        lines.append('  .unique_footnote_texts   Distinct source footnote texts')
        return '\n'.join(lines)


def extract_nonaccrual(
    source: Union[Filing, BDCEntity],
    form: str = "10-K",
    period: Optional[str] = None,
) -> Optional[NonAccrualResult]:
    """
    Extract non-accrual data from a BDC filing using all available structured sources.

    Tries three extraction methods in order of richness:

    1. **XBRL footnotes** — scans footnote text for non-accrual patterns, follows
       related_fact_ids to identify specific investments with their fair values.
    2. **Custom XBRL concepts** — searches facts for concepts containing "nonaccrual".
    3. **Standard us-gaap aggregate** — checks one standard concept.
    4. **A tagged zero** — an amount or count of non-accruals tagged as 0, when no
       footnote flags non-accrual, gives a 0% rate.

    All three results are captured in NonAccrualResult for cross-validation.

    Args:
        source: A Filing object or BDCEntity. If BDCEntity, fetches latest filing.
        form: Filing form type (default "10-K"). Only used with BDCEntity.
        period: Reporting period (e.g., "2025-12-31"). If None, uses the filing's
            period of report. Either is read as given: a filing with no investment
            data at that period gives a result at that period with no rate.

    Returns:
        NonAccrualResult if the filing could be parsed, None if XBRL unavailable.
    """
    filing = _resolve_filing(source, form)
    if filing is None:
        return None

    result = _extract_nonaccrual_from_filing(filing, period)
    if result is not None and _is_bdc_entity(source):
        # A full-document 10-K/A supersedes the original; a cover-page or
        # exhibit-only amendment carries no investment data and is ignored (GH #1713).
        for amendment in _later_amendments(source, form, filing):
            amended = _extract_nonaccrual_from_filing(amendment, period)
            if amended is not None and amended.total_portfolio_fair_value:
                return amended
    return result


def _is_bdc_entity(source) -> bool:
    from edgar.bdc.reference import BDCEntity
    return isinstance(source, BDCEntity)


def _later_amendments(source, form: str, original) -> list:
    """Amendments of ``original`` (same period), newest first."""
    amendments = []
    for f in source.get_filings(form=form):
        if (f.form == f"{form}/A"
                and f.period_of_report == original.period_of_report
                and str(f.filing_date) >= str(original.filing_date)):
            amendments.append(f)
    return sorted(amendments, key=lambda f: str(f.filing_date), reverse=True)


def _extract_nonaccrual_from_filing(filing, period: Optional[str] = None) -> Optional[NonAccrualResult]:
    xbrl = filing.xbrl()
    if xbrl is None:
        return None

    # With no period given, read the filing's report date, never a filing or
    # DEI date found among its facts.
    if period is None:
        period = getattr(filing, 'period_of_report', None)

    result = _extract_nonaccrual_from_xbrl(
        xbrl,
        period=period,
        cik=filing.cik,
        entity_name=filing.company,
        accession_number=filing.accession_no,
    )
    if result is not None and result.extraction_method == 'none' and not result.total_portfolio_fair_value:
        result.warnings.append(
            f"Filing {filing.accession_no} ({filing.form}) has no investment data; it may be an "
            f"amendment without a schedule of investments, so no non-accrual figures were extracted."
        )
    return result


def _extract_nonaccrual_from_xbrl(
    xbrl,
    period: Optional[str] = None,
    cik: int = 0,
    entity_name: str = "",
    accession_number: str = "",
    all_facts: Optional[List[dict]] = None,
) -> Optional[NonAccrualResult]:
    """
    Core extraction logic operating on a parsed XBRL object.

    This is the internal function that can be called from both
    ``extract_nonaccrual()`` and ``PortfolioInvestments.from_xbrl()``.

    Args:
        all_facts: Pre-fetched enriched facts from ``xbrl.facts.get_facts()``.
            Pass this when the caller already has the facts to avoid a
            redundant rebuild of the full enriched fact list.
    """
    if all_facts is None:
        all_facts = xbrl.facts.get_facts()
    fact_by_id: Dict[str, dict] = {
        f['fact_id']: f for f in all_facts if f.get('fact_id')
    }

    # A known period is read as given, even when the filing has no investment
    # data there; the result then has no rate (edgartools-a3m66).
    if period is None:
        period = _determine_latest_instant(all_facts)
    if period is None:
        return None

    # Total portfolio fair value (rate denominator)
    total_fv, total_source = _portfolio_total_fair_value(all_facts, period)

    # --- Layer 1: Footnote extraction ---
    nonaccrual_investments, recognized_footnotes = _extract_from_footnotes(
        xbrl, fact_by_id, all_facts, period
    )

    # --- Layer 2: Custom concept search ---
    custom_concept_rate = _extract_custom_concept_rate(all_facts, period, total_fv)

    # --- Layer 3: Standard aggregate ---
    aggregate_value = _extract_aggregate_concept(all_facts, period)

    # Determine primary extraction method and compute nonaccrual FV
    if nonaccrual_investments:
        method = 'footnote'
        nonaccrual_fv = sum(
            (inv.fair_value for inv in nonaccrual_investments if inv.fair_value),
            Decimal(0),
        )
    elif custom_concept_rate is not None:
        method = 'custom_concept'
        nonaccrual_fv = (
            Decimal(str(custom_concept_rate)) * total_fv
            if total_fv
            else None
        )
    elif aggregate_value is not None:
        method = 'aggregate_concept'
        nonaccrual_fv = aggregate_value
    elif recognized_footnotes == 0 and _tagged_zero(all_facts, period):
        # A footnote flag outranks a tagged zero, even one that resolved no
        # holdings: Antares Strategic Credit tags PortfolioCompaniesNonAccrual = 0
        # beside "Position is on non-accrual status".
        method = 'tagged_zero'
        nonaccrual_fv = Decimal(0)
    else:
        method = 'none'
        nonaccrual_fv = None

    warnings = _build_warnings(
        method=method,
        total_fv=total_fv,
        recognized_footnotes=recognized_footnotes,
        num_investments=len(nonaccrual_investments),
        period=period,
    )

    return NonAccrualResult(
        cik=cik,
        entity_name=entity_name,
        period=period,
        source_filing=accession_number,
        investments=nonaccrual_investments,
        nonaccrual_fair_value=nonaccrual_fv,
        total_portfolio_fair_value=total_fv,
        extraction_method=method,
        custom_concept_rate=custom_concept_rate,
        aggregate_concept_value=aggregate_value,
        warnings=warnings,
        total_source=total_source,
    )


def _build_warnings(
    method: str,
    total_fv: Optional[Decimal],
    recognized_footnotes: int,
    num_investments: int,
    period: str,
) -> List[str]:
    """Surface suspicious extraction outcomes so empty results aren't silent.

    Two high-signal, low-false-positive checks:

    * **Silence** — a real portfolio but no non-accrual signal from any layer.
      Usually genuine (healthy BDC), but worth flagging because the original
      #835 symptom looked exactly like this.
    * **Linkage gap** — footnotes were recognized as non-accrual flags but none
      of their linked investments resolved for *period* (likely a period or
      linkage mismatch, not a true zero).
    """
    warnings: List[str] = []

    if recognized_footnotes > 0 and num_investments == 0:
        warnings.append(
            f"Recognized {recognized_footnotes} non-accrual footnote(s) but "
            f"resolved no investments for period {period}; investment-level "
            f"detail may be incomplete (possible period or linkage mismatch)."
        )

    if method == 'none' and total_fv is not None and total_fv > 0:
        warnings.append(
            f"No non-accrual data extracted despite a portfolio of "
            f"${total_fv:,.0f}; verify manually — this may indicate a parsing "
            f"gap rather than genuinely zero non-accruals."
        )

    return warnings


# ---------------------------------------------------------------------------
# Layer 1: Footnote-based extraction
# ---------------------------------------------------------------------------

def _dims(fact: dict) -> Dict[str, str]:
    """The fact's dimensions as ``{axis key: member}``."""
    return {key: value for key, value in fact.items() if key.startswith('dim_') and value}


def _position_key(fact: dict):
    """What identifies one holding: its identifier member, or its whole dimension set."""
    return fact.get(DIM_KEY) or frozenset(_dims(fact).items())


def _schedule_on_identifier_axis(all_facts: List[dict], period: str) -> bool:
    """Whether the filing tags its schedule of investments on InvestmentIdentifierAxis for *period*."""
    return any(f.get(DIM_KEY) and f.get('concept') == CONCEPT_FAIR_VALUE
               and f.get('period_instant') == period for f in all_facts)


def _fair_values_by_position(all_facts: List[dict]) -> Dict[tuple, List[dict]]:
    """Dimensioned InvestmentOwnedAtFairValue facts keyed by ``(_position_key, instant)``."""
    index: Dict[tuple, List[dict]] = {}
    for fact in all_facts:
        if fact.get('concept') == CONCEPT_FAIR_VALUE and _dims(fact):
            index.setdefault((_position_key(fact), fact.get('period_instant')), []).append(fact)
    return index


def _investment_fv_facts_for_footnote(
    footnote,
    fact_by_id: Dict[str, dict],
    identifier_axis: bool = True,
    fv_by_position: Optional[Dict[tuple, List[dict]]] = None,
) -> List[dict]:
    """Enriched investment fair-value facts a footnote is linked to (any period).

    With ``identifier_axis`` only facts on InvestmentIdentifierAxis count. Without
    it, any dimensioned fact does: schedules tagged before the identifier axis
    name a holding by a set of axes instead (TPVG FY2024: industry, instrument,
    loan and a company axis of its own; edgartools-jv32z).

    A footnote linked to another cell of a holding's row stands for that
    holding's fair value at the same date. New Mountain Finance attaches its
    non-accrual footnote to the PIK rate and spread, never the fair value, and
    SuRo to the principal (edgartools-jv8b8); ``fv_by_position`` (from
    ``_fair_values_by_position``) resolves them. Only instant facts resolve: a
    flag on a duration fact is not a flag at its end date (Logan Ridge marks
    its Q1 2025 industry name for a loan its schedule does not mark).
    Undimensioned facts are never positions, so a footnote on a total pulls in
    nothing.
    """
    facts: List[dict] = []
    seen: set = set()
    for fact_id in footnote.related_fact_ids:
        enriched = fact_by_id.get(fact_id)
        if enriched is None:
            continue
        if identifier_axis:
            if enriched.get(DIM_KEY) is None:
                continue
        elif not _dims(enriched):
            continue
        if enriched.get('concept', '') == CONCEPT_FAIR_VALUE:
            resolved = [enriched]
        elif fv_by_position is not None and enriched.get('period_instant'):
            resolved = fv_by_position.get((_position_key(enriched), enriched['period_instant']), [])
        else:
            continue
        for fact in resolved:
            key = fact.get('fact_id') or (fact.get('concept'), _position_key(fact), fact.get('period_instant'))
            if key not in seen:
                seen.add(key)
                facts.append(fact)
    return facts


def _drop_subtotals(flagged: List[Tuple[dict, str]]) -> List[Tuple[dict, str]]:
    """Drop facts that roll up other flagged facts.

    Off the identifier axis a footnote can annotate a company's or an industry's
    subtotal as well as its loans: TPVG links "Nakd.com One World AB" at $8.47M
    (no loan member) beside its two loans of $3.18M and $5.29M, and a "Financial
    Software" industry total. A fact whose dimensions are a proper subset of
    another flagged fact's is such a roll-up.
    """
    dim_sets = [frozenset(_dims(fact).items()) for fact, _ in flagged]
    return [pair for pair, dims in zip(flagged, dim_sets, strict=True)
            if not any(dims < other for other in dim_sets)]


# Axes that name the portfolio company when a schedule is not on the identifier
# axis: tpvg:PortfolioCompaniesAxis, us-gaap:RelatedPartyTransactionsByRelatedPartyAxis (OXSQ).
_COMPANY_AXIS_RE = re.compile(r'compan|relatedparty|investee|borrower|obligor', re.IGNORECASE)
# Axes that name the instrument, most specific first
_INSTRUMENT_AXES = (
    'dim_us-gaap_InvestmentTypeAxis',
    'dim_us-gaap_StatementClassOfStockAxis',
    'dim_us-gaap_LienCategoryAxis',
    'dim_us-gaap_LongtermDebtTypeAxis',
    'dim_us-gaap_FinancialInstrumentAxis',
)
_LABEL_ROLES = (
    'http://www.xbrl.org/2003/role/label',
    'http://www.xbrl.org/2003/role/terseLabel',
    'http://www.xbrl.org/2003/role/verboseLabel',
)


def _member_label(xbrl, member: str) -> str:
    """A member's label without its "[Member]" suffix.

    A label ending in "[Member]" is the one the filer wrote. OXSQ's standard
    label is generated from the element name ("Uni Tek Global Services Inc
    Member") while its terse label reads "UniTek Global Services, Inc. [Member]";
    TPVG's terse label drops the loan's number that its standard label keeps.
    """
    element = xbrl.element_catalog.get(member.replace(':', '_'))
    labels = getattr(element, 'labels', None) or {}
    candidates = [labels[role] for role in _LABEL_ROLES if labels.get(role)]
    written = [label for label in candidates if re.search(r'\[Member\]\s*$', label)]
    label = (written or candidates or [member.split(':')[-1]])[0]
    return re.sub(r'\s*(?:\[Member\]|Member)\s*$', '', label).strip()


def _describe_dimensional_position(xbrl, fact: dict) -> Tuple[str, str, str]:
    """``(identifier, company_name, investment_type)`` for a holding named by several axes."""
    dims = _dims(fact)
    company_axis = next((axis for axis in sorted(dims) if _COMPANY_AXIS_RE.search(axis)), None)
    company = _member_label(xbrl, dims[company_axis]) if company_axis else ''
    instrument_axis = next((axis for axis in _INSTRUMENT_AXES if axis in dims), None)
    investment_type = _member_label(xbrl, dims[instrument_axis]) if instrument_axis else 'Unknown'
    others = [_member_label(xbrl, dims[axis]) for axis in sorted(dims) if axis != company_axis]
    identifier = ' | '.join(part for part in [company, *others] if part)
    return identifier, company or identifier, investment_type


def _extract_from_footnotes(
    xbrl,
    fact_by_id: Dict[str, dict],
    all_facts: List[dict],
    period: str,
) -> Tuple[List[NonAccrualInvestment], int]:
    """Scan XBRL footnotes for non-accrual flags, follow links to investments.

    Returns ``(investments, recognized_footnote_count)``. The count is the
    number of footnotes classified as non-accrual flags (regardless of whether
    their linkage resolved to investments for *period*); callers use it to tell
    "no non-accrual footnotes" apart from "flags found but nothing resolved".
    """
    footnotes = xbrl.footnotes
    if not footnotes:
        return [], 0

    identifier_axis = _schedule_on_identifier_axis(all_facts, period)
    fv_by_position = _fair_values_by_position(all_facts)
    flagged: List[Tuple[dict, str]] = []
    recognized = 0

    for footnote in footnotes.values():
        # Only process English footnotes
        lang = getattr(footnote, 'lang', 'en-US') or 'en-US'
        if not lang.startswith('en'):
            continue

        text_lower = footnote.text.lower()

        # Pre-compute investment linkage so the classifier can use structure
        # as corroboration for wording it doesn't recognize.
        linked_fv_facts = _investment_fv_facts_for_footnote(footnote, fact_by_id, identifier_axis, fv_by_position)
        linked_to_investments = bool(linked_fv_facts)

        if not _classify_nonaccrual_footnote(text_lower, linked_to_investments):
            continue

        recognized += 1

        # This footnote flags non-accrual status for its linked investments.
        flagged.extend((enriched, footnote.text) for enriched in linked_fv_facts
                       if enriched.get('period_instant') == period)

    if not identifier_axis:
        flagged = _drop_subtotals(flagged)

    seen_positions: set = set()
    investments: List[NonAccrualInvestment] = []
    # Bound company names by the filing's own members, as from_xbrl does; built on first use.
    member_candidates = None

    for enriched, footnote_text in flagged:
        # Deduplicate by holding
        position = _position_key(enriched)
        if position in seen_positions:
            continue
        seen_positions.add(position)

        inv_identifier = enriched.get(DIM_KEY)
        if inv_identifier:
            if member_candidates is None:
                member_candidates = _get_investment_member_candidates(xbrl)
            _id, company_name, investment_type = _parse_investment_identifier(inv_identifier, member_candidates)
        else:
            inv_identifier, company_name, investment_type = _describe_dimensional_position(xbrl, enriched)
        cost = _find_cost_for_investment(all_facts, position, period)

        fv = None
        numeric = enriched.get('numeric_value')
        if numeric is not None and not pd.isna(numeric):
            try:
                fv = Decimal(str(numeric))
            except (ValueError, InvalidOperation):
                pass

        investments.append(NonAccrualInvestment(
            identifier=inv_identifier,
            company_name=company_name,
            investment_type=investment_type,
            fair_value=fv,
            cost=cost,
            footnote_text=footnote_text,
        ))

    if identifier_axis:
        investments = _drop_restated(investments)
    return investments, recognized


def _drop_restated(investments: List[NonAccrualInvestment]) -> List[NonAccrualInvestment]:
    """Leave out flagged rows that restate another flagged row.

    Identifier-axis members carry no hierarchy, so a holding listed again in a
    second schedule is a second row. Logan Ridge's FY2024 10-K flags MMI
    Holdings in its schedule (with cost) and again under "Affiliate
    investments" (without), so its non-accruals read $10.86M where the filing
    states $7.9M (edgartools-wg5n8). The rule is the one
    ``PortfolioInvestments.from_xbrl`` applies to the whole schedule, run over
    the flagged rows only, so a row is dropped only when the row it restates is
    flagged too.
    """
    rows = [PortfolioInvestment(identifier=inv.identifier, company_name=inv.company_name,
                                investment_type=inv.investment_type, fair_value=inv.fair_value, cost=inv.cost)
            for inv in investments]
    kept, _excluded = _exclude_restated_rows(rows)
    return [inv for inv, row in zip(investments, rows, strict=True) if any(row is k for k in kept)]


# ---------------------------------------------------------------------------
# Layer 2: Custom XBRL concept search
# ---------------------------------------------------------------------------

def _extract_custom_concept_rate(
    all_facts: List[dict],
    period: str,
    total_fv: Optional[Decimal],
) -> Optional[float]:
    """Search for BDC-specific custom taxonomy concepts containing 'nonaccrual'.

    Prioritizes fair-value-based percentages over cost-based ones and dollar
    amounts.  Percentage values filed as decimals (0.012 = 1.2%) are returned
    as-is; values filed as whole-number percentages (> 1) are divided by 100.
    """
    # Collect all matching facts for this period, then pick the best one
    candidates: List[Tuple[str, float, str]] = []  # (priority, value, concept)

    for fact in all_facts:
        concept = (fact.get('concept') or '').lower()
        if 'nonaccrual' not in concept and 'non_accrual' not in concept:
            continue

        # Skip per-investment facts
        if fact.get(DIM_KEY):
            continue

        # Check period
        if fact.get('period_instant') != period and fact.get('period_end') != period:
            continue

        value = fact.get('numeric_value')
        if value is None or pd.isna(value):
            continue

        is_pct = 'percent' in concept or 'rate' in concept
        is_fv = 'fairvalue' in concept or 'fv' in concept
        is_cost = 'cost' in concept
        is_amount = 'amount' in concept or 'fairvalue' in concept or 'fv' in concept

        if is_pct:
            # Heuristic: values < 1 are decimal fractions (0.012 = 1.2%),
            # values >= 1 are whole-number percentages (1.2 = 1.2%).
            # Safe for non-accrual rates which are almost always < 10%.
            # A rate of exactly 100% (value=1.0) would be misclassified,
            # but no BDC has 100% non-accrual and still files.
            rate = float(value) if float(value) < 1 else float(value) / 100.0
            # Prefer FV-based percentage over cost-based
            priority = 'a_fv_pct' if is_fv else ('b_cost_pct' if is_cost else 'c_pct')
            candidates.append((priority, rate, concept))
        elif is_amount and not is_pct:
            if total_fv and total_fv > 0:
                rate = float(Decimal(str(value)) / total_fv)
                candidates.append(('d_amount', rate, concept))
        # 'count'/'number' concepts don't give us a rate — skip

    if not candidates:
        return None

    # Return the best candidate (lowest priority key = highest priority)
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


# ---------------------------------------------------------------------------
# Layer 3: Standard us-gaap aggregate concept
# ---------------------------------------------------------------------------

def _extract_aggregate_concept(
    all_facts: List[dict],
    period: str,
) -> Optional[Decimal]:
    """Check the standard us-gaap aggregate non-accrual concept."""
    for fact in all_facts:
        if (fact.get('concept') == CONCEPT_NONACCRUAL_LOANS_FV
                and fact.get('period_instant') == period
                and not fact.get(DIM_KEY)):
            value = fact.get('numeric_value')
            if value is not None and not pd.isna(value):
                try:
                    return Decimal(str(value))
                except (ValueError, InvalidOperation):
                    pass
    return None


# ---------------------------------------------------------------------------
# Layer 4: a tagged zero
# ---------------------------------------------------------------------------

# Non-accrual concepts whose zero does not mean "no investments on non-accrual":
# policy text, the days-past-due threshold, interest income recognized on
# non-accrual loans, and the part of them with no allowance.
_NOT_A_NONACCRUAL_BALANCE = re.compile(
    r'textblock|policy|threshold|pastdue|income|allowance|writeoff|reversal|reversed|recover'
)


def _tagged_zero(all_facts: List[dict], period: str) -> bool:
    """Whether the filer tags its non-accruals at *period* as zero, and nothing else.

    Many BDCs with no non-accruals have no footnote to read but tag an amount or
    count of zero: Stone Point Credit tags
    us-gaap:FinancingReceivableRecordedInvestmentNonaccrualStatus = 0, AGL
    NumberPortfolioCompanyInvestmentOnNonAccrualStatus = 0 (edgartools-rol2k).
    Only undimensioned facts at the instant count, and all of them must be zero:
    a non-zero amount or count, at cost or at fair value, rules it out.
    """
    found = False
    for fact in all_facts:
        concept = (fact.get('concept') or '').lower()
        if 'nonaccrual' not in concept and 'non_accrual' not in concept:
            continue
        if _NOT_A_NONACCRUAL_BALANCE.search(concept):
            continue
        if fact.get('period_instant') != period or _dims(fact):
            continue
        value = fact.get('numeric_value')
        if value is None or pd.isna(value):
            continue
        if float(value) != 0:
            return False
        found = True
    return found


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _resolve_filing(source, form: str = "10-K"):
    """Resolve a Filing or BDCEntity to a Filing object."""
    from edgar._filings import Filing
    from edgar.bdc.reference import BDCEntity

    if isinstance(source, Filing):
        return source
    elif isinstance(source, BDCEntity):
        # Amendments often carry no investment data (e.g. ARCC's 10-K/A adds a subsidiary's statements)
        filings = source.get_filings(form=form, amendments=False)
        if filings and len(filings) > 0:
            return filings.latest(1)
        return None
    else:
        raise TypeError(f"Expected Filing or BDCEntity, got {type(source).__name__}")


def _determine_latest_instant(facts: List[dict]) -> Optional[str]:
    """Find the period_instant to read when neither the caller nor the filing gives one.

    The most common instant among investment facts (not max, which is
    susceptible to outlier dates like filing dates), else the most common
    instant of any fact. A known period is never replaced by this: a cover-page
    10-K/A was labelled with its public-float date, and a 10-Q whose schedule
    carries another quarter's dates with that quarter (edgartools-a3m66).
    """
    from collections import Counter
    investment_instants: Counter = Counter()
    all_instants: Counter = Counter()
    for f in facts:
        pi = f.get('period_instant')
        if not pi:
            continue
        all_instants[pi] += 1
        if f.get(DIM_KEY):
            investment_instants[pi] += 1

    if investment_instants:
        return investment_instants.most_common(1)[0][0]
    if all_instants:
        return all_instants.most_common(1)[0][0]
    return None


def _portfolio_total_fair_value(facts: List[dict], period: str) -> Tuple[Optional[Decimal], Optional[str]]:
    """The rate denominator and where it came from.

    The balance-sheet total comes first. Many filers also tag subtotals and
    totals on ``InvestmentIdentifierAxis`` ("Total Investments", "Debt
    Investments", country and lien subtotals), so adding up the identifier rows
    counted GSCR's FY2024 portfolio as $45.4B against a $7.27B balance sheet
    (edgartools-7vl3h). The sum is only a fallback for filers with no total.
    """
    reported, _unit = _reported_total_fair_value(facts, period)
    if reported is not None:
        return reported, 'balance_sheet'
    split = _affiliation_split_total(facts, period)
    if split is not None:
        return split, 'balance_sheet'
    tagged = _identifier_grand_total(facts, period)
    if tagged is not None:
        return tagged, 'identifier_total'
    summed = _sum_portfolio_fair_value(facts, period)
    return (summed, 'schedule_sum') if summed is not None else (None, None)


_AFFILIATION_AXIS = 'dim_us-gaap_InvestmentIssuerAffiliationAxis'
# us-gaap's affiliated member is the parent of its controlled and non-controlled members
_AFFILIATED_PARENT = 'us-gaap:InvestmentAffiliatedIssuerMember'
_AFFILIATED_CHILDREN = ('us-gaap:InvestmentAffiliatedIssuerControlledMember',
                        'us-gaap:InvestmentAffiliatedIssuerNoncontrolledMember')


def _affiliation_split_total(facts: List[dict], period: str) -> Optional[Decimal]:
    """The balance sheet's investments added up from its affiliation lines, or None.

    A balance sheet can carry only the split ("Non-affiliated/non-control
    investments", "Affiliated investments") with no undimensioned total: OXSQ
    FY2024 tags 256,238,759 + 4,614,100 = 260,852,859 this way
    (edgartools-jv32z). Only facts on that axis alone count, the most precise
    per member, and at least two members, so one line is never taken for the whole.
    """
    best: Dict[str, Tuple[float, Decimal]] = {}
    for fact in facts:
        if fact.get('concept') != CONCEPT_FAIR_VALUE or fact.get('period_instant') != period:
            continue
        dims = _dims(fact)
        if list(dims) != [_AFFILIATION_AXIS]:
            continue
        value = fact.get('numeric_value')
        if value is None or pd.isna(value):
            continue
        decimals = str(fact.get('decimals'))
        try:
            precision = float('inf') if decimals.upper() == 'INF' else float(decimals)
        except ValueError:
            precision = -99.0
        member = dims[_AFFILIATION_AXIS]
        if member not in best or precision > best[member][0]:
            best[member] = (precision, Decimal(str(value)))
    if _AFFILIATED_PARENT in best and any(child in best for child in _AFFILIATED_CHILDREN):
        del best[_AFFILIATED_PARENT]
    # A filer's own member restating a us-gaap line is one line, not two. SLR HC
    # BDC tags its 96,665,000 of non-affiliated investments under both its
    # custom member and us-gaap:InvestmentUnaffiliatedIssuerMember, which summed
    # to twice its total (edgartools-m4qnb).
    standard_values = {value for member, (_, value) in best.items() if member.startswith('us-gaap:')}
    for member in [m for m, (_, value) in best.items()
                   if not m.startswith('us-gaap:') and value in standard_values]:
        del best[member]
    if len(best) < 2:
        return None
    return sum((value for _, value in best.values()), Decimal(0))


# A grand-total row's member name: "Investments", "Investments in Securities",
# "Total Investments - 148.3%". Not "... and Cash Equivalents" or "Net Assets".
_GRAND_TOTAL_MEMBER = re.compile(
    r'^\s*(?:total\s+)?investments(?:\s+in\s+securities)?(?:\s+at\s+fair\s+value)?'
    r'(?:\s*[-\u2013]\s*[\d.,]+\s*%)?\s*$', re.IGNORECASE)


def _identifier_grand_total(facts: List[dict], period: str) -> Optional[Decimal]:
    """The filer's grand total when it is tagged as an identifier-axis member, or None.

    With no balance-sheet total, the identifier rows were summed, subtotals and
    totals included. Oxford Square's 10-Q for 2026-03-31 tags "Investments in
    Securities" = $235,372,463 as a member and summed to $1.30B; Muzinich BDC
    tags "Investments" = $214,085,177 against a $819M sum (edgartools-cpd1b).
    Only a member named as the whole portfolio counts, and only when one value
    is named so.
    """
    values = set()
    for fact in facts:
        if (fact.get('concept') != CONCEPT_FAIR_VALUE or fact.get('period_instant') != period
                or list(_dims(fact)) != [DIM_KEY]):
            continue
        if not _GRAND_TOTAL_MEMBER.match(str(fact.get(DIM_KEY))):
            continue
        value = fact.get('numeric_value')
        if value is not None and not pd.isna(value):
            values.add(Decimal(str(value)))
    return values.pop() if len(values) == 1 else None


def _sum_portfolio_fair_value(facts: List[dict], period: str) -> Optional[Decimal]:
    """Sum all InvestmentOwnedAtFairValue facts for the period on InvestmentIdentifierAxis."""
    total = Decimal(0)
    found_any = False

    for f in facts:
        if (f.get('concept') == CONCEPT_FAIR_VALUE
                and f.get('period_instant') == period
                and f.get(DIM_KEY)):
            value = f.get('numeric_value')
            if value is not None and not pd.isna(value):
                try:
                    total += Decimal(str(value))
                    found_any = True
                except (ValueError, InvalidOperation):
                    pass

    return total if found_any else None


def _find_cost_for_investment(
    facts: List[dict],
    position,
    period: str,
) -> Optional[Decimal]:
    """Find the InvestmentOwnedAtCost fact for a holding (see ``_position_key``) and period."""
    for f in facts:
        if (f.get('concept') == CONCEPT_COST
                and f.get('period_instant') == period
                and _position_key(f) == position):
            value = f.get('numeric_value')
            if value is not None and not pd.isna(value):
                try:
                    return Decimal(str(value))
                except (ValueError, InvalidOperation):
                    pass
    return None


def extract_nonaccrual_batch(
    form: str = "10-K",
    active_only: bool = True,
) -> List[NonAccrualResult]:
    """
    Extract non-accrual data for all BDCs.

    Args:
        form: Filing form type (default "10-K").
        active_only: Only process actively filing BDCs.

    Returns:
        List of NonAccrualResult, one per BDC (None entries excluded).
    """
    from edgar.bdc.reference import get_bdc_list

    bdcs = get_bdc_list()
    if active_only:
        bdcs = bdcs.filter(active=True)

    results: List[NonAccrualResult] = []
    for bdc in bdcs:
        try:
            result = extract_nonaccrual(bdc, form=form)
            if result is not None:
                results.append(result)
        except Exception as e:
            log.warning(f"Failed to extract non-accrual for {bdc.name}: {e}")

    return results
