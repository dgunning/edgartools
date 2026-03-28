"""
Auto-Eval: Autonomous quality measurement for the XBRL standardization pipeline.

Applies the autoresearch pattern — a single composite quality score (CQS) serves
as "val_bpb". The agent modifies only YAML configs ("weights"); the eval harness
(Orchestrator + ReferenceValidator + yf_snapshots) is fixed.

Key design:
- CQS is a weighted composite of pass_rate, variance, coverage, golden masters
- Regressions are a HARD VETO — any regression caps CQS below baseline
- Per-company breakdown enables drill-down diagnostics
- Gap analysis ranks opportunities by estimated CQS impact
"""

import logging
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

from edgar.xbrl.standardization.models import MappingResult, MappingSource

logger = logging.getLogger(__name__)


# =============================================================================
# COHORT DEFINITIONS
# =============================================================================

# 5-company quick-eval cohort: diverse archetypes for fast feedback
QUICK_EVAL_COHORT = ["AAPL", "JPM", "XOM", "WMT", "JNJ"]

# Default parallelism for compute_cqs / identify_gaps.
# Set to >1 to parallelize company evaluation across processes.
# The overnight loop sets this to speed up repeated CQS measurements.
DEFAULT_MAX_WORKERS = 1

# 20-company validation cohort: broader coverage for overfitting protection
VALIDATION_COHORT = [
    "AAPL", "MSFT", "GOOG", "AMZN", "META", "NVDA", "TSLA",  # Tech
    "JPM", "BAC", "GS",                                         # Banking
    "XOM", "CVX",                                                # Energy
    "WMT", "PG", "KO", "PEP",                                   # Consumer
    "JNJ", "UNH", "PFE",                                        # Healthcare
    "CAT",                                                       # Industrial
]

# 50-company expansion cohort: first real stress test at scale
EXPANSION_COHORT_50 = [
    # Tech (10)
    "AAPL", "MSFT", "GOOG", "AMZN", "META", "NVDA", "TSLA", "CRM", "ADBE", "INTC",
    # Banking/Finance (8)
    "JPM", "BAC", "GS", "MS", "C", "BLK", "SCHW", "AXP",
    # Energy (4)
    "XOM", "CVX", "COP", "SLB",
    # Consumer (7)
    "WMT", "PG", "KO", "PEP", "MCD", "NKE", "COST",
    # Healthcare/Pharma (7)
    "JNJ", "UNH", "PFE", "LLY", "ABBV", "MRK", "TMO",
    # Industrial (6)
    "CAT", "HON", "GE", "DE", "RTX", "UPS",
    # Other (8)
    "V", "MA", "NEE", "T", "HD", "LOW", "NFLX", "AVGO",
]

# Sub-cohorts for multi-agent parallel evaluation.
# Balanced across sectors with hard gaps distributed:
# CAT in A, MS/DE in B, ABBV in C.
SUB_COHORT_A = [
    "AAPL", "MSFT", "GOOG", "AMZN",    # Tech
    "JPM", "BAC", "GS",                  # Banking
    "XOM", "CVX",                         # Energy
    "WMT", "PG",                          # Consumer
    "JNJ", "UNH",                         # Healthcare
    "CAT", "HON",                         # Industrial (CAT = hard gap)
    "V", "MA",                            # Other
]

SUB_COHORT_B = [
    "META", "NVDA", "TSLA", "CRM",       # Tech
    "MS", "C", "BLK",                     # Banking (MS = hard gap)
    "COP", "SLB",                         # Energy
    "KO", "PEP", "MCD",                   # Consumer
    "PFE", "LLY",                         # Healthcare
    "GE", "DE",                           # Industrial (DE = hard gap)
    "NEE",                                # Other
]

SUB_COHORT_C = [
    "ADBE", "INTC",                       # Tech
    "SCHW", "AXP",                        # Finance
    "NKE", "COST",                        # Consumer
    "ABBV", "MRK", "TMO",                 # Healthcare (ABBV = hard gap)
    "RTX", "UPS",                         # Industrial
    "T", "HD", "LOW", "NFLX", "AVGO",     # Other
]

# 100-company expansion cohort: production-scale stress test
EXPANSION_COHORT_100 = EXPANSION_COHORT_50 + [
    # Semiconductors (4)
    "AMD", "QCOM", "TXN", "MU",
    # Biotech/Pharma (4)
    "GILD", "AMGN", "REGN", "VRTX",
    # REITs (4)
    "PLD", "AMT", "EQIX", "SPG",
    # Utilities (3)
    "DUK", "SO", "D",
    # Telecom/Media (4)
    "CMCSA", "DIS", "VZ", "TMUS",
    # Aerospace/Defense (3)
    "LMT", "BA", "NOC",
    # Food & Beverage (3)
    "MDLZ", "KHC", "STZ",
    # Transportation (3)
    "FDX", "CSX", "NSC",
    # Specialty Finance/Insurance (4)
    "ICE", "CME", "AON", "MMC",
    # Retail/E-commerce (3)
    "TGT", "ROST", "ORLY",
    # Materials/Chemicals (3)
    "LIN", "APD", "SHW",
    # Software/Cloud (4)
    "ORCL", "NOW", "SNOW", "PANW",
    # Medical Devices (3)
    "ABT", "MDT", "SYK",
    # Diversified (5)
    "BRK-B", "DHR", "SPGI", "MCO", "ITW",
]

# 500-company expansion cohort: full S&P 500 scale
# Extends EXPANSION_COHORT_100 with ~400 additional S&P 500 members.
# Organized by GICS sector for balanced subcohort generation.
EXPANSION_COHORT_500 = EXPANSION_COHORT_100 + [
    # Information Technology (40)
    "AMAT", "LRCX", "KLAC", "MCHP", "CDNS", "SNPS", "ANSS", "FTNT",
    "CRWD", "ZS", "DDOG", "TEAM", "WDAY", "SPLK", "CTSH", "INTU",
    "FISV", "FIS", "GPN", "BR", "JKHY", "EPAM", "IT", "MSCI",
    "MPWR", "ON", "NXPI", "ADI", "SWKS", "QRVO", "ENPH", "SEDG",
    "HPQ", "HPE", "DELL", "WDC", "STX", "KEYS", "TER", "ZBRA",
    # Healthcare (35)
    "ISRG", "DXCM", "EW", "ZBH", "BSX", "BDX", "BAX", "HOLX",
    "IDXX", "VEEV", "ZTS", "A", "IQV", "CRL", "MTD", "WST",
    "ALGN", "TFX", "TECH", "BIO", "VTRS", "OGN", "CTLT",
    "CI", "ELV", "HCA", "HUM", "CNC", "MOH", "CVS",
    "BMY", "BIIB", "MRNA", "INCY", "BMRN",
    # Financials (35)
    "WFC", "USB", "PNC", "TFC", "FITB", "KEY", "CFG", "RF", "HBAN",
    "NTRS", "STT", "SIVB", "ZION", "CMA", "FRC",
    "CB", "AIG", "MET", "PRU", "ALL", "TRV", "AFL", "PGR",
    "CINF", "GL", "ERIE",
    "RJF", "MKTX", "CBOE", "NDAQ", "COIN",
    "ARE", "DLR", "O", "PSA",
    # Consumer Discretionary (30)
    "SBUX", "YUM", "CMG", "DPZ", "DARDEN", "HLT", "MAR", "RCL",
    "LVS", "WYNN", "MGM", "BKNG",
    "LULU", "TJX", "DG", "DLTR", "BBY", "TSCO", "ULTA", "AZO",
    "EBAY", "ETSY", "W", "APTV", "GM", "F", "RIVN", "LCID",
    "LEN", "DHI",
    # Industrials (35)
    "MMM", "EMR", "ROK", "ETN", "PH", "DOV", "OTIS", "CARR",
    "SWK", "TT", "IR", "IEX", "NDSN", "ROP",
    "WM", "RSG", "FAST", "CTAS",
    "GWW", "URI", "PWR", "VRSK",
    "TDG", "HWM", "HEI", "GD", "HII", "LHX", "TXT", "CW",
    "DAL", "UAL", "LUV", "ALK", "JBLU",
    # Consumer Staples (20)
    "PM", "MO", "TAP", "BF-B", "SAM",
    "SYY", "HSY", "HRL", "GIS", "K", "CPB", "SJM", "MKC",
    "CL", "CLX", "CHD", "EL", "KMB",
    "KR", "WBA",
    # Energy (15)
    "EOG", "PXD", "FANG", "DVN", "MPC", "PSX", "VLO",
    "HES", "OXY", "HAL", "BKR", "CTRA",
    "KMI", "WMB", "OKE",
    # Utilities (10)
    "AEP", "ED", "EXC", "SRE", "WEC", "ES", "XEL", "PEG",
    "CMS", "AES",
    # Materials (15)
    "ECL", "DD", "PPG", "NUE", "FCX", "NEM", "FMC", "CF",
    "ALB", "CE", "EMN", "IFF", "IP", "PKG", "WRK",
    # Real Estate (10)
    "CCI", "WELL", "AVB", "EQR", "MAA", "UDR", "CPT",
    "SUI", "HST", "PEAK",
    # Communication Services (15)
    "GOOGL", "CHTR", "FOXA", "NWSA", "PARA", "WBD", "LYV",
    "MTCH", "EA", "TTWO", "ATVI", "RBLX",
    "TRMB", "ZM", "TWLO",
    # Additional Technology (20)
    "AKAM", "FFIV", "JNPR", "NTAP", "PAYC", "PCTY", "MANH",
    "TYL", "TOST", "BILL", "SQ", "PYPL", "AFRM", "SHOP",
    "NET", "MDB", "DOCU", "OKTA", "U", "PLTR",
    # Additional Healthcare (15)
    "CAH", "MCK", "ABC", "GEHC", "RMD", "COO", "XRAY",
    "HSIC", "PODD", "RVMD", "EXAS", "SRPT", "ALNY", "SGEN", "NBIX",
    # Additional Financials (20)
    "TROW", "BEN", "IVZ", "AMG", "SEIC", "EV",
    "L", "ACGL", "RNR", "W-R", "AIZ", "BRO", "WRB", "RLI",
    "MTB", "FCNCA", "FHN", "EWBC", "WAL", "PACW",
    # Additional Industrials (20)
    "AME", "XYL", "GNRC", "AOS", "SNA",
    "PCAR", "ODFL", "SAIA", "J", "EXPD",
    "WAB", "HUBB", "ALLE", "MAS", "WTS",
    "PAYX", "CPRT", "CSGP", "CBRE", "JCI",
    # Additional Consumer (15)
    "RH", "GRMN", "DECK", "CROX", "FIVE", "OLLI", "BOOT",
    "PENN", "CZR", "DKNG",
    "ABNB", "EXPE", "TRIP", "LYFT", "UBER",
    # Additional Materials/Chemicals (10)
    "BALL", "AVY", "SEE", "SON", "RPM",
    "VMC", "MLM", "CCK", "LYB", "DOW",
    # Additional Energy (10)
    "TRGP", "LNG", "DINO", "MRO", "APA",
    "AR", "RRC", "EQT", "SWN", "CNX",
    # Additional Utilities (10)
    "AWK", "WTRG", "NI", "EVRG", "PNW",
    "DTE", "ATO", "CNP", "LNT", "FE",
    # Additional REITs (10)
    "VTR", "KIM", "REG", "FRT", "BXP",
    "SLG", "VNO", "MPW", "OHI", "NNN",
    # Additional Misc (10)
    "VRSN", "GEN", "WEX", "LDOS", "SAIC",
    "CACI", "BAH", "KBR", "TTEK", "LECO",
]


# =============================================================================
# DYNAMIC SUB-COHORT GENERATION
# =============================================================================

def generate_subcohorts(
    tickers: List[str],
    k: int,
    ledger=None,
) -> List[List[str]]:
    """Split N tickers into K balanced sub-cohorts.

    Balancing criteria:
    1. Sector diversity (round-robin by industry)
    2. Hard gaps distributed evenly (using graveyard counts)
    3. Roughly equal size (max diff = 1)

    Args:
        tickers: Full list of tickers to partition.
        k: Number of sub-cohorts to create.
        ledger: Optional ExperimentLedger for graveyard counts.

    Returns:
        List of K sub-cohort lists, each roughly N/k tickers.
    """
    from edgar.xbrl.standardization.config_loader import get_config

    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    if k >= len(tickers):
        return [[t] for t in tickers]

    config = get_config()

    # Group tickers by industry
    industry_groups: Dict[str, List[Tuple[str, int]]] = {}
    for ticker in tickers:
        industry = _get_ticker_industry(ticker, config)
        graveyard_count = 0
        if ledger is not None:
            try:
                entries = ledger.get_graveyard_entries(ticker)
                graveyard_count = len(entries) if entries else 0
            except Exception:
                pass
        industry_groups.setdefault(industry, []).append((ticker, graveyard_count))

    # Within each industry, sort by graveyard count descending (hard gaps first)
    for industry in industry_groups:
        industry_groups[industry].sort(key=lambda x: x[1], reverse=True)

    # Round-robin assign across K buckets
    buckets: List[List[str]] = [[] for _ in range(k)]
    bucket_idx = 0

    # Iterate through industries in sorted order for determinism
    for industry in sorted(industry_groups.keys()):
        for ticker, _count in industry_groups[industry]:
            buckets[bucket_idx].append(ticker)
            bucket_idx = (bucket_idx + 1) % k

    return buckets


def _get_ticker_industry(ticker: str, config) -> str:
    """Get industry for a ticker, with graceful fallback."""
    try:
        company = config.companies.get(ticker)
        industry = config._get_industry_for_company(ticker, company)
        if industry:
            return industry
    except Exception:
        pass
    return "other"


# =============================================================================
# HEADLINE METRICS — the most critical metrics for subscription-grade quality.
# These must achieve >= 0.99 EF rate before launch.
# =============================================================================

HEADLINE_METRICS = [
    "Revenue",
    "NetIncome",
    "TotalAssets",
    "OperatingCashFlow",
    "StockholdersEquity",
    "OperatingIncome",
    "EPS",
    "TotalLiabilities",
]


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class CompanyCQS:
    """Per-company quality breakdown."""
    ticker: str
    pass_rate: float           # Fraction of metrics passing validation [0-1]
    mean_variance: float       # Average variance % across validated metrics
    coverage_rate: float       # Fraction of non-excluded metrics mapped [0-1]
    golden_master_rate: float  # Fraction of metrics with golden masters [0-1]
    regression_count: int      # Number of regressions vs previous baseline
    metrics_total: int         # Total non-excluded metrics
    metrics_mapped: int        # Mapped metrics
    metrics_valid: int         # Validation-passing metrics
    metrics_excluded: int      # CONFIG-excluded metrics
    cqs: float                 # Composite quality score for this company
    # Two-score architecture
    ef_pass_rate: float = 0.0  # Extraction Fidelity: fraction of correctly extracted concepts
    sa_pass_rate: float = 0.0  # Standardization Alignment: fraction matching yfinance
    ef_cqs: float = 0.0       # EF component of CQS
    sa_cqs: float = 0.0       # SA component of CQS
    explained_variance_count: int = 0  # Gaps with documented explanations
    # RFA/SMA sub-scores (finer than EF)
    rfa_pass_rate: float = 0.0  # Reported Fact Accuracy: value matches authoritative source
    sma_pass_rate: float = 0.0  # Standardized Metric Accuracy: concept semantically correct
    unverified_count: int = 0  # Metrics with no reference data (excluded from pass/fail)
    unverified_metrics: List[str] = field(default_factory=list)  # Which metrics are unverified
    failed_metrics: List[str] = field(default_factory=list)  # Metrics that failed validation
    failed_metric_refs: Dict[str, Optional[float]] = field(default_factory=dict)  # metric -> reference_value for failed metrics
    regressed_metrics: List[str] = field(default_factory=list)  # Metrics that regressed from golden
    disputed_count: int = 0  # Metrics excluded due to reference_disputed
    headline_ef_rate: float = 0.0  # EF rate for headline metrics only (target: >= 0.99)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> 'CompanyCQS':
        """Reconstruct from to_dict() output."""
        return cls(**d)


@dataclass
class ExtractionEvidence:
    """Structured diagnostic explaining what the validator actually extracted and why."""
    metric: str
    ticker: str
    reference_value: Optional[float] = None       # yfinance target
    extracted_value: Optional[float] = None        # what validator actually got
    resolution_type: str = "none"                  # "direct" | "composite" | "industry" | "none"
    components_used: List[str] = field(default_factory=list)     # XBRL concepts actually used
    components_missing: List[str] = field(default_factory=list)  # Expected components not found
    period_selected: str = ""                      # Which period was used
    variance_pct: Optional[float] = None           # Actual variance
    failure_reason: str = ""                       # Human-readable explanation
    company_industry: Optional[str] = None         # Industry from config or SIC lookup


@dataclass
class MetricGap:
    """A gap in the extraction pipeline, ranked by CQS impact."""
    ticker: str
    metric: str
    gap_type: str              # "unmapped" | "validation_failure" | "high_variance" | "regression" | "explained_variance" | "reference_disputed"
    estimated_impact: float    # Estimated CQS improvement if resolved [0-1]
    current_variance: Optional[float] = None
    reference_value: Optional[float] = None
    xbrl_value: Optional[float] = None
    graveyard_count: int = 0   # Number of prior failed attempts
    notes: str = ""
    variance_type: str = "raw" # "raw" | "explained" | "standardized"
    extraction_evidence: Optional[ExtractionEvidence] = None  # Diagnostic evidence from validator
    hv_subtype: Optional[str] = None  # "hv_missing_component" | "hv_wrong_concept" | "hv_missing_industry" | "hv_period_mismatch"
    root_cause: Optional[str] = None  # Detailed root cause from taxonomy

    @property
    def fix_tier(self) -> str:
        """Determine fix tier based on root cause."""
        TIER_1A = {"missing_concept", "wrong_concept", "industry_structural", "formula_needed"}
        TIER_1B = {"extension_concept", "partial_composite", "sign_error", "algebraic_coincidence"}
        TIER_2 = {"scale_mismatch", "reference_error"}
        if self.root_cause in TIER_1A:
            return "1A"
        elif self.root_cause in TIER_1B:
            return "1B"
        elif self.root_cause in TIER_2:
            return "2"
        else:
            return "3"

    @property
    def is_dead_end(self) -> bool:
        """Skip gaps with too many prior failures across ALL strategies."""
        # Threshold is 6 (3 per strategy × 2 strategies: heuristic + solver)
        # to prevent one strategy's failures from killing another's budget
        return self.graveyard_count >= 6


@dataclass
class TimingBreakdown:
    """Per-company timing data from a CQS computation."""
    per_company: Dict[str, float]   # ticker -> seconds
    total_seconds: float
    parallelism: int                # max_workers used
    companies_evaluated: int


@dataclass
class CQSResult:
    """
    Composite Quality Score — the single number that drives auto-eval decisions.

    CQS = weighted sum of sub-metrics, with hard veto on regressions.
    """
    # Aggregate sub-metrics
    pass_rate: float           # Weight: 0.50
    mean_variance: float       # Weight: 0.20 (inverted: lower is better)
    coverage_rate: float       # Weight: 0.15
    golden_master_rate: float  # Weight: 0.10
    regression_rate: float     # Weight: 0.05 (inverted: lower is better)

    # The composite score
    cqs: float

    # Metadata
    companies_evaluated: int
    total_metrics: int
    total_mapped: int
    total_valid: int
    total_regressions: int

    # Two-score architecture
    ef_cqs: float = 0.0        # Extraction Fidelity CQS
    sa_cqs: float = 0.0        # Standardization Alignment CQS
    ef_pass_rate: float = 0.0  # Aggregate EF pass rate
    sa_pass_rate: float = 0.0  # Aggregate SA pass rate
    explained_variance_count: int = 0  # Total explained variance gaps
    # RFA/SMA sub-scores
    rfa_rate: float = 0.0   # Reported Fact Accuracy aggregate
    sma_rate: float = 0.0   # Standardized Metric Accuracy aggregate
    # Headline metrics (subscription-grade targets)
    headline_ef_rate: float = 0.0  # EF rate for headline metrics only (target: >= 0.99)

    # Per-company breakdown
    company_scores: Dict[str, CompanyCQS] = field(default_factory=dict)

    # Timing
    duration_seconds: float = 0.0

    # Whether regressions triggered hard veto
    vetoed: bool = False

    # Per-company timing breakdown
    timing: Optional[TimingBreakdown] = None

    # All regressed metrics as (ticker, metric) tuples
    regressed_metrics: List[Tuple[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d['company_scores'] = {k: v.to_dict() if isinstance(v, CompanyCQS) else v
                               for k, v in self.company_scores.items()}
        return d

    @classmethod
    def from_dict(cls, d: dict) -> 'CQSResult':
        """Reconstruct from to_dict() output. TimingBreakdown is dropped (not needed for cache)."""
        d = dict(d)  # Preserve caller's dict
        company_scores = {
            k: CompanyCQS.from_dict(v)
            for k, v in d.pop('company_scores', {}).items()
        }
        d.pop('timing', None)
        d['company_scores'] = company_scores
        # Convert regressed_metrics list of lists back to tuples
        d['regressed_metrics'] = [tuple(x) for x in d.get('regressed_metrics', [])]
        return cls(**d)

    def summary(self) -> str:
        """One-line summary."""
        veto = " [VETOED]" if self.vetoed else ""
        return (
            f"EF={self.ef_cqs:.4f} headline={self.headline_ef_rate:.4f}{veto} | "
            f"RFA={self.rfa_rate:.4f} SMA={self.sma_rate:.4f} SA={self.sa_cqs:.4f} | "
            f"CQS={self.cqs:.4f} pass={self.pass_rate:.1%} var={self.mean_variance:.1f}% "
            f"cov={self.coverage_rate:.1%} golden={self.golden_master_rate:.1%} "
            f"regress={self.total_regressions} | "
            f"{self.companies_evaluated} cos, {self.duration_seconds:.1f}s"
        )


@dataclass
class LISResult:
    """
    Localized Impact Score — targeted decision metric for single-metric fixes.

    Global CQS at 0.9957 produces ~0.0003 delta for single-metric fixes,
    below the noise floor. LIS checks only what matters:
    1. Did the target metric improve?
    2. Did any other metric regress?
    3. Is overall pass_rate non-regressing?

    When lis_pass is True, the autonomous loop can skip the global CQS
    improvement check (which would discard correct fixes).
    """
    target_improved: bool          # Target metric now passes (was in failed_metrics)
    target_metric_improved: bool   # More specific: the exact target metric improved
    zero_regressions: bool         # No new regressions introduced
    lis_pass: bool                 # Overall LIS decision: improved AND no regressions
    target_delta_pp: float         # Target company pass_rate delta in percentage points
    detail: str                    # Human-readable explanation


def compute_lis(
    baseline_result: CQSResult,
    target_ticker: str,
    target_metric: str,
    new_company_cqs: 'CompanyCQS',
    multi_period: bool = False,
) -> LISResult:
    """
    Compute Localized Impact Score for a single-metric fix.

    Checks whether a config change fixed the target metric without
    introducing regressions. This replaces the global CQS improvement
    check for company-scoped changes.

    Args:
        baseline_result: CQS result before the change.
        target_ticker: The ticker being targeted.
        target_metric: The metric being fixed.
        new_company_cqs: The new CompanyCQS for the target company after the change.
        multi_period: If True, run multi-period validation (slower, requires network).
                      Default True for overnight runs, False for interactive use.

    Returns:
        LISResult with pass/fail decision and detail.
    """
    baseline_company = baseline_result.company_scores.get(target_ticker)
    if baseline_company is None:
        return LISResult(
            target_improved=False,
            target_metric_improved=False,
            zero_regressions=True,
            lis_pass=False,
            target_delta_pp=0.0,
            detail=f"No baseline data for {target_ticker}",
        )

    # (a) Target metric no longer in failed_metrics
    was_failing = target_metric in baseline_company.failed_metrics
    now_passing = target_metric not in new_company_cqs.failed_metrics
    target_metric_improved = was_failing and now_passing

    # (b) No new regressions
    new_regressions = new_company_cqs.regression_count - baseline_company.regression_count
    zero_regressions = new_regressions <= 0

    # (c) Pass rate non-regressing
    pass_rate_ok = new_company_cqs.pass_rate >= baseline_company.pass_rate - 0.001

    # Target company improved (broader check: pass_rate went up or stayed level with metric fix)
    target_improved = (
        new_company_cqs.pass_rate >= baseline_company.pass_rate
        or target_metric_improved
    )

    # Delta in percentage points
    target_delta_pp = (new_company_cqs.pass_rate - baseline_company.pass_rate) * 100

    # LIS passes if: target metric fixed + no regressions + pass_rate non-regressing
    lis_pass = target_metric_improved and zero_regressions and pass_rate_ok

    detail_parts = []
    if target_metric_improved:
        detail_parts.append(f"{target_metric} fixed (was failing, now passing)")
    elif was_failing:
        detail_parts.append(f"{target_metric} still failing")
    else:
        detail_parts.append(f"{target_metric} was not failing")

    if not zero_regressions:
        detail_parts.append(f"{new_regressions} new regression(s)")
    if not pass_rate_ok:
        detail_parts.append(f"pass_rate regressed ({baseline_company.pass_rate:.1%} -> {new_company_cqs.pass_rate:.1%})")

    # Optional multi-period validation: if LIS passes single-period,
    # also check that the mapping holds across 3+ annual filings.
    # This catches algebraic coincidences where a mapping works for one year
    # but not historically.
    if multi_period and lis_pass:
        try:
            from edgar.xbrl.standardization.reference_validator import ReferenceValidator
            validator = ReferenceValidator(use_sec_facts=True)
            # Get the concept from the new company's mapping (if available)
            # We don't have direct access to the concept here, but we can
            # use the validate_mapping_across_periods which uses the orchestrator
            mp_result = validator.validate_mapping_across_periods(
                target_ticker, target_metric, concept="", n_periods=3,
            )
            if not mp_result.is_stable:
                lis_pass = False
                detail_parts.append(
                    f"multi-period FAIL: {mp_result.detail}"
                )
            else:
                detail_parts.append(
                    f"multi-period OK: {mp_result.periods_passed}/{mp_result.periods_checked}"
                )
        except Exception as e:
            # Multi-period is best-effort — don't block LIS on errors
            logger.debug(f"Multi-period validation error for {target_ticker}:{target_metric}: {e}")
            detail_parts.append(f"multi-period skipped: {e}")

    detail = "; ".join(detail_parts)

    return LISResult(
        target_improved=target_improved,
        target_metric_improved=target_metric_improved,
        zero_regressions=zero_regressions,
        lis_pass=lis_pass,
        target_delta_pp=target_delta_pp,
        detail=detail,
    )


def list_regressions(cqs_result: CQSResult) -> List[Tuple[str, str]]:
    """List all regressed metrics from a CQS result.

    Returns: [(ticker, metric), ...] for every metric that was previously golden
    but now fails validation.
    """
    return list(cqs_result.regressed_metrics)


def clear_regressions(cqs_result: CQSResult, ledger=None) -> int:
    """Clear golden masters for all regressed metrics so they can be re-promoted.

    Args:
        cqs_result: CQS result with regressed_metrics populated.
        ledger: ExperimentLedger instance (uses default if None).

    Returns:
        Number of golden masters deactivated.
    """
    from edgar.xbrl.standardization.ledger.schema import ExperimentLedger
    if ledger is None:
        ledger = ExperimentLedger()

    regressed = list_regressions(cqs_result)
    if not regressed:
        return 0

    return ledger.clear_regressed_golden_masters(regressed)


# =============================================================================
# CQS COMPUTATION
# =============================================================================

def compute_cqs(
    eval_cohort: Optional[List[str]] = None,
    snapshot_mode: bool = True,
    use_ai: bool = False,
    baseline_cqs: Optional[float] = None,
    ledger=None,
    max_workers: Optional[int] = None,
    config=None,
    use_sec_facts: bool = True,
) -> CQSResult:
    """
    Compute the Composite Quality Score for a cohort of companies.

    This is the core measurement function — the "val_bpb" of our system.
    It runs the full Orchestrator pipeline and validates against yfinance
    snapshots, then computes a single composite score.

    Args:
        eval_cohort: List of tickers to evaluate (defaults to QUICK_EVAL_COHORT).
        snapshot_mode: Use cached yfinance snapshots (True for speed).
        use_ai: Whether to use Layer 3 AI mapping (False for deterministic eval).
        baseline_cqs: If provided, regressions trigger hard veto below this value.
        ledger: ExperimentLedger instance for golden master lookups.
        max_workers: Parallel workers (None = use DEFAULT_MAX_WORKERS).
        config: In-memory MappingConfig for parallel eval (None = load from disk).

    Returns:
        CQSResult with composite score and per-company breakdown.
    """
    from edgar.xbrl.standardization.orchestrator import Orchestrator
    from edgar.xbrl.standardization.ledger.schema import ExperimentLedger

    start_time = time.time()

    if eval_cohort is None:
        eval_cohort = QUICK_EVAL_COHORT

    if ledger is None:
        ledger = ExperimentLedger()

    # Run orchestrator on the cohort
    workers = max_workers if max_workers is not None else DEFAULT_MAX_WORKERS
    orchestrator = Orchestrator(config=config, snapshot_mode=snapshot_mode, use_sec_facts=use_sec_facts)
    all_results = orchestrator.map_companies(
        tickers=eval_cohort, use_ai=use_ai, validate=True,
        max_workers=workers,
    )

    # Gather golden masters for regression detection
    golden_masters = ledger.get_all_golden_masters(active_only=True)
    golden_set = {(gm.ticker, gm.metric) for gm in golden_masters}

    # Compute per-company scores
    company_scores: Dict[str, CompanyCQS] = {}

    for ticker, metrics in all_results.items():
        company_scores[ticker] = _compute_company_cqs(
            ticker, metrics, golden_set, orchestrator.validation_results.get(ticker, {})
        )

    # Aggregate across companies
    result = _aggregate_cqs(company_scores, baseline_cqs, time.time() - start_time)

    # Attach per-company timing if available
    if orchestrator._company_timings:
        result.timing = TimingBreakdown(
            per_company=dict(orchestrator._company_timings),
            total_seconds=result.duration_seconds,
            parallelism=workers,
            companies_evaluated=len(eval_cohort),
        )

    # Record valid results and promote golden masters
    count = record_eval_results(all_results, orchestrator.validation_results, ledger)
    if count > 0:
        promoted = ledger.promote_golden_masters()  # Uses default min_periods=3
        logger.info(f"Recorded {count} extraction runs, promoted {len(promoted)} golden masters")

    logger.info(f"Auto-eval complete: {result.summary()}")
    return result


# =============================================================================
# INCREMENTAL CQS (Phase 2a)
# =============================================================================

# Change types that only affect specific companies (safe for incremental eval)
_COMPANY_SCOPED_CHANGES = frozenset([
    "add_exclusion",
    "add_known_variance",
    "add_company_override",
    "set_industry",
])

# Change types that can affect ALL companies (must use full eval)
_GLOBAL_SCOPED_CHANGES = frozenset([
    "add_concept",
    "add_tree_hint",
    "add_standardization",
    "remove_pattern",
    "modify_value",
    "add_divergence",
])


def is_change_company_scoped(change) -> bool:
    """Determine if a config change only affects specific companies.

    Company-scoped changes are safe for incremental CQS — they can't cause
    cross-company regressions. Global changes MUST use full-cohort evaluation.
    """
    change_type = change.change_type.value if hasattr(change.change_type, 'value') else str(change.change_type)
    if change_type in _COMPANY_SCOPED_CHANGES:
        # Must also have specific target companies
        targets = [t.strip() for t in change.target_companies.split(",") if t.strip()]
        return len(targets) > 0
    return False


def get_affected_tickers(change) -> List[str]:
    """Extract the list of tickers affected by a config change."""
    return [t.strip() for t in change.target_companies.split(",") if t.strip()]


def compute_cqs_incremental(
    baseline_result: CQSResult,
    change,
    config,
    eval_cohort: Optional[List[str]] = None,
    ledger=None,
    max_workers: Optional[int] = None,
    use_sec_facts: bool = True,
) -> CQSResult:
    """Incrementally recompute CQS after a config change.

    For company-scoped changes (add_exclusion, add_known_variance), only
    re-evaluates the affected company(ies) and substitutes into the baseline
    matrix. For global changes, falls back to full compute_cqs().

    Args:
        baseline_result: The CQSResult from the previous evaluation.
        change: ConfigChange describing what was modified.
        config: The MappingConfig with the change already applied.
        eval_cohort: Full list of tickers in the cohort.
        ledger: ExperimentLedger for golden master lookups.
        max_workers: Parallel workers for full eval fallback.

    Returns:
        Updated CQSResult with the change reflected.
    """
    from edgar.xbrl.standardization.orchestrator import Orchestrator
    from edgar.xbrl.standardization.ledger.schema import ExperimentLedger

    start_time = time.time()

    if eval_cohort is None:
        eval_cohort = QUICK_EVAL_COHORT

    if ledger is None:
        ledger = ExperimentLedger()

    # Safety check: global changes must use full eval
    if not is_change_company_scoped(change):
        logger.info(
            f"Incremental CQS: change type '{change.change_type.value}' is global-scoped, "
            f"falling back to full compute_cqs()"
        )
        return compute_cqs(
            eval_cohort=eval_cohort,
            snapshot_mode=True,
            use_ai=False,
            baseline_cqs=baseline_result.cqs,
            ledger=ledger,
            max_workers=max_workers,
            config=config,
            use_sec_facts=use_sec_facts,
        )

    affected = get_affected_tickers(change)
    # Only re-evaluate tickers that are in the eval cohort
    affected_in_cohort = [t for t in affected if t in baseline_result.company_scores]

    if not affected_in_cohort:
        # Change doesn't affect any company in the cohort — return baseline unchanged
        logger.info(f"Incremental CQS: no affected tickers in cohort, returning baseline")
        return baseline_result

    # Re-evaluate only the affected companies with the new config
    workers = max_workers if max_workers is not None else DEFAULT_MAX_WORKERS
    orchestrator = Orchestrator(config=config, snapshot_mode=True, use_sec_facts=use_sec_facts)
    updated_results = orchestrator.map_companies(
        tickers=affected_in_cohort, use_ai=False, validate=True,
        max_workers=min(workers, len(affected_in_cohort)),
    )

    # Gather golden masters
    golden_masters = ledger.get_all_golden_masters(active_only=True)
    golden_set = {(gm.ticker, gm.metric) for gm in golden_masters}

    # Build updated company_scores: start from baseline, substitute affected
    updated_scores = dict(baseline_result.company_scores)
    for ticker in affected_in_cohort:
        if ticker in updated_results:
            updated_scores[ticker] = _compute_company_cqs(
                ticker,
                updated_results[ticker],
                golden_set,
                orchestrator.validation_results.get(ticker, {}),
            )

    # Re-aggregate with the updated matrix
    result = _aggregate_cqs(updated_scores, baseline_result.cqs, time.time() - start_time)

    # Record results for affected companies
    if updated_results:
        record_eval_results(updated_results, orchestrator.validation_results, ledger)

    logger.info(
        f"Incremental CQS: re-evaluated {len(affected_in_cohort)} company(ies) "
        f"({', '.join(affected_in_cohort)}), "
        f"CQS {baseline_result.cqs:.4f} -> {result.cqs:.4f} "
        f"({time.time() - start_time:.1f}s)"
    )
    return result


def compute_cqs_incremental_batch(
    baseline_result: CQSResult,
    changes: list,
    config,
    eval_cohort: Optional[List[str]] = None,
    ledger=None,
    max_workers: Optional[int] = None,
    use_sec_facts: bool = True,
) -> CQSResult:
    """Incrementally recompute CQS after multiple company-scoped changes.

    Collects all affected tickers from the batch of changes, re-evaluates
    them in a single orchestrator run, and re-aggregates the matrix.

    All changes must be company-scoped. If any global change is present,
    falls back to full compute_cqs().

    Args:
        baseline_result: CQSResult from previous evaluation.
        changes: List of ConfigChanges already applied to config.
        config: MappingConfig with all changes applied.
        eval_cohort: Full cohort tickers.
        ledger: ExperimentLedger.
        max_workers: Workers for orchestrator.

    Returns:
        Updated CQSResult with all changes reflected.
    """
    from edgar.xbrl.standardization.orchestrator import Orchestrator
    from edgar.xbrl.standardization.ledger.schema import ExperimentLedger

    start_time = time.time()

    if eval_cohort is None:
        eval_cohort = QUICK_EVAL_COHORT

    if ledger is None:
        ledger = ExperimentLedger()

    # Collect all affected tickers across the batch
    all_affected = set()
    for change in changes:
        if not is_change_company_scoped(change):
            logger.info(
                f"Incremental batch: found global change '{change.change_type.value}', "
                f"falling back to full eval"
            )
            return compute_cqs(
                eval_cohort=eval_cohort,
                snapshot_mode=True,
                use_ai=False,
                baseline_cqs=baseline_result.cqs,
                ledger=ledger,
                max_workers=max_workers,
                config=config,
                use_sec_facts=use_sec_facts,
            )
        all_affected.update(get_affected_tickers(change))

    # Only re-evaluate tickers in the eval cohort
    affected_in_cohort = [t for t in all_affected if t in baseline_result.company_scores]

    if not affected_in_cohort:
        return baseline_result

    # Re-evaluate affected companies with the batch config
    workers = max_workers if max_workers is not None else DEFAULT_MAX_WORKERS
    orchestrator = Orchestrator(config=config, snapshot_mode=True, use_sec_facts=use_sec_facts)
    updated_results = orchestrator.map_companies(
        tickers=affected_in_cohort, use_ai=False, validate=True,
        max_workers=min(workers, len(affected_in_cohort)),
    )

    golden_masters = ledger.get_all_golden_masters(active_only=True)
    golden_set = {(gm.ticker, gm.metric) for gm in golden_masters}

    updated_scores = dict(baseline_result.company_scores)
    for ticker in affected_in_cohort:
        if ticker in updated_results:
            updated_scores[ticker] = _compute_company_cqs(
                ticker,
                updated_results[ticker],
                golden_set,
                orchestrator.validation_results.get(ticker, {}),
            )

    result = _aggregate_cqs(updated_scores, baseline_result.cqs, time.time() - start_time)

    if updated_results:
        record_eval_results(updated_results, orchestrator.validation_results, ledger)

    logger.info(
        f"Incremental batch CQS: {len(changes)} changes, "
        f"re-evaluated {len(affected_in_cohort)} company(ies), "
        f"CQS {baseline_result.cqs:.4f} -> {result.cqs:.4f} "
        f"({time.time() - start_time:.1f}s)"
    )
    return result


def _compute_company_cqs(
    ticker: str,
    metrics: Dict[str, MappingResult],
    golden_set: set,
    validations: dict,
) -> CompanyCQS:
    """Compute CQS sub-metrics for a single company."""
    total = 0
    mapped = 0
    valid = 0
    excluded = 0
    variances = []
    golden_count = 0
    regression_count = 0
    regressed_metrics = []
    ef_pass_count = 0
    sa_pass_count = 0
    rfa_pass_count = 0
    sma_pass_count = 0
    explained_variance_count = 0
    unverified_count = 0
    unverified_metrics_list = []
    failed_metrics = []
    failed_metric_refs = {}
    disputed_count = 0
    headline_ef_pass = 0
    headline_ef_total = 0

    for metric, result in metrics.items():
        if result.source == MappingSource.CONFIG:
            excluded += 1
            # Count exclusions as correctly handled — the system identified
            # this metric as non-applicable for the company and excluded it.
            total += 1
            valid += 1
            mapped += 1
            ef_pass_count += 1
            continue

        total += 1

        # Handle unverified metrics — exclude from ALL scoring (coverage, pass/fail, etc.)
        if result.validation_status == "unverified":
            unverified_count += 1
            unverified_metrics_list.append(metric)
            continue  # Don't count in any denominator or numerator

        # Single validation lookup per metric
        val_result = validations.get(metric)

        # Handle documented divergences — exclude from pass/fail scoring
        # (no penalty, no unearned credit; still counts as mapped)
        if val_result and val_result.variance_type == "explained":
            if result.is_mapped:
                mapped += 1
            explained_variance_count += 1
            continue  # Skip pass/fail/golden evaluation

        if result.is_mapped:
            mapped += 1

        # Check validation status
        if result.validation_status == "valid":
            valid += 1
        elif result.validation_status == "invalid":
            # A previously golden metric that now fails = regression
            if (ticker, metric) in golden_set:
                regression_count += 1
                regressed_metrics.append(metric)

        # Track failed metrics for derive_gaps_from_cqs fast path
        if result.validation_status != "valid" and result.source != MappingSource.CONFIG:
            failed_metrics.append(metric)
            failed_metric_refs[metric] = val_result.reference_value if val_result else None

        # Collect variance from validation results
        if val_result and val_result.variance_pct is not None:
            variances.append(abs(val_result.variance_pct))

        # Detect reference_disputed -- exclude from pass/fail
        if val_result and hasattr(val_result, 'notes') and val_result.notes:
            if 'reference suspect' in (val_result.notes or '').lower():
                disputed_count += 1

        # EF/SA/RFA/SMA scoring from validation results
        if val_result:
            if val_result.ef_pass:
                ef_pass_count += 1
            if val_result.sa_pass:
                sa_pass_count += 1
            if val_result.rfa_pass:
                rfa_pass_count += 1
            if val_result.sma_pass:
                sma_pass_count += 1
        elif result.is_mapped and result.source == MappingSource.TREE:
            # Tree-resolved with no validation = EF pass (trusted source)
            ef_pass_count += 1

        # Track headline metrics separately
        if metric in HEADLINE_METRICS and result.source != MappingSource.CONFIG:
            if result.validation_status != "unverified":
                headline_ef_total += 1
                if val_result and val_result.ef_pass:
                    headline_ef_pass += 1
                elif result.is_mapped and result.source == MappingSource.TREE and not val_result:
                    headline_ef_pass += 1

        # Check golden master status
        if (ticker, metric) in golden_set:
            golden_count += 1

    # Compute sub-metrics (exclude disputed + unverified + documented divergence from denominators)
    effective_total = total - disputed_count - unverified_count - explained_variance_count
    pass_rate = valid / effective_total if effective_total > 0 else 0.0
    mean_variance = sum(variances) / len(variances) if variances else 0.0
    coverage_rate = min(1.0, mapped / effective_total) if effective_total > 0 else 0.0
    golden_master_rate = golden_count / effective_total if effective_total > 0 else 0.0
    ef_pass_rate = ef_pass_count / effective_total if effective_total > 0 else 0.0
    sa_pass_rate = sa_pass_count / effective_total if effective_total > 0 else 0.0
    rfa_pass_rate = rfa_pass_count / effective_total if effective_total > 0 else 0.0
    sma_pass_rate = sma_pass_count / effective_total if effective_total > 0 else 0.0
    headline_ef_rate = headline_ef_pass / headline_ef_total if headline_ef_total > 0 else 0.0

    cqs = (
        0.45 * pass_rate
        + 0.20 * max(0, 1 - mean_variance / 100)
        + 0.15 * coverage_rate
        + 0.15 * golden_master_rate
        + 0.05 * (1.0 if regression_count == 0 else 0.0)
    )

    # EF-CQS: extraction fidelity component (concept found correctly)
    ef_cqs = ef_pass_rate

    # SA-CQS: standardization alignment (value matches yfinance)
    sa_cqs = sa_pass_rate

    return CompanyCQS(
        ticker=ticker,
        pass_rate=pass_rate,
        mean_variance=mean_variance,
        coverage_rate=coverage_rate,
        golden_master_rate=golden_master_rate,
        regression_count=regression_count,
        metrics_total=total,
        metrics_mapped=mapped,
        metrics_valid=valid,
        metrics_excluded=excluded,
        cqs=cqs,
        ef_pass_rate=ef_pass_rate,
        sa_pass_rate=sa_pass_rate,
        ef_cqs=ef_cqs,
        sa_cqs=sa_cqs,
        explained_variance_count=explained_variance_count,
        rfa_pass_rate=rfa_pass_rate,
        sma_pass_rate=sma_pass_rate,
        unverified_count=unverified_count,
        unverified_metrics=unverified_metrics_list,
        failed_metrics=failed_metrics,
        failed_metric_refs=failed_metric_refs,
        regressed_metrics=regressed_metrics,
        disputed_count=disputed_count,
        headline_ef_rate=headline_ef_rate,
    )


def _aggregate_cqs(
    company_scores: Dict[str, CompanyCQS],
    baseline_cqs: Optional[float],
    duration: float,
) -> CQSResult:
    """Aggregate per-company scores into a single CQS."""
    if not company_scores:
        return CQSResult(
            pass_rate=0, mean_variance=0, coverage_rate=0,
            golden_master_rate=0, regression_rate=0, cqs=0,
            companies_evaluated=0, total_metrics=0, total_mapped=0,
            total_valid=0, total_regressions=0, duration_seconds=duration,
        )

    n = len(company_scores)
    scores = list(company_scores.values())

    # Weighted average (equal weight per company)
    pass_rate = sum(s.pass_rate for s in scores) / n
    mean_variance = sum(s.mean_variance for s in scores) / n
    coverage_rate = sum(s.coverage_rate for s in scores) / n
    golden_master_rate = sum(s.golden_master_rate for s in scores) / n

    total_regressions = sum(s.regression_count for s in scores)
    total_metrics = sum(s.metrics_total for s in scores)
    regression_rate = total_regressions / total_metrics if total_metrics > 0 else 0.0

    # Aggregate EF/SA/RFA/SMA scores
    ef_pass_rate = sum(s.ef_pass_rate for s in scores) / n
    sa_pass_rate = sum(s.sa_pass_rate for s in scores) / n
    rfa_rate = sum(s.rfa_pass_rate for s in scores) / n
    sma_rate = sum(s.sma_pass_rate for s in scores) / n
    explained_variance_count = sum(s.explained_variance_count for s in scores)
    headline_ef_rate = sum(s.headline_ef_rate for s in scores) / n

    # Collect all regressed metrics across companies
    all_regressed = []
    for ticker, cs in company_scores.items():
        for m in cs.regressed_metrics:
            all_regressed.append((ticker, m))

    raw_cqs = (
        0.45 * pass_rate
        + 0.20 * max(0, 1 - mean_variance / 100)
        + 0.15 * coverage_rate
        + 0.15 * golden_master_rate
        + 0.05 * (1 - regression_rate)
    )

    # EF-CQS and SA-CQS (simple averages across companies)
    ef_cqs = sum(s.ef_cqs for s in scores) / n
    sa_cqs = sum(s.sa_cqs for s in scores) / n

    # Note: regression veto logic moved to evaluate_experiment() which compares
    # new vs baseline regression counts. _aggregate_cqs computes honest scores.

    return CQSResult(
        pass_rate=pass_rate,
        mean_variance=mean_variance,
        coverage_rate=coverage_rate,
        golden_master_rate=golden_master_rate,
        regression_rate=regression_rate,
        cqs=raw_cqs,
        ef_cqs=ef_cqs,
        sa_cqs=sa_cqs,
        ef_pass_rate=ef_pass_rate,
        sa_pass_rate=sa_pass_rate,
        explained_variance_count=explained_variance_count,
        rfa_rate=rfa_rate,
        sma_rate=sma_rate,
        headline_ef_rate=headline_ef_rate,
        companies_evaluated=n,
        total_metrics=total_metrics,
        total_mapped=sum(s.metrics_mapped for s in scores),
        total_valid=sum(s.metrics_valid for s in scores),
        total_regressions=total_regressions,
        company_scores=company_scores,
        duration_seconds=duration,
        vetoed=False,
        regressed_metrics=all_regressed,
    )


# =============================================================================
# RESULT RECORDING & GOLDEN MASTER PROMOTION
# =============================================================================

def record_eval_results(
    all_results: Dict[str, Dict[str, MappingResult]],
    validation_results: Dict[str, dict],
    ledger,
) -> int:
    """
    Record valid extractions from auto-eval as ExtractionRun entries.

    This bridges the gap between auto-eval validation and the golden master
    promotion pipeline. Without ExtractionRun records, promote_golden_masters()
    has no data for expansion companies.
    """
    from edgar.xbrl.standardization.ledger.schema import ExtractionRun
    from edgar.xbrl.standardization.tools.auto_eval_loop import get_config_fingerprint
    from edgar.xbrl.standardization.config_loader import get_config

    fingerprint = get_config_fingerprint()
    config = get_config()
    recorded = 0

    for ticker, metrics in all_results.items():
        for metric, result in metrics.items():
            if result.validation_status != "valid":
                continue

            val = validation_results.get(ticker, {}).get(metric)
            fiscal_period = result.fiscal_period if result.fiscal_period else "unknown"

            # Look up metric-specific tolerance from config
            metric_config = config.get_metric(metric) if config else None
            tolerance = (metric_config.validation_tolerance
                         if metric_config and metric_config.validation_tolerance is not None
                         else 20.0)

            run = ExtractionRun(
                ticker=ticker,
                metric=metric,
                fiscal_period=fiscal_period,
                form_type="10-K",
                archetype=result.source.value,
                strategy_name=result.source.value,
                concept=result.concept,
                strategy_fingerprint=fingerprint,
                extracted_value=val.xbrl_value if val else None,
                reference_value=val.reference_value if val else None,
                variance_pct=val.variance_pct if val and val.variance_pct is not None else 0.0,
                is_valid=True,
                confidence=result.confidence,
                validation_tolerance=tolerance,
                reference_source=val.rfa_source if val else None,
                publish_confidence=val.publish_confidence if val else None,
                accession_number=val.accession_number if val else None,
                period_type=val.period_type if val else None,
                period_start=val.period_start if val else None,
                period_end=val.period_end if val else None,
                unit=val.unit if val else None,
                decimals=val.fact_decimals if val else None,
            )
            ledger.record_run(run)
            recorded += 1

    return recorded


# =============================================================================
# GAP ANALYSIS
# =============================================================================

def identify_gaps(
    eval_cohort: Optional[List[str]] = None,
    snapshot_mode: bool = True,
    use_ai: bool = False,
    ledger=None,
    max_graveyard: int = 3,
    max_workers: Optional[int] = None,
    config=None,
    use_sec_facts: bool = True,
) -> Tuple[List[MetricGap], CQSResult]:
    """
    Run evaluation and identify gaps ranked by CQS impact.

    Returns both the gaps and the CQS result so callers can use the
    baseline CQS for experiment decisions.

    Args:
        eval_cohort: Tickers to evaluate.
        snapshot_mode: Use cached snapshots.
        use_ai: Use AI mapping layer.
        ledger: ExperimentLedger for golden master + graveyard lookups.
        max_graveyard: Skip gaps with this many graveyard entries.
        max_workers: Number of parallel workers (1 = sequential, >1 = parallel).
        config: In-memory MappingConfig for parallel eval (None = load from disk).

    Returns:
        Tuple of (ranked gaps, CQS result).
    """
    from edgar.xbrl.standardization.orchestrator import Orchestrator
    from edgar.xbrl.standardization.ledger.schema import ExperimentLedger

    if eval_cohort is None:
        eval_cohort = QUICK_EVAL_COHORT

    if ledger is None:
        ledger = ExperimentLedger()

    # Run orchestrator ONCE — reuse results for both CQS computation and gap analysis
    workers = max_workers if max_workers is not None else DEFAULT_MAX_WORKERS
    start_time = time.time()
    orchestrator = Orchestrator(config=config, snapshot_mode=snapshot_mode, use_sec_facts=use_sec_facts)
    all_results = orchestrator.map_companies(
        tickers=eval_cohort, use_ai=use_ai, validate=True,
        max_workers=workers,
    )

    # Compute CQS from the orchestrator results directly
    golden_masters = ledger.get_all_golden_masters(active_only=True)
    golden_set = {(gm.ticker, gm.metric) for gm in golden_masters}

    company_scores: Dict[str, 'CompanyCQS'] = {}
    for ticker, metrics in all_results.items():
        company_scores[ticker] = _compute_company_cqs(
            ticker, metrics, golden_set, orchestrator.validation_results.get(ticker, {})
        )

    cqs_result = _aggregate_cqs(company_scores, None, time.time() - start_time)
    cqs_result.company_scores = company_scores
    logger.info(f"identify_gaps eval: {cqs_result.summary()}")

    # Get graveyard counts per metric
    graveyard_counts = _get_graveyard_counts(ledger)

    # Build gap list (reusing golden_set from CQS computation above)
    gaps: List[MetricGap] = []

    for ticker, metrics in all_results.items():
        validations = orchestrator.validation_results.get(ticker, {})
        company_total = sum(
            1 for r in metrics.values() if r.source != MappingSource.CONFIG
        )

        for metric, result in metrics.items():
            if result.source == MappingSource.CONFIG:
                continue

            gap = _classify_gap(
                ticker, metric, result, validations.get(metric),
                golden_set, company_total, graveyard_counts
            )
            if gap is not None:
                gaps.append(gap)

    # Sort by estimated impact (highest first), skip dead ends
    gaps.sort(key=lambda g: (-g.estimated_impact, g.graveyard_count))

    # Filter out dead ends
    active_gaps = [g for g in gaps if not g.is_dead_end]
    dead_ends = [g for g in gaps if g.is_dead_end]

    if dead_ends:
        logger.info(f"Skipping {len(dead_ends)} dead-end gaps (>={max_graveyard} graveyard entries)")

    return active_gaps, cqs_result


def derive_gaps_from_cqs(
    cqs_result: CQSResult,
    graveyard_counts: Dict[str, int],
) -> List[MetricGap]:
    """
    Derive gaps from an existing CQSResult without re-running the orchestrator.

    This is the fast path after a KEEP decision — we already have per-company
    scores and know which metrics failed. ~0s vs ~150s for identify_gaps().

    Args:
        cqs_result: CQSResult with company_scores populated.
        graveyard_counts: Dict of "ticker:metric" -> graveyard count.

    Returns:
        List of MetricGap, sorted by estimated impact (highest first).
    """
    gaps: List[MetricGap] = []

    for ticker, score in cqs_result.company_scores.items():
        company_total = max(score.metrics_total, 1)
        per_metric_impact = 0.50 / company_total

        for metric in score.failed_metrics:
            graveyard_key = f"{ticker}:{metric}"
            gc = graveyard_counts.get(graveyard_key, 0)

            gap = MetricGap(
                ticker=ticker,
                metric=metric,
                gap_type="validation_failure",  # Conservative default
                estimated_impact=per_metric_impact,
                graveyard_count=gc,
                reference_value=score.failed_metric_refs.get(metric),
                notes="Derived from CQSResult (fast path)",
            )
            if not gap.is_dead_end:
                gaps.append(gap)

    gaps.sort(key=lambda g: (-g.estimated_impact, g.graveyard_count))
    return gaps


def _build_extraction_evidence(
    ticker: str,
    metric: str,
    validation,
) -> ExtractionEvidence:
    """Build ExtractionEvidence from a ValidationResult."""
    if validation is None:
        return ExtractionEvidence(
            metric=metric, ticker=ticker,
            failure_reason="No validation result available",
        )

    return ExtractionEvidence(
        metric=metric,
        ticker=ticker,
        reference_value=validation.reference_value,
        extracted_value=validation.xbrl_value,
        resolution_type=getattr(validation, 'resolution_type', 'none'),
        components_used=getattr(validation, 'components_used', None) or [],
        components_missing=getattr(validation, 'components_missing', None) or [],
        variance_pct=validation.variance_pct,
        company_industry=getattr(validation, 'company_industry', None),
        failure_reason=validation.notes or "",
    )


def _determine_hv_subtype(evidence: ExtractionEvidence) -> Optional[str]:
    """Determine the high_variance subtype from extraction evidence."""
    # Composite metric with missing components
    if evidence.resolution_type == "composite" and evidence.components_missing:
        return "hv_missing_component"

    # Company has no industry set — may need industry-specific extraction
    if evidence.company_industry is None:
        return "hv_missing_industry"

    # Direct metric with wrong value — standard solver target
    if evidence.resolution_type == "direct" and evidence.extracted_value is not None:
        return "hv_wrong_concept"

    # Reference value suspiciously small or zero (possible bad ref data)
    if evidence.reference_value is not None and evidence.extracted_value is not None:
        if abs(evidence.reference_value) < 1.0:  # Less than $1 — likely bad ref data
            return "hv_reference_suspect"

    # Value extracted but from a resolution path that produced wrong result
    if evidence.extracted_value is not None:
        return "hv_wrong_concept"

    return None


def _classify_gap(
    ticker: str,
    metric: str,
    result: MappingResult,
    validation,
    golden_set: set,
    company_total: int,
    graveyard_counts: Dict[str, int],
) -> Optional[MetricGap]:
    """Classify a single metric gap and estimate its CQS impact."""
    # Impact of fixing one metric for one company on aggregate CQS
    # pass_rate weight = 0.50, and each metric contributes 1/total to pass_rate
    per_metric_impact = 0.50 / max(company_total, 1)

    graveyard_key = f"{ticker}:{metric}"
    gc = graveyard_counts.get(graveyard_key, 0)

    xbrl_val = None
    ref_val = None
    variance = None

    if validation:
        xbrl_val = validation.xbrl_value
        ref_val = validation.reference_value
        variance = validation.variance_pct

    # Build extraction evidence from validation result
    evidence = _build_extraction_evidence(ticker, metric, validation)

    # Regression: previously golden, now failing
    if (ticker, metric) in golden_set and result.validation_status == "invalid":
        return MetricGap(
            ticker=ticker, metric=metric, gap_type="regression",
            estimated_impact=per_metric_impact * 2,  # Higher priority
            current_variance=variance, reference_value=ref_val,
            xbrl_value=xbrl_val, graveyard_count=gc,
            notes="Golden master regressed — high priority",
            extraction_evidence=evidence,
            root_cause="regression",
        )

    # Validation failure: mapped but wrong value (or reset after validation failure)
    # Check validation_status before is_mapped — the orchestrator resets concept to None
    # on validation failure, so is_mapped becomes False but validation_status stays "invalid"
    if result.validation_status == "invalid":
        # Use RFA/SMA sub-scores to refine root cause routing
        rc = "wrong_concept"  # default
        notes = result.reasoning or f"Mapped to {result.concept} but failed validation"
        if validation:
            sma = validation.sma_pass
            rfa = validation.rfa_pass
            if sma is True and rfa is False:
                # Concept is semantically correct but value doesn't match —
                # likely needs a standardization formula or composite resolution
                rc = "formula_needed"
                notes += " [SMA pass, RFA fail → concept right, needs formula/composite]"
            elif sma is False and rfa is True:
                # Value matches but concept is wrong — algebraic coincidence
                rc = "algebraic_coincidence"
                notes += " [SMA fail, RFA pass → value matches by coincidence]"
            elif sma is False and rfa is False:
                # Both wrong — need full concept search
                rc = "missing_concept"
                notes += " [SMA fail, RFA fail → need concept search]"

        return MetricGap(
            ticker=ticker, metric=metric, gap_type="validation_failure",
            estimated_impact=per_metric_impact * 1.5,
            current_variance=variance, reference_value=ref_val,
            xbrl_value=xbrl_val, graveyard_count=gc,
            notes=notes,
            extraction_evidence=evidence,
            root_cause=rc,
        )

    # Unmapped: no concept found
    if not result.is_mapped:
        rc = "industry_structural" if ref_val is None else "missing_concept"
        return MetricGap(
            ticker=ticker, metric=metric, gap_type="unmapped",
            estimated_impact=per_metric_impact,
            reference_value=ref_val, graveyard_count=gc,
            notes="No mapping found",
            extraction_evidence=evidence,
            root_cause=rc,
        )

    # --- Sign and scale detection (before general high_variance) ---
    # Sign error: values match magnitude but opposite signs
    if (xbrl_val is not None and ref_val is not None
            and ref_val != 0 and xbrl_val != 0):
        if (xbrl_val > 0) != (ref_val > 0):
            magnitude_ratio = abs(xbrl_val) / abs(ref_val)
            if 0.8 < magnitude_ratio < 1.2:  # magnitudes match within 20%
                # If validation already passes (abs comparison), this is cosmetic —
                # _compare_values() uses abs() so sign-inverted metrics pass CQS.
                if result.validation_status == "valid":
                    return None  # Not a real gap — already passes CQS
                return MetricGap(
                    ticker=ticker, metric=metric, gap_type="high_variance",
                    estimated_impact=per_metric_impact * 1.2,
                    current_variance=variance, reference_value=ref_val,
                    xbrl_value=xbrl_val, graveyard_count=gc,
                    notes=f"Sign inverted: XBRL={xbrl_val:.0f}, ref={ref_val:.0f}",
                    extraction_evidence=evidence,
                    hv_subtype="hv_sign_inverted",
                    root_cause="sign_error",
                )

    # Scale mismatch: values differ by factor of 10/100/1000
    if (xbrl_val is not None and ref_val is not None
            and abs(ref_val) > 0 and abs(xbrl_val) > 0):
        ratio = abs(xbrl_val) / abs(ref_val)
        for scale in [1000, 100, 10, 0.001, 0.01, 0.1]:
            if 0.9 < (ratio / scale) < 1.1:  # within 10% of a round scale factor
                return MetricGap(
                    ticker=ticker, metric=metric, gap_type="high_variance",
                    estimated_impact=per_metric_impact * 1.0,
                    current_variance=variance, reference_value=ref_val,
                    xbrl_value=xbrl_val, graveyard_count=gc,
                    notes=f"Scale mismatch ~{scale}x: XBRL={xbrl_val:.0f}, ref={ref_val:.0f}",
                    extraction_evidence=evidence,
                    hv_subtype="hv_scale_mismatch",
                    root_cause="scale_mismatch",
                )

    # High variance: mapped and "valid" but variance is concerning
    if variance is not None and abs(variance) > 10:
        # Check if this is an explained variance (documented reason exists)
        vtype = "raw"
        if validation and hasattr(validation, 'variance_type'):
            vtype = validation.variance_type

        if vtype == "explained":
            return MetricGap(
                ticker=ticker, metric=metric, gap_type="explained_variance",
                estimated_impact=per_metric_impact * 0.1,  # Low priority — already understood
                current_variance=variance, reference_value=ref_val,
                xbrl_value=xbrl_val, graveyard_count=gc,
                notes=f"Explained variance {variance:.1f}% — documented reason exists",
                variance_type="explained",
                extraction_evidence=evidence,
                root_cause="explained_variance",
            )

        # Determine high_variance subtype for targeted proposal routing
        hv_subtype = _determine_hv_subtype(evidence)

        # Reference disputed: XBRL likely correct but yfinance disagrees
        if hv_subtype == "hv_reference_suspect":
            return MetricGap(
                ticker=ticker, metric=metric, gap_type="reference_disputed",
                estimated_impact=per_metric_impact * 0.1,  # Low priority -- likely correct
                current_variance=variance, reference_value=ref_val,
                xbrl_value=xbrl_val, graveyard_count=gc,
                notes=f"Reference suspect: yfinance ref={ref_val} may be stale",
                extraction_evidence=evidence,
                hv_subtype="hv_reference_suspect",
                root_cause="reference_error",
            )

        # Map hv_subtype to root_cause
        HV_ROOT_CAUSE_MAP = {
            "hv_missing_component": "partial_composite",
            "hv_missing_industry": "sector_specific",
            "hv_wrong_concept": "wrong_concept",
            "hv_reference_suspect": "reference_error",
        }
        rc = HV_ROOT_CAUSE_MAP.get(hv_subtype, "wrong_concept") if hv_subtype else "wrong_concept"

        return MetricGap(
            ticker=ticker, metric=metric, gap_type="high_variance",
            estimated_impact=per_metric_impact * 0.5,
            current_variance=variance, reference_value=ref_val,
            xbrl_value=xbrl_val, graveyard_count=gc,
            notes=f"Variance {variance:.1f}% is above 10% threshold",
            variance_type=vtype,
            extraction_evidence=evidence,
            hv_subtype=hv_subtype,
            root_cause=rc,
        )

    return None


def _get_graveyard_counts(ledger) -> Dict[str, int]:
    """Get graveyard failure counts per ticker:metric key."""
    counts: Dict[str, int] = {}
    try:
        entries = ledger.get_graveyard_entries()
        for entry in entries:
            key = f"{entry.get('target_companies', '')}:{entry.get('target_metric', '')}"
            counts[key] = counts.get(key, 0) + 1
    except Exception as e:
        logger.warning(f"Failed to read graveyard counts: {e}")
    return counts


# =============================================================================
# PRINTING / REPORTING
# =============================================================================

def print_cqs_report(result: CQSResult):
    """Print a formatted CQS report to console."""
    print()
    print("=" * 70)
    print("EXTRACTION QUALITY REPORT")
    print("=" * 70)

    veto_str = " ** HARD VETO — REGRESSIONS DETECTED **" if result.vetoed else ""
    # EF-CQS is the headline metric
    ef_status = "PASS" if result.ef_cqs >= 0.95 else "BELOW TARGET"
    print(f"\n  EF-CQS (Extraction Fidelity):  {result.ef_cqs:.4f}  [{ef_status}]{veto_str}")
    print(f"  RFA Rate (Reported Fact):       {result.rfa_rate:.4f}")
    print(f"  SMA Rate (Semantic Mapping):    {result.sma_rate:.4f}")
    print(f"  SA-CQS (Standardization):       {result.sa_cqs:.4f}")
    print(f"  CQS (composite):                {result.cqs:.4f}")
    headline_status = "PASS" if result.headline_ef_rate >= 0.99 else "BELOW TARGET"
    print(f"  Headline EF Rate:               {result.headline_ef_rate:.4f}  [{headline_status}]")
    print()

    print("  Sub-metrics:")
    print(f"    Pass Rate:          {result.pass_rate:.1%}  (weight: 0.45)")
    print(f"    Mean Variance:      {result.mean_variance:.1f}%  (weight: 0.20, inverted)")
    print(f"    Coverage Rate:      {result.coverage_rate:.1%}  (weight: 0.15)")
    print(f"    Stability Rate:     {result.golden_master_rate:.1%}  (weight: 0.15)")
    print(f"    Regression Rate:    {result.regression_rate:.1%}  (weight: 0.05, inverted)")
    print()
    print(f"    EF Pass Rate:       {result.ef_pass_rate:.1%}")
    print(f"    SA Pass Rate:       {result.sa_pass_rate:.1%}")
    print(f"    RFA Rate:           {result.rfa_rate:.1%}")
    print(f"    SMA Rate:           {result.sma_rate:.1%}")
    print(f"    Explained Gaps:     {result.explained_variance_count}")
    print()

    print("  Totals:")
    print(f"    Companies:    {result.companies_evaluated}")
    print(f"    Metrics:      {result.total_metrics}")
    print(f"    Mapped:       {result.total_mapped}")
    print(f"    Valid:        {result.total_valid}")
    print(f"    Regressions:  {result.total_regressions}")
    print(f"    Duration:     {result.duration_seconds:.1f}s")

    if result.company_scores:
        print()
        print("  Per-Company Breakdown:")
        print(f"    {'Ticker':<8} {'EF':>6} {'RFA':>6} {'SMA':>6} {'Pass':>6} {'Cov':>6} {'Var%':>6} {'Reg':>4}")
        print("    " + "-" * 56)
        for ticker in sorted(result.company_scores.keys()):
            cs = result.company_scores[ticker]
            print(
                f"    {ticker:<8} {cs.ef_cqs:>5.1%} {cs.rfa_pass_rate:>5.1%} {cs.sma_pass_rate:>5.1%} "
                f"{cs.pass_rate:>5.1%} {cs.coverage_rate:>5.1%} "
                f"{cs.mean_variance:>5.1f} {cs.regression_count:>4d}"
            )

    print("=" * 70)
    print()


def check_offline_readiness(eval_cohort: Optional[List[str]] = None) -> bool:
    """
    Quick check that the eval cohort has local data available.

    Returns True if all companies have at least one local 10-K filing.
    Prints a warning for any companies missing local data.
    """
    from edgar.xbrl.standardization.tools.bulk_preload import verify_offline_readiness

    if eval_cohort is None:
        eval_cohort = QUICK_EVAL_COHORT

    readiness = verify_offline_readiness(eval_cohort)

    if not readiness['overall_ready']:
        missing = [
            ticker for ticker, status in readiness['tickers'].items()
            if not status.get('ready', False)
        ]
        logger.warning(
            f"Offline data missing for: {', '.join(missing)}. "
            f"Run bulk_preload.preload_cohort() to download."
        )

    return readiness['overall_ready']


def print_gap_report(gaps: List[MetricGap], limit: int = 20):
    """Print a formatted gap analysis report."""
    print()
    print("=" * 70)
    print(f"GAP ANALYSIS — Top {min(limit, len(gaps))} opportunities")
    print("=" * 70)

    if not gaps:
        print("  No gaps found — pipeline is at full quality!")
        return

    print(f"  Total gaps: {len(gaps)}")
    print()
    print(f"  {'#':>3} {'Ticker':<8} {'Metric':<28} {'Type':<18} {'Impact':>7} {'GY':>3}")
    print("  " + "-" * 70)

    for i, gap in enumerate(gaps[:limit], 1):
        print(
            f"  {i:>3} {gap.ticker:<8} {gap.metric:<28} "
            f"{gap.gap_type:<18} {gap.estimated_impact:>7.4f} {gap.graveyard_count:>3}"
        )
        if gap.notes:
            print(f"      {gap.notes}")

    print("=" * 70)
    print()
