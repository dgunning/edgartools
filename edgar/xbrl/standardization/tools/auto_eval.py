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

    def to_dict(self) -> dict:
        return asdict(self)


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
    gap_type: str              # "unmapped" | "validation_failure" | "high_variance" | "regression" | "explained_variance"
    estimated_impact: float    # Estimated CQS improvement if resolved [0-1]
    current_variance: Optional[float] = None
    reference_value: Optional[float] = None
    xbrl_value: Optional[float] = None
    graveyard_count: int = 0   # Number of prior failed attempts
    notes: str = ""
    variance_type: str = "raw" # "raw" | "explained" | "standardized"
    extraction_evidence: Optional[ExtractionEvidence] = None  # Diagnostic evidence from validator
    hv_subtype: Optional[str] = None  # "hv_missing_component" | "hv_wrong_concept" | "hv_missing_industry" | "hv_period_mismatch"

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

    # Per-company breakdown
    company_scores: Dict[str, CompanyCQS] = field(default_factory=dict)

    # Timing
    duration_seconds: float = 0.0

    # Whether regressions triggered hard veto
    vetoed: bool = False

    # Per-company timing breakdown
    timing: Optional[TimingBreakdown] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d['company_scores'] = {k: v.to_dict() if isinstance(v, CompanyCQS) else v
                               for k, v in self.company_scores.items()}
        return d

    def summary(self) -> str:
        """One-line summary."""
        veto = " [VETOED]" if self.vetoed else ""
        return (
            f"CQS={self.cqs:.4f}{veto} | "
            f"EF={self.ef_cqs:.4f} SA={self.sa_cqs:.4f} | "
            f"pass={self.pass_rate:.1%} var={self.mean_variance:.1f}% "
            f"cov={self.coverage_rate:.1%} golden={self.golden_master_rate:.1%} "
            f"regress={self.total_regressions} | "
            f"{self.companies_evaluated} cos, {self.duration_seconds:.1f}s"
        )


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
    orchestrator = Orchestrator(config=config, snapshot_mode=snapshot_mode)
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
        promoted = ledger.promote_golden_masters(min_periods=1)
        logger.info(f"Recorded {count} extraction runs, promoted {len(promoted)} golden masters")

    logger.info(f"Auto-eval complete: {result.summary()}")
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
    ef_pass_count = 0
    sa_pass_count = 0
    explained_variance_count = 0

    for metric, result in metrics.items():
        if result.source == MappingSource.CONFIG:
            excluded += 1
            continue

        total += 1

        if result.is_mapped:
            mapped += 1

        # Check validation status
        if result.validation_status == "valid":
            valid += 1
        elif result.validation_status == "invalid":
            # A previously golden metric that now fails = regression
            if (ticker, metric) in golden_set:
                regression_count += 1

        # Collect variance and EF/SA from validation results
        val_result = validations.get(metric)
        if val_result and val_result.variance_pct is not None:
            variances.append(abs(val_result.variance_pct))

        # EF/SA scoring from validation results
        if val_result:
            if val_result.ef_pass:
                ef_pass_count += 1
            if val_result.sa_pass:
                sa_pass_count += 1
            if val_result.variance_type == "explained":
                explained_variance_count += 1
        elif result.is_mapped:
            # No validation result but mapped = EF pass
            ef_pass_count += 1

        # Check golden master status
        if (ticker, metric) in golden_set:
            golden_count += 1

    # Compute sub-metrics
    pass_rate = valid / total if total > 0 else 0.0
    mean_variance = sum(variances) / len(variances) if variances else 0.0
    coverage_rate = mapped / total if total > 0 else 0.0
    golden_master_rate = golden_count / total if total > 0 else 0.0
    ef_pass_rate = ef_pass_count / total if total > 0 else 0.0
    sa_pass_rate = sa_pass_count / total if total > 0 else 0.0

    # Per-company CQS (same formula as aggregate)
    cqs = (
        0.50 * pass_rate
        + 0.20 * max(0, 1 - mean_variance / 100)
        + 0.15 * coverage_rate
        + 0.10 * golden_master_rate
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

    # Aggregate EF/SA scores
    ef_pass_rate = sum(s.ef_pass_rate for s in scores) / n
    sa_pass_rate = sum(s.sa_pass_rate for s in scores) / n
    explained_variance_count = sum(s.explained_variance_count for s in scores)

    # Compute composite CQS
    raw_cqs = (
        0.50 * pass_rate
        + 0.20 * max(0, 1 - mean_variance / 100)
        + 0.15 * coverage_rate
        + 0.10 * golden_master_rate
        + 0.05 * (1 - regression_rate)
    )

    # EF-CQS and SA-CQS (simple averages across companies)
    ef_cqs = sum(s.ef_cqs for s in scores) / n
    sa_cqs = sum(s.sa_cqs for s in scores) / n

    # HARD VETO: regressions cap CQS below baseline
    vetoed = False
    if total_regressions > 0 and baseline_cqs is not None:
        raw_cqs = baseline_cqs - 0.01
        vetoed = True

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
        companies_evaluated=n,
        total_metrics=total_metrics,
        total_mapped=sum(s.metrics_mapped for s in scores),
        total_valid=sum(s.metrics_valid for s in scores),
        total_regressions=total_regressions,
        company_scores=company_scores,
        duration_seconds=duration,
        vetoed=vetoed,
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

    fingerprint = get_config_fingerprint()
    recorded = 0

    for ticker, metrics in all_results.items():
        for metric, result in metrics.items():
            if result.validation_status != "valid":
                continue

            val = validation_results.get(ticker, {}).get(metric)
            fiscal_period = result.fiscal_period if result.fiscal_period else "unknown"

            run = ExtractionRun(
                ticker=ticker,
                metric=metric,
                fiscal_period=fiscal_period,
                form_type="10-K",
                archetype=result.source.value,
                strategy_name=result.source.value,
                strategy_fingerprint=fingerprint,
                extracted_value=val.xbrl_value if val else None,
                reference_value=val.reference_value if val else None,
                variance_pct=val.variance_pct if val and val.variance_pct is not None else 0.0,
                is_valid=True,
                confidence=result.confidence,
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
    orchestrator = Orchestrator(config=config, snapshot_mode=snapshot_mode)
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
        )

    # Validation failure: mapped but wrong value (or reset after validation failure)
    # Check validation_status before is_mapped — the orchestrator resets concept to None
    # on validation failure, so is_mapped becomes False but validation_status stays "invalid"
    if result.validation_status == "invalid":
        return MetricGap(
            ticker=ticker, metric=metric, gap_type="validation_failure",
            estimated_impact=per_metric_impact * 1.5,
            current_variance=variance, reference_value=ref_val,
            xbrl_value=xbrl_val, graveyard_count=gc,
            notes=result.reasoning or f"Mapped to {result.concept} but failed validation",
            extraction_evidence=evidence,
        )

    # Unmapped: no concept found
    if not result.is_mapped:
        return MetricGap(
            ticker=ticker, metric=metric, gap_type="unmapped",
            estimated_impact=per_metric_impact,
            reference_value=ref_val, graveyard_count=gc,
            notes="No mapping found",
            extraction_evidence=evidence,
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
            )

        # Determine high_variance subtype for targeted proposal routing
        hv_subtype = _determine_hv_subtype(evidence)

        return MetricGap(
            ticker=ticker, metric=metric, gap_type="high_variance",
            estimated_impact=per_metric_impact * 0.5,
            current_variance=variance, reference_value=ref_val,
            xbrl_value=xbrl_val, graveyard_count=gc,
            notes=f"Variance {variance:.1f}% is above 10% threshold",
            variance_type=vtype,
            extraction_evidence=evidence,
            hv_subtype=hv_subtype,
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
    print("COMPOSITE QUALITY SCORE (CQS) REPORT")
    print("=" * 70)

    veto_str = " ** HARD VETO — REGRESSIONS DETECTED **" if result.vetoed else ""
    print(f"\n  CQS: {result.cqs:.4f}{veto_str}")
    print(f"  EF-CQS (Extraction Fidelity):       {result.ef_cqs:.4f}")
    print(f"  SA-CQS (Standardization Alignment):  {result.sa_cqs:.4f}")
    print()

    print("  Sub-metrics:")
    print(f"    Pass Rate:          {result.pass_rate:.1%}  (weight: 0.50)")
    print(f"    Mean Variance:      {result.mean_variance:.1f}%  (weight: 0.20, inverted)")
    print(f"    Coverage Rate:      {result.coverage_rate:.1%}  (weight: 0.15)")
    print(f"    Golden Master Rate: {result.golden_master_rate:.1%}  (weight: 0.10)")
    print(f"    Regression Rate:    {result.regression_rate:.1%}  (weight: 0.05, inverted)")
    print()
    print(f"    EF Pass Rate:       {result.ef_pass_rate:.1%}")
    print(f"    SA Pass Rate:       {result.sa_pass_rate:.1%}")
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
        print(f"    {'Ticker':<8} {'CQS':>6} {'EF':>6} {'SA':>6} {'Pass':>6} {'Cov':>6} {'Var%':>6} {'Reg':>4}")
        print("    " + "-" * 56)
        for ticker in sorted(result.company_scores.keys()):
            cs = result.company_scores[ticker]
            print(
                f"    {ticker:<8} {cs.cqs:>6.3f} {cs.ef_cqs:>5.1%} {cs.sa_cqs:>5.1%} "
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
