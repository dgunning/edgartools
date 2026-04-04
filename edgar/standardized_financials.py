"""
Standardized Financials API

Provides cross-company comparable financial metrics by mapping raw XBRL
to 24 standardized metrics using the 3-layer concept mapping pipeline.

Usage:
    from edgar import Company
    sf = Company("AAPL").get_standardized_financials()
    print(sf.revenue)           # float value
    print(sf['Revenue'])        # StandardizedMetric object
    print(sf.to_dataframe())    # DataFrame with all metrics
"""

import contextlib
import io
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union

from rich.table import Table
from rich.text import Text

from edgar.richtools import repr_rich

log = logging.getLogger(__name__)


# Metric display sections
METRIC_SECTIONS = {
    'Income Statement': [
        'Revenue', 'COGS', 'SGA', 'OperatingIncome', 'PretaxIncome', 'NetIncome'
    ],
    'Cash Flow': [
        'OperatingCashFlow', 'Capex', 'FreeCashFlow',
        'DepreciationAmortization', 'StockBasedCompensation', 'DividendsPaid'
    ],
    'Balance Sheet - Assets': [
        'TotalAssets', 'CashAndEquivalents', 'AccountsReceivable',
        'Inventory', 'Goodwill', 'IntangibleAssets', 'TangibleAssets'
    ],
    'Balance Sheet - Liabilities': [
        'ShortTermDebt', 'LongTermDebt', 'NetDebt', 'AccountsPayable'
    ],
    'Per-Share': [
        'WeightedAverageSharesDiluted'
    ],
}

# All metric names in display order
ALL_METRICS = [m for section in METRIC_SECTIONS.values() for m in section]

# Derived metrics: calculated from other metrics, not extracted directly
DERIVED_METRICS = {
    'FreeCashFlow': ('OperatingCashFlow', 'Capex'),       # OCF - abs(Capex)
    'TangibleAssets': ('TotalAssets', 'IntangibleAssets'),  # TotalAssets - IntangibleAssets
    'NetDebt': ('ShortTermDebt', 'LongTermDebt', 'CashAndEquivalents'),  # STD + LTD - Cash
}

# Metrics that should be negative (outflows) per street sign convention
NEGATE_IF_POSITIVE = {'Capex', 'DividendsPaid'}

# Snake_case property names for each metric
_PROPERTY_NAMES = {
    'Revenue': 'revenue',
    'COGS': 'cogs',
    'SGA': 'sga',
    'OperatingIncome': 'operating_income',
    'PretaxIncome': 'pretax_income',
    'NetIncome': 'net_income',
    'OperatingCashFlow': 'operating_cash_flow',
    'Capex': 'capex',
    'FreeCashFlow': 'free_cash_flow',
    'DepreciationAmortization': 'depreciation_amortization',
    'StockBasedCompensation': 'stock_based_compensation',
    'DividendsPaid': 'dividends_paid',
    'TotalAssets': 'total_assets',
    'CashAndEquivalents': 'cash_and_equivalents',
    'AccountsReceivable': 'accounts_receivable',
    'Inventory': 'inventory',
    'Goodwill': 'goodwill',
    'IntangibleAssets': 'intangible_assets',
    'TangibleAssets': 'tangible_assets',
    'ShortTermDebt': 'short_term_debt',
    'LongTermDebt': 'long_term_debt',
    'NetDebt': 'net_debt',
    'AccountsPayable': 'accounts_payable',
    'WeightedAverageSharesDiluted': 'weighted_average_shares_diluted',
}

# Reverse lookup: snake_case -> metric name
_METRIC_BY_PROPERTY = {v: k for k, v in _PROPERTY_NAMES.items()}


@dataclass
class StandardizedMetric:
    """A single standardized financial metric with provenance."""
    name: str
    value: Optional[float]
    concept: Optional[str]
    confidence: float
    source: str   # 'tree', 'facts', 'ai', 'industry', 'derived', 'excluded'
    notes: Optional[str] = None
    is_excluded: bool = False
    # Data dictionary metadata
    definition: Optional[str] = None
    statement_family: Optional[str] = None
    unit: Optional[str] = None
    sign_convention: Optional[str] = None
    # Provenance and quality indicators
    publish_confidence: Optional[str] = None    # "high" | "medium" | "low" | "unverified"
    evidence_tier: Optional[str] = None         # "sec_confirmed" | "yfinance_confirmed" | "self_validated" | "unverified"
    period_end: Optional[str] = None            # ISO date of the fiscal period end
    accession_number: Optional[str] = None      # SEC filing accession number
    is_golden_master: bool = False
    # Divergence documentation (populated from known_divergences when applicable)
    divergence_notes: Optional[str] = None      # Why this metric may differ from reference sources

    @property
    def has_value(self) -> bool:
        return self.value is not None and not self.is_excluded

    def __repr__(self):
        if self.is_excluded:
            return f"StandardizedMetric({self.name}=excluded)"
        if self.value is None:
            return f"StandardizedMetric({self.name}=None)"
        return f"StandardizedMetric({self.name}={_format_value(self.value)})"


class StandardizedFinancials:
    """
    Cross-company comparable financial metrics from a single filing.

    Provides 24 standardized metrics extracted from XBRL via the
    deterministic concept mapping pipeline (TreeParser + FactsSearcher).

    Access patterns:
        sf['Revenue']           → StandardizedMetric
        sf.revenue              → float (or None)
        sf.income_metrics       → list of StandardizedMetric
        sf.to_dataframe()       → DataFrame
        sf.to_dict()            → dict
    """

    def __init__(
        self,
        metrics: Dict[str, StandardizedMetric],
        company_name: str = "",
        ticker: str = "",
        form_type: str = "",
        fiscal_period: str = "",
    ):
        self._metrics = metrics
        self.company_name = company_name
        self.ticker = ticker
        self.form_type = form_type
        self.fiscal_period = fiscal_period

    # --- Dict-style access ---

    def __getitem__(self, key: str) -> StandardizedMetric:
        if key not in self._metrics:
            raise KeyError(f"Unknown metric: {key}. Available: {list(self._metrics.keys())}")
        return self._metrics[key]

    def __contains__(self, key: str) -> bool:
        return key in self._metrics

    def __iter__(self):
        return iter(self._metrics.values())

    def __len__(self):
        return len(self._metrics)

    # --- Property access (snake_case) ---

    def __getattr__(self, name: str):
        if name.startswith('_') or name in (
            'company_name', 'ticker', 'form_type', 'fiscal_period',
        ):
            raise AttributeError(name)
        metric_name = _METRIC_BY_PROPERTY.get(name)
        if metric_name and metric_name in self._metrics:
            return self._metrics[metric_name].value
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

    # --- Section views ---

    @property
    def income_metrics(self) -> List[StandardizedMetric]:
        return [self._metrics[m] for m in METRIC_SECTIONS['Income Statement'] if m in self._metrics]

    @property
    def cashflow_metrics(self) -> List[StandardizedMetric]:
        return [self._metrics[m] for m in METRIC_SECTIONS['Cash Flow'] if m in self._metrics]

    @property
    def balance_sheet_metrics(self) -> List[StandardizedMetric]:
        assets = [self._metrics[m] for m in METRIC_SECTIONS['Balance Sheet - Assets'] if m in self._metrics]
        liabilities = [self._metrics[m] for m in METRIC_SECTIONS['Balance Sheet - Liabilities'] if m in self._metrics]
        return assets + liabilities

    # --- Stats ---

    @property
    def mapped_count(self) -> int:
        return sum(1 for m in self._metrics.values() if m.has_value)

    @property
    def total_count(self) -> int:
        return sum(1 for m in self._metrics.values() if not m.is_excluded)

    @property
    def coverage_pct(self) -> float:
        total = self.total_count
        if total == 0:
            return 0.0
        return (self.mapped_count / total) * 100.0

    # --- Export ---

    def to_dict(self) -> Dict[str, dict]:
        """Export all metrics as a dict of dicts."""
        return {
            name: {
                'value': m.value,
                'concept': m.concept,
                'confidence': m.confidence,
                'source': m.source,
                'is_excluded': m.is_excluded,
                'notes': m.notes,
                'publish_confidence': m.publish_confidence,
                'evidence_tier': m.evidence_tier,
                'period_end': m.period_end,
                'is_golden_master': m.is_golden_master,
            }
            for name, m in self._metrics.items()
        }

    def to_dataframe(self):
        """Export as a pandas DataFrame with one row per metric, including quality metadata."""
        import pandas as pd
        rows = []
        for name, m in self._metrics.items():
            rows.append({
                'metric': name,
                'value': m.value,
                'formatted': _format_value(m.value) if m.value is not None else ('excluded' if m.is_excluded else '—'),
                'concept': m.concept,
                'confidence': m.confidence,
                'source': m.source,
                'is_excluded': m.is_excluded,
                'publish_confidence': m.publish_confidence,
                'evidence_tier': m.evidence_tier,
                'period_end': m.period_end,
                'is_golden_master': m.is_golden_master,
            })
        return pd.DataFrame(rows)

    # --- Display ---

    def __str__(self):
        return (
            f"StandardizedFinancials({self.company_name} [{self.ticker}] "
            f"{self.form_type} {self.fiscal_period} | "
            f"{self.mapped_count}/{self.total_count} metrics)"
        )

    def __repr__(self):
        return self.__str__()

    def __rich__(self):
        title = f"{self.company_name} [{self.ticker}] — {self.form_type} {self.fiscal_period}"
        subtitle = f"{self.mapped_count}/{self.total_count} metrics mapped ({self.coverage_pct:.0f}%)"

        table = Table(
            title=title,
            caption=subtitle,
            show_header=True,
            header_style="bold",
            padding=(0, 1),
        )
        table.add_column("Metric", style="cyan", min_width=28)
        table.add_column("Value", justify="right", min_width=14)
        table.add_column("Quality", justify="center", min_width=8)
        table.add_column("Source", min_width=8)

        for section_name, metric_names in METRIC_SECTIONS.items():
            # Section header
            table.add_row(
                Text(f"  {section_name}", style="bold underline"),
                "", "", "",
            )
            for name in metric_names:
                m = self._metrics.get(name)
                if m is None:
                    continue
                if m.is_excluded:
                    table.add_row(
                        f"    {name}", Text("excluded", style="dim"), "", ""
                    )
                    continue
                # Value
                if m.value is not None:
                    val_text = _format_value(m.value)
                else:
                    val_text = "—"
                # Quality indicator based on publish_confidence
                pc = m.publish_confidence or "unverified"
                if pc == "high":
                    quality_text = Text("HIGH", style="bold green")
                elif pc == "medium":
                    quality_text = Text("MED", style="yellow")
                elif pc == "low":
                    quality_text = Text("LOW", style="red")
                else:
                    quality_text = Text("—", style="dim")
                if m.value is None:
                    quality_text = Text("")

                table.add_row(
                    f"    {name}",
                    val_text,
                    quality_text,
                    m.source if m.value is not None else "",
                )

        return table

    def _repr_html_(self):
        return repr_rich(self.__rich__())


# ---------------------------------------------------------------------------
# Value formatting
# ---------------------------------------------------------------------------

def _format_value(value: Optional[float]) -> str:
    """Format a numeric value with B/M/K suffixes."""
    if value is None:
        return "—"
    abs_val = abs(value)
    sign = "-" if value < 0 else ""
    if abs_val >= 1e9:
        return f"{sign}{abs_val / 1e9:,.1f}B"
    if abs_val >= 1e6:
        return f"{sign}{abs_val / 1e6:,.1f}M"
    if abs_val >= 1e3:
        return f"{sign}{abs_val / 1e3:,.1f}K"
    return f"{sign}{abs_val:,.0f}"


# ---------------------------------------------------------------------------
# Pipeline: extract_standardized_financials
# ---------------------------------------------------------------------------

def extract_standardized_financials(filing, ticker: str) -> Optional['StandardizedFinancials']:
    """
    Extract standardized financials from a filing using the deterministic pipeline.

    Steps:
        1. Parse XBRL
        2. Layer 1: TreeParser concept mapping
        3. Layer 2: FactsSearcher gap filling
        4. Value extraction via ReferenceValidator helpers
        5. Sign conventions & derived metrics
        6. Wrap in StandardizedFinancials

    Args:
        filing: A Filing object (10-K or 10-Q)
        ticker: Company ticker symbol

    Returns:
        StandardizedFinancials or None if XBRL is unavailable
    """
    from edgar.xbrl.standardization.config_loader import get_config
    from edgar.xbrl.standardization.layers.tree_parser import TreeParser
    from edgar.xbrl.standardization.layers.facts_search import FactsSearcher
    from edgar.xbrl.standardization.reference_validator import ReferenceValidator
    from edgar.xbrl.standardization.models import MappingResult, MappingSource

    # 1. Parse XBRL
    xbrl = filing.xbrl()
    if xbrl is None:
        log.warning("No XBRL data available for %s", ticker)
        return None

    config = get_config()
    form_type = getattr(filing, 'form', '10-K')

    # Determine fiscal period from filing
    period_of_report = getattr(filing, 'period_of_report', None)
    if period_of_report:
        fiscal_period = period_of_report
    else:
        fiscal_period = "unknown"

    # Determine company name
    company_name = getattr(xbrl, 'entity_name', '') or ticker

    # 2. Layer 1: TreeParser — suppress debug prints
    tree_parser = TreeParser(config)
    with contextlib.redirect_stdout(io.StringIO()):
        tree_results = tree_parser.map_company(ticker, filing)

    # 3. Layer 2: FactsSearcher — suppress debug prints
    facts_searcher = FactsSearcher(config)
    with contextlib.redirect_stdout(io.StringIO()):
        combined_results = facts_searcher.search_gaps(tree_results, ticker, fiscal_period)

    # 4. Value extraction using ReferenceValidator helpers
    validator = ReferenceValidator(config, snapshot_mode=True)
    validator._current_ticker = ticker
    validator._current_form_type = form_type

    # Get company config and excluded metrics
    company_config = config.get_company(ticker)
    excluded_metrics = config.get_excluded_metrics_for_company(ticker)

    # Build metrics dict
    metrics: Dict[str, StandardizedMetric] = {}

    # Extract directly-mapped metrics (not derived, not excluded)
    for metric_name in ALL_METRICS:
        if metric_name in DERIVED_METRICS:
            continue  # Handle after direct extraction

        if metric_name in excluded_metrics:
            metrics[metric_name] = StandardizedMetric(
                name=metric_name,
                value=None,
                concept=None,
                confidence=0.0,
                source='excluded',
                is_excluded=True,
                notes=f"Excluded for {ticker}",
            )
            continue

        result = combined_results.get(metric_name)
        value = None
        concept = None
        confidence = 0.0
        source = 'unmapped'

        # Check if metric config says it's composite
        metric_config = config.get_metric(metric_name)
        is_composite = metric_config and metric_config.is_composite

        if is_composite:
            # Composite metrics: use _extract_composite_value
            value = validator._extract_composite_value(xbrl, metric_name)
            if value is not None:
                concept = f"Composite({metric_name})"
                confidence = 0.85
                source = 'tree'
        elif result and result.is_mapped and result.concept:
            # Standard metric with a mapped concept
            concept = result.concept
            confidence = result.confidence
            source = result.source.value if hasattr(result.source, 'value') else str(result.source)
            value = validator._extract_xbrl_value(xbrl, concept)

        # Try industry extraction if no value yet
        if value is None and not is_composite:
            industry_value = validator._try_industry_extraction(ticker, metric_name, xbrl)
            if industry_value is not None:
                value = industry_value
                source = 'industry'
                confidence = max(confidence, 0.80)
                if concept is None:
                    concept = f"Industry({metric_name})"

        # Apply sign convention: Capex and DividendsPaid should be negative
        if value is not None and metric_name in NEGATE_IF_POSITIVE and value > 0:
            value = -value

        metrics[metric_name] = StandardizedMetric(
            name=metric_name,
            value=value,
            concept=concept,
            confidence=confidence,
            source=source,
        )

    # 5. Calculate derived metrics
    _calculate_derived_metrics(metrics)

    # 6. Enrich with data dictionary (cached, no network calls)
    try:
        from edgar.xbrl.standardization.config_loader import load_data_dictionary
        data_dict = load_data_dictionary()
        for metric_name, m in metrics.items():
            dd_entry = data_dict.get(metric_name)
            if dd_entry:
                m.definition = dd_entry.description
                m.statement_family = dd_entry.statement_family
                m.unit = dd_entry.unit
                m.sign_convention = dd_entry.sign_convention
    except Exception as e:
        log.warning(f"Data dictionary enrichment failed: {e}")

    # 6b. Populate divergence_notes from known_divergences
    if company_config and company_config.known_divergences:
        for metric_name, m in metrics.items():
            div = company_config.known_divergences.get(metric_name)
            if div:
                m.divergence_notes = div.get("reason")

    # 7. Wrap in StandardizedFinancials
    return StandardizedFinancials(
        metrics=metrics,
        company_name=company_name,
        ticker=ticker,
        form_type=form_type,
        fiscal_period=fiscal_period,
    )


def _calculate_derived_metrics(metrics: Dict[str, StandardizedMetric]):
    """Calculate FreeCashFlow, TangibleAssets, and NetDebt from their components."""

    def _get_val(name: str) -> Optional[float]:
        m = metrics.get(name)
        if m and m.has_value:
            return m.value
        return None

    # FreeCashFlow = OperatingCashFlow - abs(Capex)
    ocf = _get_val('OperatingCashFlow')
    capex = _get_val('Capex')
    if ocf is not None and capex is not None:
        fcf = ocf - abs(capex)
        metrics['FreeCashFlow'] = StandardizedMetric(
            name='FreeCashFlow', value=fcf,
            concept='Derived(OperatingCashFlow - |Capex|)',
            confidence=min(metrics['OperatingCashFlow'].confidence, metrics['Capex'].confidence),
            source='derived',
        )
    else:
        metrics.setdefault('FreeCashFlow', StandardizedMetric(
            name='FreeCashFlow', value=None, concept=None,
            confidence=0.0, source='derived',
            notes='Missing OperatingCashFlow or Capex',
        ))

    # TangibleAssets = TotalAssets - IntangibleAssets
    total_assets = _get_val('TotalAssets')
    intangibles = _get_val('IntangibleAssets')
    if total_assets is not None and intangibles is not None:
        tangible = total_assets - intangibles
        metrics['TangibleAssets'] = StandardizedMetric(
            name='TangibleAssets', value=tangible,
            concept='Derived(TotalAssets - IntangibleAssets)',
            confidence=min(metrics['TotalAssets'].confidence, metrics['IntangibleAssets'].confidence),
            source='derived',
        )
    else:
        metrics.setdefault('TangibleAssets', StandardizedMetric(
            name='TangibleAssets', value=None, concept=None,
            confidence=0.0, source='derived',
            notes='Missing TotalAssets or IntangibleAssets',
        ))

    # NetDebt = ShortTermDebt + LongTermDebt - CashAndEquivalents
    std = _get_val('ShortTermDebt')
    ltd = _get_val('LongTermDebt')
    cash = _get_val('CashAndEquivalents')
    if ltd is not None and cash is not None:
        # ShortTermDebt can be None (some companies don't have it)
        short = std if std is not None else 0.0
        net_debt = short + ltd - cash
        components = [metrics.get('LongTermDebt'), metrics.get('CashAndEquivalents')]
        if metrics.get('ShortTermDebt') and metrics['ShortTermDebt'].has_value:
            components.append(metrics['ShortTermDebt'])
        min_conf = min(c.confidence for c in components if c)
        metrics['NetDebt'] = StandardizedMetric(
            name='NetDebt', value=net_debt,
            concept='Derived(ShortTermDebt + LongTermDebt - Cash)',
            confidence=min_conf,
            source='derived',
        )
    else:
        metrics.setdefault('NetDebt', StandardizedMetric(
            name='NetDebt', value=None, concept=None,
            confidence=0.0, source='derived',
            notes='Missing LongTermDebt or CashAndEquivalents',
        ))
