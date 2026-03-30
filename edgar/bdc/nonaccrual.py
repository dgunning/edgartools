"""
Non-accrual investment extraction from BDC filings.

Extracts non-accrual status data using three layered approaches:

1. **XBRL footnotes** — richest source. Scans footnote text for non-accrual patterns,
   follows related_fact_ids to identify specific investments with fair values.
2. **Custom XBRL concepts** — 6/11 BDCs use proprietary taxonomy extensions
   (rate only, no investment-level detail).
3. **Standard us-gaap aggregate** — single concept fallback (dollar amount only).

Usage::

    from edgar import Company
    from edgar.bdc.nonaccrual import extract_nonaccrual

    filing = Company("ARCC").get_filings(form="10-K").latest()
    result = extract_nonaccrual(filing)
    print(result.nonaccrual_rate)       # e.g. 0.012
    print(result.num_nonaccrual)        # e.g. 20
    for inv in result.investments:
        print(inv.company_name, inv.fair_value)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Union

import pandas as pd

from edgar.bdc.investments import _parse_investment_identifier

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

# Negation patterns — footnotes that explicitly deny non-accrual status.
# These must be checked BEFORE affirmative patterns.
# Examples: "there were no investments on non-accrual status",
#           "the Company had no portfolio company investment on non-accrual"
NEGATION_PATTERNS = [
    r'\bno\s+(?:investments?|loans?|portfolio\s+company).{0,40}non[- ]?accrual',
    r'\bnone\b.{0,40}non[- ]?accrual',
    r'(?:were|was|is|are)\s+not\s+(?:on\s+)?non[- ]?accrual',
    r'did\s+not\s+have\s+any.{0,40}non[- ]?accrual',
    r'\bzero\b.{0,40}non[- ]?accrual',
    r'there\s+were\s+no.{0,40}non[- ]?accrual',
]

# Affirmative patterns — footnotes that directly state an investment is on non-accrual.
# Uses a whitelist approach: a footnote must contain an explicit affirmative statement
# to be treated as a non-accrual flag. This avoids false positives from rollforward
# tables or policy disclosures that mention "non-accrual" in passing.
AFFIRMATIVE_PATTERNS = [
    r'(?:was|were)\s+(?:on|placed\s+on)\s+non[- ]?accrual\s+status',
    r'(?:was|were)\s+(?:on|placed\s+on)\s+non[- ]?accrual(?:\s|[,.])',
    r'(?:is|are)\s+(?:on|currently\s+on)\s+non[- ]?accrual\s+status',
    r'(?:is|are)\s+(?:on|currently\s+on)\s+non[- ]?accrual(?:\s|[,.])',
    r'(?:loan|debt|investment)\s+was\s+(?:on|placed\s+on)\s+non[- ]?accrual',
    r'(?:loan|debt|investment)\s+is\s+(?:on|currently\s+on)\s+non[- ]?accrual',
    r'^non[- ]?accrual\s+and\s+non[- ]?income',
    r'the\s+investment\s+is\s+on\s+non[- ]?accrual',
]


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
    extraction_method: str  # 'footnote' | 'custom_concept' | 'aggregate_concept' | 'none'
    custom_concept_rate: Optional[float] = None
    aggregate_concept_value: Optional[Decimal] = None

    @property
    def nonaccrual_rate(self) -> Optional[float]:
        """Non-accrual rate at fair value. Primary metric."""
        if self.nonaccrual_fair_value is None or self.total_portfolio_fair_value is None:
            return None
        if self.total_portfolio_fair_value == 0:
            return 0.0
        return float(self.nonaccrual_fair_value / self.total_portfolio_fair_value)

    @property
    def num_nonaccrual(self) -> int:
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
        lines.append(f'Non-Accrual Investments: {self.num_nonaccrual}')
        if self.nonaccrual_fair_value is not None:
            lines.append(f'Non-Accrual Fair Value: ${self.nonaccrual_fair_value:,.0f}')
        if self.total_portfolio_fair_value is not None:
            lines.append(f'Total Portfolio Fair Value: ${self.total_portfolio_fair_value:,.0f}')
        lines.append(f'Extraction Method: {self.extraction_method}')

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
            lines.append('  .num_nonaccrual      Count of non-accrual investments')
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
        lines.append('  .num_nonaccrual      Count of non-accrual investments')
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

    All three results are captured in NonAccrualResult for cross-validation.

    Args:
        source: A Filing object or BDCEntity. If BDCEntity, fetches latest filing.
        form: Filing form type (default "10-K"). Only used with BDCEntity.
        period: Reporting period (e.g., "2025-12-31"). If None, uses latest instant.

    Returns:
        NonAccrualResult if the filing could be parsed, None if XBRL unavailable.
    """
    filing = _resolve_filing(source, form)
    if filing is None:
        return None

    xbrl = filing.xbrl()
    if xbrl is None:
        return None

    # Use filing's reporting period as anchor when no explicit period given.
    # This avoids resolving to filing dates or DEI dates instead of balance sheet dates.
    if period is None:
        period = getattr(filing, 'period_of_report', None)

    return _extract_nonaccrual_from_xbrl(
        xbrl,
        period=period,
        cik=filing.cik,
        entity_name=filing.company,
        accession_number=filing.accession_no,
    )


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

    # Determine period — _determine_latest_instant is only reached when
    # extract_nonaccrual couldn't provide a period_of_report anchor
    if period is None:
        period = _determine_latest_instant(all_facts)
    else:
        # Validate that the provided period has investment data, fall back if not
        period = _determine_latest_instant(all_facts, anchor_period=period)
    if period is None:
        return None

    # Total portfolio fair value (rate denominator)
    total_fv = _sum_portfolio_fair_value(all_facts, period)

    # --- Layer 1: Footnote extraction ---
    nonaccrual_investments = _extract_from_footnotes(xbrl, fact_by_id, all_facts, period)

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
    else:
        method = 'none'
        nonaccrual_fv = None

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
    )


# ---------------------------------------------------------------------------
# Layer 1: Footnote-based extraction
# ---------------------------------------------------------------------------

def _extract_from_footnotes(
    xbrl,
    fact_by_id: Dict[str, dict],
    all_facts: List[dict],
    period: str,
) -> List[NonAccrualInvestment]:
    """Scan XBRL footnotes for non-accrual text, follow links to investments."""
    footnotes = xbrl.footnotes
    if not footnotes:
        return []

    seen_identifiers: set = set()
    investments: List[NonAccrualInvestment] = []

    for fn_id, footnote in footnotes.items():
        # Only process English footnotes
        lang = getattr(footnote, 'lang', 'en-US') or 'en-US'
        if not lang.startswith('en'):
            continue

        text_lower = footnote.text.lower()

        # Skip footnotes that explicitly deny non-accrual status.
        # e.g., "there were no investments on non-accrual status"
        if any(re.search(p, text_lower) for p in NEGATION_PATTERNS):
            continue

        # Require an explicit affirmative statement about non-accrual status.
        # This avoids false positives from rollforward tables or policy
        # disclosures that mention "non-accrual" in passing.
        if not any(re.search(p, text_lower) for p in AFFIRMATIVE_PATTERNS):
            continue

        # This footnote affirms non-accrual status for linked investments.
        # Follow related_fact_ids to find linked investment facts.
        for fact_id in footnote.related_fact_ids:
            enriched = fact_by_id.get(fact_id)
            if enriched is None:
                continue

            # We want facts on the InvestmentIdentifierAxis with fair value concept
            inv_identifier = enriched.get(DIM_KEY)
            if inv_identifier is None:
                continue

            concept = enriched.get('concept', '')
            if concept != CONCEPT_FAIR_VALUE:
                continue

            # Check period
            if enriched.get('period_instant') != period:
                continue

            # Deduplicate by identifier
            if inv_identifier in seen_identifiers:
                continue
            seen_identifiers.add(inv_identifier)

            _id, company_name, investment_type = _parse_investment_identifier(inv_identifier)
            cost = _find_cost_for_investment(all_facts, inv_identifier, period)

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
                footnote_text=footnote.text,
            ))

    return investments


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
# Helper functions
# ---------------------------------------------------------------------------

def _resolve_filing(source, form: str = "10-K"):
    """Resolve a Filing or BDCEntity to a Filing object."""
    from edgar._filings import Filing
    from edgar.bdc.reference import BDCEntity

    if isinstance(source, Filing):
        return source
    elif isinstance(source, BDCEntity):
        filings = source.get_filings(form=form)
        if filings and len(filings) > 0:
            return filings.latest(1)
        return None
    else:
        raise TypeError(f"Expected Filing or BDCEntity, got {type(source).__name__}")


def _determine_latest_instant(facts: List[dict], anchor_period: Optional[str] = None) -> Optional[str]:
    """Find the best period_instant for investment data extraction.

    When *anchor_period* is provided (typically from ``filing.period_of_report``),
    it is used directly if investment facts exist on that date.  This avoids
    resolving to filing dates, DEI dates, or other non-balance-sheet instants.

    When no anchor is given or the anchor has no investment data, falls back to
    the most common instant among investment facts (not max, which is susceptible
    to outlier dates like filing dates).
    """
    # Collect instants that have investment data
    from collections import Counter
    investment_instants: Counter = Counter()
    for f in facts:
        pi = f.get('period_instant')
        if pi and f.get(DIM_KEY):
            investment_instants[pi] += 1

    # If anchor period has investment data, use it directly
    if anchor_period and anchor_period in investment_instants:
        return anchor_period

    # Pick the most common instant among investment facts
    if investment_instants:
        return investment_instants.most_common(1)[0][0]

    # Fallback: no investment-dimensioned facts at all.
    # Use anchor if it has any facts, otherwise pick the most common instant.
    all_instants: Counter = Counter()
    for f in facts:
        pi = f.get('period_instant')
        if pi:
            all_instants[pi] += 1
    if not all_instants:
        return None

    if anchor_period and anchor_period in all_instants:
        return anchor_period

    return all_instants.most_common(1)[0][0]


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
    identifier: str,
    period: str,
) -> Optional[Decimal]:
    """Find the InvestmentOwnedAtCost fact for a specific investment and period."""
    for f in facts:
        if (f.get('concept') == CONCEPT_COST
                and f.get('period_instant') == period
                and f.get(DIM_KEY) == identifier):
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
