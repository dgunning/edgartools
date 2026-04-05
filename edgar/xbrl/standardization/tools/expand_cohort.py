"""Inner loop for expansion pipeline: onboard, measure, fix, report.

Coordinates the company onboarding workflow:
1. Onboard companies via onboard_company
2. Measure quality via compute_cqs
3. Diagnose gaps and apply deterministic fixes
4. Generate cohort report
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from edgar.xbrl.standardization.config_loader import get_industry_sic_ranges
from edgar.xbrl.standardization.tools.config_applier import apply_action_to_json
from edgar.xbrl.standardization.tools.report_generator import (
    CohortReportData,
    CompanyResult,
    AppliedFix,
    UnresolvedGapEntry,
    generate_cohort_report,
    write_evidence_sidecar,
)

log = logging.getLogger(__name__)

_DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "cohort-reports"


def run_expand_cohort(
    tickers: List[str],
    cohort_name: str,
    output_dir: Optional[Path] = None,
    config_dir: Optional[Path] = None,
    dry_run: bool = False,
) -> Path:
    """Run the inner loop for a cohort of companies.

    Args:
        tickers: Company tickers to onboard.
        cohort_name: Name for this cohort (used in report filename).
        output_dir: Where to write cohort report (default: cohort-reports/).
        config_dir: Config directory override (for testing).
        dry_run: If True, skip actual SEC/yfinance calls.

    Returns:
        Path to the generated cohort report markdown file.
    """
    if output_dir is None:
        output_dir = _DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.utcnow()

    # Step 1: Onboard
    onboard_results = _onboard_single(tickers, dry_run=dry_run)

    # Step 2: Measure
    successful_tickers = [t for t, r in onboard_results.items() if r.error is None]
    company_scores = _measure_cohort(successful_tickers, config_dir=config_dir)

    # Step 3: Diagnose and fix
    fixes, unresolved = _diagnose_and_fix(
        successful_tickers, company_scores, config_dir=config_dir
    )

    # Step 4: Build report
    companies = []
    for ticker, result in onboard_results.items():
        if result.error:
            companies.append(CompanyResult(
                ticker=ticker,
                ef_cqs=0.0,
                status="failed",
                gaps_remaining=0,
                notes=f"Onboarding error: {result.error}",
            ))
            continue

        score = company_scores.get(ticker)
        ef_cqs = score.ef_cqs if score else 0.0
        gaps = sum(1 for u in unresolved if u.ticker == ticker)

        status = "graduated" if ef_cqs >= 0.80 else "needs_investigation"
        companies.append(CompanyResult(
            ticker=ticker,
            ef_cqs=ef_cqs,
            status=status,
            gaps_remaining=gaps,
            notes="",
        ))

    date_str = now.strftime('%Y-%m-%d')
    report_data = CohortReportData(
        name=f"{cohort_name}-{date_str}",
        status="inner_loop_complete",
        companies=companies,
        fixes=[AppliedFix(
            ticker=f["ticker"],
            metric=f["metric"],
            action=f["action"],
            confidence=f.get("confidence", 1.0),
            detail=f.get("detail", ""),
        ) for f in fixes],
        unresolved=unresolved,
    )

    md = generate_cohort_report(report_data)
    report_path = output_dir / f"cohort-{date_str}-{cohort_name}.md"
    report_path.write_text(md)

    write_evidence_sidecar(report_path, report_data.name, unresolved)

    log.info(f"Cohort report written to {report_path}")
    return report_path


def _onboard_single(
    tickers: List[str],
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Onboard companies. Returns dict of ticker -> OnboardingResult."""
    from edgar.xbrl.standardization.tools.onboard_company import (
        onboard_company,
        OnboardingResult,
    )

    results = {}
    for ticker in tickers:
        try:
            result = onboard_company(ticker, dry_run=dry_run)
            results[ticker] = result
        except Exception as e:
            log.error(f"Failed to onboard {ticker}: {e}")
            # Create a minimal error result
            results[ticker] = OnboardingResult(
                ticker=ticker,
                cik=0,
                company_name="",
                archetype="A",
                error=str(e),
            )
    return results


def _measure_cohort(
    tickers: List[str],
    config_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Measure EF-CQS for a cohort. Returns dict of ticker -> company score."""
    if not tickers:
        return {}

    from edgar.xbrl.standardization.tools.auto_eval import compute_cqs

    kwargs: Dict[str, Any] = {"eval_cohort": tickers, "snapshot_mode": True}
    if config_dir:
        from edgar.xbrl.standardization.config_loader import ConfigLoader
        kwargs["config"] = ConfigLoader(config_dir=config_dir).load()

    cqs_result = compute_cqs(**kwargs)
    return cqs_result.company_scores


def _diagnose_and_fix(
    tickers: List[str],
    company_scores: Dict[str, Any],
    config_dir: Optional[Path] = None,
) -> Tuple[List[Dict], List[UnresolvedGapEntry]]:
    """Diagnose gaps and apply deterministic fixes.

    Returns:
        Tuple of (applied_fixes, unresolved_gaps)
    """
    if not tickers:
        return [], []

    from edgar.xbrl.standardization.tools.auto_eval import identify_gaps

    kwargs: Dict[str, Any] = {"eval_cohort": tickers, "snapshot_mode": True}
    if config_dir:
        from edgar.xbrl.standardization.config_loader import ConfigLoader
        kwargs["config"] = ConfigLoader(config_dir=config_dir).load()

    gaps, _ = identify_gaps(**kwargs)

    applied_fixes: List[Dict] = []
    unresolved: List[UnresolvedGapEntry] = []

    for gap in gaps:
        # Try deterministic fixes based on gap type
        fix = _try_deterministic_fix(gap)
        if fix:
            apply_action_to_json(fix, **({"config_dir": config_dir} if config_dir else {}))
            applied_fixes.append(fix)
        else:
            ev = gap.extraction_evidence
            unresolved.append(UnresolvedGapEntry(
                ticker=gap.ticker,
                metric=gap.metric,
                gap_type=gap.gap_type,
                variance=gap.current_variance,
                root_cause=gap.root_cause or "unknown",
                graveyard=gap.graveyard_count,
                reference_value=getattr(gap, 'reference_value', None),
                xbrl_value=getattr(gap, 'xbrl_value', None),
                components_found=len(ev.components_used) if ev else 0,
                components_needed=(len(ev.components_used) + len(ev.components_missing)) if ev else 0,
            ))

    return applied_fixes, unresolved


def _try_deterministic_fix(gap) -> Optional[Dict]:
    """Attempt a deterministic fix for a gap. Returns action dict or None.

    Only the two safest gap types are auto-fixed; all others escalate to
    the outer loop (investigate-gaps).

    Safe cases:
    1. Sign errors — XBRL value is an exact negation of the reference value.
       Unambiguous: ratio is within 5% of -1.0.
    2. Concept absent — unmapped gap with no extraction evidence components.
       The metric simply doesn't exist for this company/industry.
    """
    # 1. Sign errors: exact negation is unambiguous
    if gap.root_cause == "sign_error":
        ref = gap.reference_value
        xbrl = gap.xbrl_value
        if ref is not None and xbrl is not None and ref != 0:
            ratio = xbrl / ref
            if abs(ratio + 1.0) < 0.05:  # within 5% of exact negation
                return {
                    "action": "FIX_SIGN_CONVENTION",
                    "ticker": gap.ticker,
                    "metric": gap.metric,
                    "params": {},
                    "confidence": 0.98,
                    "detail": f"Auto-fixed sign inversion (ratio={ratio:.3f})",
                }

    # 2. Concept absent: unmapped + no extraction evidence = metric doesn't apply
    if (gap.root_cause in ("missing_concept", "industry_structural")
            and gap.gap_type == "unmapped"
            and gap.extraction_evidence is not None
            and not gap.extraction_evidence.components_used):
        return {
            "action": "EXCLUDE_METRIC",
            "ticker": gap.ticker,
            "metric": gap.metric,
            "params": {"reason": "not_applicable", "notes": "Auto-excluded: concept absent from all XBRL sources"},
            "confidence": 0.95,
            "detail": "Concept not found in calc tree, facts, or element index",
        }

    return None


def detect_archetype_gaps(company_infos: List[Dict]) -> Dict[str, str]:
    """Amendment 3: Flag companies without matching industry_metrics.yaml section.

    Args:
        company_infos: List of dicts with keys: ticker, sic_code, archetype

    Returns:
        Dict of ticker -> reason string for companies with no industry coverage.
    """
    industry_sic_ranges = get_industry_sic_ranges()
    flagged: Dict[str, str] = {}

    for info in company_infos:
        ticker = info["ticker"]
        sic_code = info.get("sic_code")

        if not sic_code:
            flagged[ticker] = "No SIC code available"
            continue

        try:
            sic_int = int(sic_code)
        except (ValueError, TypeError):
            flagged[ticker] = f"Invalid SIC code: {sic_code}"
            continue

        covered = False
        for industry, ranges in industry_sic_ranges.items():
            for low, high in ranges:
                if low <= sic_int <= high:
                    covered = True
                    break
            if covered:
                break

        if not covered:
            flagged[ticker] = f"SIC {sic_code} not covered by any industry_metrics.yaml section"

    return flagged

