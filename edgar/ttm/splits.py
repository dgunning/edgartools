"""Stock split detection and adjustment utilities.

Provides functions for detecting stock splits from SEC filings and
retroactively adjusting per-share metrics and share counts.
"""
from dataclasses import replace
from typing import Any, Dict, List

from edgar.entity.models import FinancialFact
from edgar.ttm.calculator import MAX_SPLIT_DURATION_DAYS, MAX_SPLIT_LAG_DAYS


def _split_fact_priority(f: FinancialFact) -> int:
    """Return priority score for a split fact (lower is better).

    Prefers 8-K instant facts (most accurate effective date) over
    other instant facts, and instant facts over short-duration facts.
    """
    is_instant = f.period_start is None
    is_8k = f.form_type and f.form_type.startswith('8-K')
    if is_instant and is_8k:
        return 0  # Best: 8-K instant fact — period_end is the event date
    if is_instant:
        return 1  # Good: instant fact from 10-Q/10-K
    return 2      # Acceptable: short-duration fact


def detect_splits(facts: List[FinancialFact]) -> List[Dict[str, Any]]:
    """Detect stock splits from facts.

    Identifies 'StockSplitConversionRatio' facts and filters for valid
    split events (rejecting filing lags and long-duration aggregations).

    When multiple facts report the same split, prefers 8-K instant facts
    whose period_end reflects the actual effective date, over 10-Q/10-K
    facts whose period_end is the reporting period end.
    """
    split_facts = [f for f in facts if 'StockSplitConversionRatio' in f.concept]

    # Collect all valid facts grouped by (year, ratio) to pick the best date
    from collections import defaultdict
    candidates: Dict[tuple, List[FinancialFact]] = defaultdict(list)

    for f in split_facts:
        # Normalize: Ratio > 1 implies forward split (e.g. 10). Adjust by dividing older values.
        if f.numeric_value is not None and f.numeric_value > 0 and f.period_end:
            # Filter out "historical echo" facts (e.g. 2023 10-K reporting a 2020 split)
            if f.filing_date:
                lag = (f.filing_date - f.period_end).days
                if lag > MAX_SPLIT_LAG_DAYS:
                    continue

            # Accept Instant facts OR short-duration facts
            # Instant: period_start is None (true event date)
            # Short duration: Split event reported for the month (e.g., NVDA May 2024 = 30 days)
            # Reject long durations: Comparative quarters/years (90+ days)
            if f.period_start is not None:
                duration_days = (f.period_end - f.period_start).days
                if duration_days > MAX_SPLIT_DURATION_DAYS:
                    continue

            # Group by year and ratio to deduplicate
            split_key = (f.period_end.year, f.numeric_value)
            candidates[split_key].append(f)

    # For each split event, pick the fact with the best date
    splits = []
    for (_year, ratio), fact_group in candidates.items():
        best = min(fact_group, key=_split_fact_priority)
        splits.append({
            'date': best.period_end,
            'ratio': ratio
        })
    splits.sort(key=lambda s: s['date'])
    return splits

def apply_split_adjustments(facts: List[FinancialFact], splits: List[Dict[str, Any]]) -> List[FinancialFact]:
    """Apply retrospective split adjustments to per-share and share-count facts.
    
    Adjusts:
    - Per-share metrics (EPS, Dividend/Share): Divided by cumulative ratio
    - Share counts (Shares Outstanding): Multiplied by cumulative ratio
    """
    adjusted_facts = []
    for f in facts:
        if not f.unit or f.numeric_value is None:
            adjusted_facts.append(f)
            continue

        unit_lower = str(f.unit).lower()
        concept_lower = f.concept.lower()

        # Identify adjustables
        is_per_share = '/share' in unit_lower or 'earningspershare' in concept_lower
        is_shares = 'shares' in unit_lower and not is_per_share

        if not (is_per_share or is_shares):
            adjusted_facts.append(f)
            continue

        # Calculate cumulative ratio
        # Apply all splits that occurred AFTER this fact's period_end
        cum_ratio = 1.0
        for s in splits:
            if s['date'] > f.period_end:
                # Check if finding is NOT restated (filing date < split)
                if not f.filing_date or f.filing_date <= s['date']:
                    cum_ratio *= s['ratio']

        if cum_ratio == 1.0:
            adjusted_facts.append(f)
            continue

        # Guard against invalid split ratios
        if cum_ratio <= 0:
            from edgar.core import log
            log.warning(f"Invalid cumulative split ratio {cum_ratio} for {f.concept}, skipping adjustment")
            adjusted_facts.append(f)
            continue

        # Apply adjustment
        if is_per_share:
            new_val = f.numeric_value / cum_ratio
        else: # is_shares
            new_val = f.numeric_value * cum_ratio

        # Clone and replace
        # Note: We depend on FinancialFact being a dataclass or having replace method
        try:
            new_f = replace(f, 
                            value=new_val, 
                            numeric_value=new_val, 
                            calculation_context=f"split_adj_ratio_{cum_ratio:.2f}")
            adjusted_facts.append(new_f)
        except TypeError:
            # Fallback if replace doesn't work (non-dataclass object)
            adjusted_facts.append(f)

    return adjusted_facts
