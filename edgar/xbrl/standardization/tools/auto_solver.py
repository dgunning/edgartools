"""
Auto-Solver: Discovers yfinance's composite formulas by searching XBRL facts.

When Standardization Alignment (SA) shows a gap between our raw XBRL extraction
and yfinance's aggregated number, the Auto-Solver performs a bounded combinatorial
search to discover which combination of XBRL facts sums to yfinance's value.

This is the key tool for reverse-engineering yfinance's standardization methodology.

Usage:
    from edgar.xbrl.standardization.tools.auto_solver import AutoSolver

    solver = AutoSolver()
    candidates = solver.solve_metric("ABBV", "DepreciationAmortization")
    for c in candidates:
        print(c)

    # Cross-company validation
    results = solver.validate_formula(candidates[0], ["SLB", "GE", "HD", "PEP"])
"""

import logging
from dataclasses import dataclass, field
from itertools import combinations
from typing import Dict, List, Optional, Tuple

from edgar import Company

logger = logging.getLogger(__name__)


@dataclass
class FormulaCandidate:
    """A candidate composite formula that explains a yfinance value."""
    metric: str                     # Target metric name
    ticker: str                     # Company where discovered
    components: List[str]           # XBRL concept names
    values: List[float]             # Corresponding values
    total: float                    # Sum of component values
    target: float                   # yfinance value
    variance_pct: float             # How close (0 = exact match)
    statement_family: str = ""      # Which statement the components come from
    periods_checked: int = 0        # Multi-period: how many periods had all components
    periods_passed: int = 0         # Multi-period: how many periods matched target

    def __repr__(self):
        parts = " + ".join(
            f"{c}(${v/1e9:.2f}B)" for c, v in zip(self.components, self.values)
        )
        return (
            f"FormulaCandidate({self.metric} @ {self.ticker}: "
            f"{parts} = ${self.total/1e9:.2f}B "
            f"vs target ${self.target/1e9:.2f}B [{self.variance_pct:.1f}%])"
        )


@dataclass
class FormulaValidation:
    """Result of validating a formula across multiple companies."""
    formula_components: List[str]
    results: Dict[str, dict] = field(default_factory=dict)
    # Per-ticker: {ticker: {total, target, variance_pct, status}}

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.results.values() if r.get("status") == "pass")

    @property
    def total_count(self) -> int:
        return len(self.results)

    @property
    def is_sector_pattern(self) -> bool:
        """A formula is a sector pattern if it works for >=2 companies at <=5%."""
        return self.pass_count >= 2

    def summary(self) -> str:
        lines = [f"Formula: {' + '.join(self.formula_components)}"]
        lines.append(f"Pass: {self.pass_count}/{self.total_count}")
        for ticker, r in sorted(self.results.items()):
            status = r.get("status", "?")
            var = r.get("variance_pct")
            var_str = f"{var:.1f}%" if var is not None else "N/A"
            lines.append(f"  {ticker}: {status} (variance: {var_str})")
        return "\n".join(lines)


class AutoSolver:
    """
    Discovers yfinance's composite formulas via bounded subset-sum search.

    For a given metric gap, extracts all numeric XBRL facts from the relevant
    statement, then searches for combinations of 1-4 facts that sum to the
    yfinance target value within 1% tolerance.
    """

    # Map auto-solver family codes to DataFrame statement_type values
    FAMILY_TO_STATEMENT_TYPES = {
        "INCOME": ["IncomeStatement"],
        "OPERATIONS": ["IncomeStatement"],
        "BALANCE": ["BalanceSheet"],
        "FINANCIAL_POSITION": ["BalanceSheet"],
        "CASHFLOW": ["CashFlowStatement"],
    }

    # Statement family mapping: which statements to search for each metric
    METRIC_STATEMENT_FAMILIES = {
        "DepreciationAmortization": ["CASHFLOW"],
        "StockBasedCompensation": ["CASHFLOW"],
        "Capex": ["CASHFLOW"],
        "OperatingCashFlow": ["CASHFLOW"],
        "DividendsPaid": ["CASHFLOW"],
        "Revenue": ["INCOME", "OPERATIONS"],
        "COGS": ["INCOME", "OPERATIONS"],
        "SGA": ["INCOME", "OPERATIONS"],
        "OperatingIncome": ["INCOME", "OPERATIONS"],
        "PretaxIncome": ["INCOME", "OPERATIONS"],
        "NetIncome": ["INCOME", "OPERATIONS"],
        "WeightedAverageSharesDiluted": ["INCOME"],
        "TotalAssets": ["BALANCE", "FINANCIAL_POSITION"],
        "Goodwill": ["BALANCE", "FINANCIAL_POSITION"],
        "IntangibleAssets": ["BALANCE", "FINANCIAL_POSITION"],
        "ShortTermDebt": ["BALANCE", "FINANCIAL_POSITION"],
        "LongTermDebt": ["BALANCE", "FINANCIAL_POSITION"],
        "CashAndEquivalents": ["BALANCE", "FINANCIAL_POSITION"],
        "Inventory": ["BALANCE", "FINANCIAL_POSITION"],
        "AccountsReceivable": ["BALANCE", "FINANCIAL_POSITION"],
        "AccountsPayable": ["BALANCE", "FINANCIAL_POSITION"],
    }

    def __init__(
        self,
        max_components: int = 4,
        search_tolerance_pct: float = 1.0,
        snapshot_mode: bool = True,
        allow_subtraction: bool = False,
        allow_scale_search: bool = False,
    ):
        self.max_components = max_components
        self.search_tolerance = search_tolerance_pct / 100.0
        self.snapshot_mode = snapshot_mode
        self.allow_subtraction = allow_subtraction
        self.allow_scale_search = allow_scale_search

    def solve_metric(
        self,
        ticker: str,
        metric: str,
        yfinance_value: Optional[float] = None,
        xbrl_facts: Optional[Dict[str, float]] = None,
        multi_period: bool = False,
        num_periods: int = 3,
    ) -> List[FormulaCandidate]:
        """
        Discover which combination of XBRL facts sums to yfinance's value.

        Args:
            ticker: Company ticker (e.g., "ABBV")
            metric: Metric name (e.g., "DepreciationAmortization")
            yfinance_value: Target yfinance value. If None, fetched from snapshot.
            xbrl_facts: Dict of {concept_name: value}. If None, extracted from filing.
            multi_period: If True, validate candidates inline across multiple periods.
            num_periods: Number of annual filings to check (default 3).

        Returns:
            List of FormulaCandidate, ranked by: fewest components, lowest variance.
        """
        # Get yfinance target
        if yfinance_value is None:
            yfinance_value = self._get_yfinance_target(ticker, metric)
            if yfinance_value is None:
                logger.warning(f"No yfinance value for {ticker}:{metric}")
                return []

        # Get XBRL facts — optionally load multiple periods upfront
        other_period_facts: List[Dict[str, float]] = []

        if xbrl_facts is None:
            if multi_period:
                all_period_facts = self._extract_multi_period_facts(
                    ticker, metric, num_periods=num_periods
                )
                if not all_period_facts:
                    logger.warning(f"No XBRL facts for {ticker}:{metric}")
                    return []
                xbrl_facts = all_period_facts[0]  # Primary = latest filing
                other_period_facts = all_period_facts[1:]
            else:
                xbrl_facts = self._extract_xbrl_facts(ticker, metric)

            if not xbrl_facts:
                logger.warning(f"No XBRL facts for {ticker}:{metric}")
                return []

        target = abs(yfinance_value)
        logger.info(
            f"Solving {ticker}:{metric} — target=${target/1e9:.2f}B, "
            f"{len(xbrl_facts)} candidate facts"
            + (f", {len(other_period_facts)} additional periods" if multi_period else "")
        )

        # Filter to positive-valued facts within plausible range
        candidates = {}
        for concept, value in xbrl_facts.items():
            abs_val = abs(value)
            # Skip zero values and values larger than 2x target
            if abs_val > 0 and abs_val <= target * 2:
                candidates[concept] = abs_val

        if not candidates:
            logger.warning(f"No plausible candidate facts for {ticker}:{metric}")
            return []

        # Cap candidates to avoid combinatorial explosion.
        # Sort by closeness to target, keep top N. C(50,4) ≈ 230K — tractable.
        MAX_CANDIDATES = 50
        if len(candidates) > MAX_CANDIDATES:
            sorted_by_relevance = sorted(
                candidates.items(),
                key=lambda kv: abs(kv[1] - target),
            )
            candidates = dict(sorted_by_relevance[:MAX_CANDIDATES])
            logger.info(f"Pruned to {MAX_CANDIDATES} most relevant candidates (from {len(xbrl_facts)})")

        # Bounded subset-sum search: 1 to max_components terms
        results: List[FormulaCandidate] = []
        concept_list = list(candidates.keys())
        value_list = [candidates[c] for c in concept_list]

        for size in range(1, min(self.max_components + 1, len(concept_list) + 1)):
            for combo_indices in combinations(range(len(concept_list)), size):
                combo_sum = sum(value_list[i] for i in combo_indices)
                variance = abs(combo_sum - target) / target if target != 0 else 0

                if variance <= self.search_tolerance:
                    combo_concepts = [concept_list[i] for i in combo_indices]
                    combo_values = [value_list[i] for i in combo_indices]

                    # Phase B: Inline multi-period constraint
                    periods_checked = 1  # Primary period always counts
                    periods_passed = 1   # Primary matched (within tolerance)

                    if multi_period and other_period_facts:
                        mp_checked, mp_passed = self._check_multi_period(
                            combo_concepts, target, other_period_facts,
                        )
                        periods_checked += mp_checked
                        periods_passed += mp_passed

                        # Require at least min(2, periods_checked) to pass
                        min_required = min(2, periods_checked)
                        if periods_passed < min_required:
                            continue  # Reject: doesn't hold across periods

                    results.append(FormulaCandidate(
                        metric=metric,
                        ticker=ticker,
                        components=combo_concepts,
                        values=combo_values,
                        total=combo_sum,
                        target=target,
                        variance_pct=variance * 100,
                        statement_family=self._get_statement_family(metric),
                        periods_checked=periods_checked,
                        periods_passed=periods_passed,
                    ))

        # Phase C: Subtraction search (A - B, A + B - C, etc.)
        if self.allow_subtraction and len(concept_list) >= 2:
            for size in range(2, min(self.max_components + 1, len(concept_list) + 1)):
                for combo_indices in combinations(range(len(concept_list)), size):
                    combo_concepts = [concept_list[i] for i in combo_indices]
                    combo_values = [value_list[i] for i in combo_indices]

                    # Try subtracting each single element from the sum of the rest
                    for neg_idx in range(len(combo_values)):
                        signed_values = list(combo_values)
                        signed_values[neg_idx] = -signed_values[neg_idx]
                        combo_sum = sum(signed_values)

                        if target != 0:
                            variance = abs(combo_sum - target) / target
                        else:
                            variance = 0

                        if variance <= self.search_tolerance:
                            results.append(FormulaCandidate(
                                metric=metric,
                                ticker=ticker,
                                components=combo_concepts,
                                values=signed_values,
                                total=combo_sum,
                                target=target,
                                variance_pct=variance * 100,
                                statement_family=self._get_statement_family(metric),
                            ))

        # Phase D: Scale normalization search
        if self.allow_scale_search:
            scale_factors = [1000, 1_000_000, 0.001, 0.000001]
            for concept, value in candidates.items():
                for scale in scale_factors:
                    scaled = value * scale
                    if target != 0:
                        variance = abs(scaled - target) / target
                    else:
                        variance = 0
                    if variance <= self.search_tolerance:
                        results.append(FormulaCandidate(
                            metric=metric,
                            ticker=ticker,
                            components=[concept],
                            values=[scaled],
                            total=scaled,
                            target=target,
                            variance_pct=variance * 100,
                            statement_family=self._get_statement_family(metric),
                        ))

        # Sort: fewest components first, then lowest variance
        results.sort(key=lambda f: (len(f.components), f.variance_pct))

        logger.info(f"Found {len(results)} formula candidates for {ticker}:{metric}")
        return results

    def solve_composite_metric(
        self,
        ticker: str,
        metric: str,
        found_components: List[str],
        found_total: float,
        target: float,
    ) -> List[FormulaCandidate]:
        """
        Solve for missing components in a composite metric.

        Instead of searching for facts that sum to `target`, finds facts
        that fill the gap: target - found_total (the residual).

        Args:
            ticker: Company ticker.
            metric: Metric name (e.g., "IntangibleAssets").
            found_components: Components already successfully extracted.
            found_total: Sum of already-found component values.
            target: The full yfinance target value.

        Returns:
            List of FormulaCandidate representing the residual match.
        """
        residual = abs(target) - abs(found_total)
        if residual <= 0:
            logger.info(
                f"Composite solver: {ticker}:{metric} found_total={found_total} "
                f">= target={target}, no residual to solve"
            )
            return []

        logger.info(
            f"Composite solver: {ticker}:{metric} searching for residual "
            f"${residual/1e9:.2f}B (target=${target/1e9:.2f}B - found=${found_total/1e9:.2f}B, "
            f"found_components={found_components})"
        )

        # Use solve_metric with the residual as the target
        candidates = self.solve_metric(
            ticker, metric,
            yfinance_value=residual,
            multi_period=False,  # Component search is less strict
        )

        # Filter out candidates that include already-found components
        filtered = []
        found_set = set(found_components)
        for candidate in candidates:
            overlap = found_set.intersection(set(candidate.components))
            if not overlap:
                # Update candidate to reflect it's solving the residual
                candidate.target = target  # Full target for context
                filtered.append(candidate)

        if filtered:
            logger.info(
                f"Composite solver found {len(filtered)} residual candidates "
                f"for {ticker}:{metric}"
            )
        else:
            logger.info(
                f"Composite solver: all {len(candidates)} candidates overlap "
                f"with found components {found_components}"
            )

        return filtered

    def validate_formula(
        self,
        formula: FormulaCandidate,
        tickers: List[str],
        tolerance_pct: float = 5.0,
    ) -> FormulaValidation:
        """
        Validate a discovered formula across multiple companies.

        Args:
            formula: The FormulaCandidate to validate.
            tickers: List of tickers to test against.
            tolerance_pct: Pass threshold (default 5%).

        Returns:
            FormulaValidation with per-company results.
        """
        tolerance = tolerance_pct / 100.0
        validation = FormulaValidation(formula_components=formula.components)

        for ticker in tickers:
            yf_value = self._get_yfinance_target(ticker, formula.metric)
            if yf_value is None:
                validation.results[ticker] = {
                    "total": None, "target": None,
                    "variance_pct": None, "status": "no_reference",
                }
                continue

            facts = self._extract_xbrl_facts(ticker, formula.metric)
            if not facts:
                validation.results[ticker] = {
                    "total": None, "target": abs(yf_value),
                    "variance_pct": None, "status": "no_xbrl",
                }
                continue

            # Sum the formula components
            total = 0.0
            missing = []
            for component in formula.components:
                if component in facts:
                    total += abs(facts[component])
                else:
                    missing.append(component)

            if missing:
                validation.results[ticker] = {
                    "total": total, "target": abs(yf_value),
                    "variance_pct": None, "status": f"missing:{','.join(missing)}",
                    "missing_components": missing,
                }
                continue

            target = abs(yf_value)
            variance = abs(total - target) / target if target != 0 else 0

            validation.results[ticker] = {
                "total": total,
                "target": target,
                "variance_pct": variance * 100,
                "status": "pass" if variance <= tolerance else "fail",
            }

        return validation

    def validate_formula_multi_period(
        self,
        formula: FormulaCandidate,
        ticker: str,
        num_periods: int = 3,
        tolerance_pct: float = 5.0,
    ) -> Dict[str, dict]:
        """
        Validate a formula across multiple fiscal periods for the same company.

        Checks the last `num_periods` 10-K filings to ensure the formula
        isn't a coincidental single-period match.

        Args:
            formula: The FormulaCandidate to validate.
            ticker: Company ticker.
            num_periods: Number of annual filings to check (default 3).
            tolerance_pct: Pass threshold (default 5%).

        Returns:
            Dict with 'periods_checked', 'periods_passed', 'results' (per-period).
        """
        tolerance = tolerance_pct / 100.0
        results = {
            "periods_checked": 0,
            "periods_passed": 0,
            "results": [],
        }

        try:
            company = Company(ticker)
            filings = list(company.get_filings(form="10-K"))[:num_periods]
        except Exception as e:
            logger.warning(f"Multi-period validation failed for {ticker}: {e}")
            return results

        # Hoist reference lookup — same value for all periods
        ref_value = self._get_yfinance_target(ticker, formula.metric)
        if ref_value is None:
            return results
        target = abs(ref_value)

        for filing in filings:
            try:
                xbrl = filing.xbrl()
                fact_values = self._parse_facts_from_xbrl(
                    xbrl, period_filter="annual",
                )
                if not fact_values:
                    continue

                # Sum formula components
                total = 0.0
                missing = []
                for component in formula.components:
                    if component in fact_values:
                        total += abs(fact_values[component])
                    else:
                        missing.append(component)

                if missing:
                    results["results"].append({
                        "filing": str(filing.accession_no),
                        "status": f"missing:{','.join(missing)}",
                    })
                    continue
                variance = abs(total - target) / target if target != 0 else 0
                passed = variance <= tolerance

                results["periods_checked"] += 1
                if passed:
                    results["periods_passed"] += 1

                results["results"].append({
                    "filing": str(filing.accession_no),
                    "total": total,
                    "target": target,
                    "variance_pct": variance * 100,
                    "status": "pass" if passed else "fail",
                })

            except Exception as e:
                logger.debug(f"Multi-period check failed for {filing}: {e}")
                continue

        return results

    def solve_all_gaps(
        self,
        gaps: List[dict],
    ) -> Dict[str, List[FormulaCandidate]]:
        """
        Run the solver on a list of gaps from auto-eval.

        Args:
            gaps: List of dicts with 'ticker', 'metric', optionally 'reference_value'.

        Returns:
            Dict mapping "ticker:metric" to discovered formulas.
        """
        results = {}
        for gap in gaps:
            ticker = gap.get("ticker", "")
            metric = gap.get("metric", "")
            ref_value = gap.get("reference_value")
            key = f"{ticker}:{metric}"

            candidates = self.solve_metric(ticker, metric, yfinance_value=ref_value)
            if candidates:
                results[key] = candidates
                logger.info(f"  {key}: {len(candidates)} formulas found")
            else:
                logger.info(f"  {key}: no formulas found")

        return results

    # =========================================================================
    # Internal helpers
    # =========================================================================

    @staticmethod
    def _parse_facts_from_xbrl(
        xbrl,
        period_filter: str = "annual",
        statement_families: Optional[List[str]] = None,
    ) -> Dict[str, float]:
        """
        Extract numeric facts from an XBRL object, filtered by period and statement.

        Args:
            xbrl: Loaded XBRL object.
            period_filter: "annual" (>300 day duration, latest instant),
                           "quarterly" (60-100 day duration), or "all".
            statement_families: Optional list of family codes (e.g., ["INCOME"])
                                to restrict which statements are searched.

        Returns:
            Dict of {concept_name: value} with namespace prefixes stripped.
            Only the first value per concept is kept.
        """
        if xbrl is None or xbrl.facts is None:
            return {}

        facts_df = xbrl.facts.to_dataframe()
        if facts_df is None or facts_df.empty:
            return {}

        # Phase C: Statement-family pre-filtering
        if statement_families:
            target_types = set()
            for family in statement_families:
                target_types.update(
                    AutoSolver.FAMILY_TO_STATEMENT_TYPES.get(family, [])
                )
            if target_types and "statement_type" in facts_df.columns:
                stmt_filtered = facts_df[facts_df["statement_type"].isin(target_types)]
                # Fallback: if too few facts after filtering, use all statements
                if len(stmt_filtered) >= 5:
                    facts_df = stmt_filtered

        # Phase A: Period-aware filtering
        if period_filter != "all":
            facts_df = AutoSolver._filter_by_period(facts_df, period_filter)

        # Build {concept: value} dict
        result = {}
        for _, row in facts_df.iterrows():
            concept = row.get("concept", "")
            # Prefer numeric_value (Decimal) over string value
            value = row.get("numeric_value")
            if value is None:
                value = row.get("value")
            if value is None:
                continue
            try:
                value = float(value)
            except (ValueError, TypeError):
                continue
            if value == 0:
                continue
            # Strip namespace prefixes
            clean = concept
            for prefix in ["us-gaap:", "us-gaap_", "ifrs-full:", "dei:", "srt:"]:
                clean = clean.replace(prefix, "")
            if clean not in result:
                result[clean] = value
        return result

    @staticmethod
    def _filter_by_period(facts_df, period_filter: str):
        """
        Filter a facts DataFrame to rows matching the requested period type.

        For "annual": duration facts with >300 days, instant facts at latest date.
        For "quarterly": duration facts with 60-100 days, instant facts at latest date.
        """
        import pandas as pd

        has_period_type = "period_type" in facts_df.columns
        if not has_period_type:
            return facts_df

        duration_mask = facts_df["period_type"] == "duration"
        instant_mask = facts_df["period_type"] == "instant"
        filtered_parts = []

        # --- Duration facts (Revenue, NetIncome, CashFlow items) ---
        duration_df = facts_df[duration_mask]
        if (
            not duration_df.empty
            and "period_start" in duration_df.columns
            and "period_end" in duration_df.columns
        ):
            start = pd.to_datetime(duration_df["period_start"], errors="coerce")
            end = pd.to_datetime(duration_df["period_end"], errors="coerce")
            days = (end - start).dt.days

            if period_filter == "annual":
                duration_df = duration_df[days > 300]
            elif period_filter == "quarterly":
                duration_df = duration_df[(days >= 60) & (days <= 100)]

            filtered_parts.append(duration_df)

        # --- Instant facts (TotalAssets, Cash, balance sheet items) ---
        instant_df = facts_df[instant_mask]
        if not instant_df.empty and "period_instant" in instant_df.columns:
            # Keep only the latest instant date (fiscal year end for 10-K)
            dates = pd.to_datetime(instant_df["period_instant"], errors="coerce")
            latest = dates.max()
            if pd.notna(latest):
                instant_df = instant_df[dates == latest]
            filtered_parts.append(instant_df)

        if filtered_parts:
            return pd.concat(filtered_parts, ignore_index=True)
        return facts_df  # Fallback: return unfiltered if nothing matched

    def _get_yfinance_target(self, ticker: str, metric: str) -> Optional[float]:
        """Get yfinance reference value from snapshot or live API."""
        from edgar.xbrl.standardization.reference_validator import ReferenceValidator

        validator = ReferenceValidator(snapshot_mode=self.snapshot_mode)
        # Use the validator's internal mechanism to get the yfinance value
        if self.snapshot_mode:
            validator._current_ticker = ticker
            value = validator._get_yfinance_value(None, metric)
        else:
            stock = validator._get_stock(ticker)
            value = validator._get_yfinance_value(stock, metric)

        return value

    def _extract_xbrl_facts(
        self, ticker: str, metric: str
    ) -> Dict[str, float]:
        """
        Extract numeric XBRL facts from the latest 10-K filing.

        Uses period-aware filtering (annual) and statement-family pre-filtering
        when a family mapping exists for the metric.
        """
        statement_families = self.METRIC_STATEMENT_FAMILIES.get(metric)
        try:
            company = Company(ticker)
            filings = company.get_filings(form="10-K")
            if not filings or len(filings) == 0:
                return {}

            filing = filings[0]
            xbrl = filing.xbrl()
            return self._parse_facts_from_xbrl(
                xbrl,
                period_filter="annual",
                statement_families=statement_families,
            )

        except Exception as e:
            logger.warning(f"Failed to extract XBRL facts for {ticker}: {e}")
            return {}

    def _extract_multi_period_facts(
        self, ticker: str, metric: str, num_periods: int = 3
    ) -> List[Dict[str, float]]:
        """
        Extract period-aware facts from the last N 10-K filings.

        Returns a list of fact dicts, one per filing, ordered newest-first.
        Used by solve_metric(multi_period=True) to validate candidates inline.
        """
        statement_families = self.METRIC_STATEMENT_FAMILIES.get(metric)
        try:
            company = Company(ticker)
            filings = list(company.get_filings(form="10-K"))[:num_periods]
        except Exception as e:
            logger.warning(f"Failed to load filings for {ticker}: {e}")
            return []

        all_facts: List[Dict[str, float]] = []
        for filing in filings:
            try:
                xbrl = filing.xbrl()
                facts = self._parse_facts_from_xbrl(
                    xbrl,
                    period_filter="annual",
                    statement_families=statement_families,
                )
                if facts:
                    all_facts.append(facts)
            except Exception as e:
                logger.debug(f"Failed to extract facts from {filing}: {e}")
                continue

        return all_facts

    def _check_multi_period(
        self,
        combo_concepts: List[str],
        target: float,
        other_period_facts: List[Dict[str, float]],
        tolerance: float = 0.05,
    ) -> Tuple[int, int]:
        """
        Check if a formula holds across additional periods.

        Soft constraint: periods where a component is MISSING are skipped
        (not counted as failure). Only periods with all components present
        are checked against the target.

        Returns:
            (periods_checked, periods_passed) — excludes primary period.
        """
        checked = 0
        passed = 0

        for facts in other_period_facts:
            # Check that all components are present
            total = 0.0
            all_present = True
            for concept in combo_concepts:
                if concept in facts:
                    total += abs(facts[concept])
                else:
                    all_present = False
                    break

            if not all_present:
                # Soft constraint: missing concept → skip, don't penalize
                continue

            checked += 1
            variance = abs(total - target) / target if target != 0 else 0
            if variance <= tolerance:
                passed += 1

        return checked, passed

    def _get_statement_family(self, metric: str) -> str:
        """Get the statement family label for a metric."""
        families = self.METRIC_STATEMENT_FAMILIES.get(metric, [])
        return families[0] if families else "UNKNOWN"


# =============================================================================
# CLI / Interactive Usage
# =============================================================================

def print_solve_results(candidates: List[FormulaCandidate], limit: int = 10):
    """Pretty-print solver results."""
    print()
    print("=" * 70)
    print(f"AUTO-SOLVER RESULTS — {candidates[0].metric} @ {candidates[0].ticker}" if candidates else "NO RESULTS")
    print("=" * 70)

    if not candidates:
        print("  No formula candidates found.")
        return

    print(f"  Target: ${candidates[0].target/1e9:.3f}B")
    print(f"  Candidates: {len(candidates)}")
    print()

    for i, c in enumerate(candidates[:limit], 1):
        parts = " + ".join(
            f"{name} (${val/1e9:.3f}B)" for name, val in zip(c.components, c.values)
        )
        print(f"  #{i} [{len(c.components)} terms, {c.variance_pct:.2f}%] {parts}")
        print(f"      = ${c.total/1e9:.3f}B")

    print("=" * 70)
    print()


def print_validation_results(validation: FormulaValidation):
    """Pretty-print cross-company validation."""
    print()
    print("=" * 70)
    print("CROSS-COMPANY VALIDATION")
    print("=" * 70)
    print(validation.summary())
    if validation.is_sector_pattern:
        print("\n  >> SECTOR PATTERN DETECTED — formula works across multiple companies")
    print("=" * 70)
    print()
