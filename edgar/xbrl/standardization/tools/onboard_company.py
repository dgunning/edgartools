#!/usr/bin/env python3
"""
Automated Company Onboarding Pipeline for S&P 100 Expansion.

Takes a ticker and produces:
1. A draft companies.yaml fragment (ready to paste)
2. A JSON validation report in config/onboarding_reports/

Usage:
    # Single company
    python -m edgar.xbrl.standardization.tools.onboard_company HD

    # Batch
    python -m edgar.xbrl.standardization.tools.onboard_company --tickers HD,V,ABBV,MCD,LOW

    # Dry run (no snapshot download, no extraction)
    python -m edgar.xbrl.standardization.tools.onboard_company --dry-run HD

    # Skip AI layer (faster, static-only mapping)
    python -m edgar.xbrl.standardization.tools.onboard_company --no-ai HD
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from edgar import Company, set_identity, use_local_storage
from edgar.xbrl.standardization.archetypes.definitions import (
    AccountingArchetype,
    ARCHETYPE_DEFINITIONS,
)
from edgar.xbrl.standardization.config_loader import get_config
from edgar.xbrl.standardization.models import MappingSource
from edgar.xbrl.standardization.orchestrator import Orchestrator
from edgar.xbrl.standardization.yf_snapshot import (
    SNAPSHOT_DIR,
    fetch_and_save_snapshot,
    load_snapshot,
)

from edgar.xbrl.standardization.ledger.schema import ExperimentLedger, ExtractionRun

REPORT_DIR = Path(__file__).parent.parent / "config" / "onboarding_reports"


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class FailureDetail:
    """Detail about a single metric failure during onboarding."""
    metric: str
    reason: str
    xbrl_value: Optional[float] = None
    reference_value: Optional[float] = None
    variance_pct: Optional[float] = None
    pattern: str = "unknown"  # dimensional, structural, period_mismatch, extraction_error


@dataclass
class OnboardingResult:
    """Complete result of onboarding a single company."""
    ticker: str
    cik: int
    company_name: str
    archetype: str
    sic_code: Optional[str] = None
    fiscal_year_end: str = "December"
    draft_yaml: str = ""
    metrics_passed: List[str] = field(default_factory=list)
    metrics_failed: List[str] = field(default_factory=list)
    metrics_excluded: List[str] = field(default_factory=list)
    failures: Dict[str, FailureDetail] = field(default_factory=dict)
    remediation_complexity: str = "clean"  # "clean" | "needs_review" | "structural"
    snapshot_created: bool = False
    extraction_ran: bool = False
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        """Serialize for JSON output."""
        d = asdict(self)
        return d

    @property
    def pass_rate(self) -> float:
        total = len(self.metrics_passed) + len(self.metrics_failed)
        if total == 0:
            return 0.0
        return len(self.metrics_passed) / total * 100

    @property
    def summary_line(self) -> str:
        total = len(self.metrics_passed) + len(self.metrics_failed)
        return (
            f"{self.ticker}: {len(self.metrics_passed)}/{total} passed "
            f"({self.pass_rate:.0f}%) — archetype {self.archetype} — {self.remediation_complexity}"
        )


# =============================================================================
# ARCHETYPE DETECTION
# =============================================================================

def detect_archetype(sic_code: Optional[str]) -> str:
    """Detect accounting archetype from SIC code using ARCHETYPE_DEFINITIONS.

    Uses narrowest-match-first strategy: checks specific archetypes (B, C, D, E)
    before the broad Archetype A, since A's SIC ranges overlap with others.

    Returns archetype letter (A, B, C, D, E) or 'A' as default.
    """
    if not sic_code:
        return "A"

    try:
        sic_int = int(sic_code)
    except (ValueError, TypeError):
        return "A"

    # Check specific archetypes first (B, C, D, E) before the broad A
    # Archetype A has wide SIC ranges (1000-5999) that overlap with more
    # specific ranges in other archetypes (e.g., pharma 2833-2836 in C).
    check_order = [
        AccountingArchetype.B,
        AccountingArchetype.C,
        AccountingArchetype.D,
        AccountingArchetype.E,
        AccountingArchetype.A,
    ]

    for archetype in check_order:
        defn = ARCHETYPE_DEFINITIONS.get(archetype, {})
        for start, end in defn.get("sic_ranges", []):
            if start <= sic_int <= end:
                return archetype.name

    return "A"


def get_archetype_excluded_metrics(archetype_letter: str) -> List[str]:
    """Get default excluded metrics for an archetype letter."""
    for arch_enum, defn in ARCHETYPE_DEFINITIONS.items():
        if arch_enum.name == archetype_letter:
            return defn.get("excluded_metrics", [])
    return []


# =============================================================================
# FISCAL YEAR END DETECTION
# =============================================================================

def detect_fiscal_year_end(company: Company) -> str:
    """Detect fiscal year end month from company's latest 10-K filing date."""
    try:
        filings = company.get_filings(form="10-K", amendments=False)
        for f in filings:
            # The period_of_report is the fiscal year end date
            report_date = getattr(f, 'period_of_report', None)
            if report_date:
                # report_date is typically a string like "2024-12-31"
                date_str = str(report_date)
                if "-" in date_str:
                    month = int(date_str.split("-")[1])
                    month_names = [
                        "January", "February", "March", "April",
                        "May", "June", "July", "August",
                        "September", "October", "November", "December",
                    ]
                    return month_names[month - 1]
            break
    except Exception:
        pass
    return "December"


# =============================================================================
# YAML GENERATION
# =============================================================================

def generate_yaml_fragment(result: OnboardingResult) -> str:
    """Generate a companies.yaml fragment for a company."""
    lines = []
    lines.append(f"  {result.ticker}:")
    lines.append(f'    name: "{result.company_name}"')
    lines.append(f"    cik: {result.cik}")

    if result.fiscal_year_end != "December":
        lines.append(f'    fiscal_year_end: "{result.fiscal_year_end}"')

    # Exclude metrics (archetype-driven + failed structural)
    all_excludes = set(result.metrics_excluded)
    for metric, detail in result.failures.items():
        if detail.pattern == "structural":
            all_excludes.add(metric)

    if all_excludes:
        lines.append("    exclude_metrics:")
        for m in sorted(all_excludes):
            lines.append(f"      - {m}")

    # Known divergences for metrics with >20% variance but not structural
    divergences = {}
    for metric, detail in result.failures.items():
        if detail.pattern != "structural" and detail.variance_pct is not None:
            if detail.variance_pct > 20.0:
                divergences[metric] = detail

    if divergences:
        lines.append("    known_divergences:")
        for metric in sorted(divergences):
            detail = divergences[metric]
            lines.append(f"      {metric}:")
            lines.append(f'        form_types: ["10-K"]')
            var = detail.variance_pct or 0
            lines.append(f"        variance_pct: {var:.1f}")
            reason = detail.reason.replace('"', '\\"')
            lines.append(f'        reason: "{reason}"')
            lines.append("        skip_validation: true")
            lines.append(f'        added_date: "{datetime.utcnow().strftime("%Y-%m-%d")}"')

    return "\n".join(lines)


# =============================================================================
# FAILURE CLASSIFICATION
# =============================================================================

def classify_failure(
    metric: str,
    validation_result,
) -> FailureDetail:
    """Classify a validation failure into a known pattern."""
    status = getattr(validation_result, "status", "unknown")
    xbrl_val = getattr(validation_result, "xbrl_value", None)
    ref_val = getattr(validation_result, "reference_value", None)
    variance = getattr(validation_result, "variance_pct", None)
    notes = getattr(validation_result, "notes", "") or ""

    # Determine pattern
    if "dimension" in notes.lower():
        pattern = "dimensional"
        reason = "Values exist only with dimensions"
    elif xbrl_val is None and ref_val is not None:
        pattern = "extraction_error"
        reason = "No XBRL value extracted but reference exists"
    elif "period" in notes.lower() or "ytd" in notes.lower():
        pattern = "period_mismatch"
        reason = "Period mismatch between XBRL and reference"
    elif variance is not None and variance > 100:
        pattern = "structural"
        reason = f"Structural divergence ({variance:.0f}% variance)"
    else:
        pattern = "unknown"
        reason = notes or f"Validation failed: {status}"

    return FailureDetail(
        metric=metric,
        reason=reason,
        xbrl_value=xbrl_val,
        reference_value=ref_val,
        variance_pct=variance,
        pattern=pattern,
    )


# =============================================================================
# EXTRACTION RUN RECORDING
# =============================================================================

def _record_extraction_runs(
    result: OnboardingResult,
    mapping_results: Dict,
    validation_results: Dict,
    ledger: ExperimentLedger,
) -> int:
    """Write one ExtractionRun per metric to the ledger.

    Args:
        result: Completed OnboardingResult.
        mapping_results: Dict of metric -> MappingResult from orchestrator.
        validation_results: Dict of metric -> ValidationResult from validator.
        ledger: ExperimentLedger to record into.

    Returns:
        Number of runs recorded.
    """
    count = 0
    for metric, mapping in mapping_results.items():
        if mapping.source == MappingSource.CONFIG:
            continue

        vr = validation_results.get(metric)
        extracted_value = getattr(vr, 'xbrl_value', None) if vr else None
        reference_value = getattr(vr, 'reference_value', None) if vr else None

        run = ExtractionRun(
            ticker=result.ticker,
            metric=metric,
            fiscal_period="latest",
            form_type="10-K",
            archetype=result.archetype,
            strategy_name=mapping.source.value,
            strategy_fingerprint="",
            extracted_value=extracted_value,
            reference_value=reference_value,
            confidence=mapping.confidence,
        )
        try:
            ledger.record_run(run)
            count += 1
        except Exception:
            pass

    return count


# =============================================================================
# ONBOARDING PIPELINE
# =============================================================================

def onboard_company(
    ticker: str,
    use_ai: bool = True,
    dry_run: bool = False,
    snapshot_mode: bool = True,
) -> OnboardingResult:
    """Run the full onboarding pipeline for a single company.

    Steps:
    1. Resolve CIK and company metadata
    2. Detect archetype from SIC code
    3. Generate yfinance snapshot (idempotent)
    4. Run Orchestrator with all layers
    5. Collect validation results
    6. Classify failures
    7. Generate draft YAML fragment

    Args:
        ticker: Company ticker symbol
        use_ai: Whether to use Layer 3 AI mapping
        dry_run: If True, only resolve metadata (no extraction)
        snapshot_mode: Use pinned snapshots for determinism

    Returns:
        OnboardingResult with all details
    """
    ticker = ticker.upper()
    set_identity("Dev Gunning developer-gunning@gmail.com")
    use_local_storage(True)

    print(f"\n{'='*60}")
    print(f"ONBOARDING: {ticker}")
    print(f"{'='*60}")

    # Step 1: Resolve company metadata
    try:
        company = Company(ticker)
    except Exception as e:
        return OnboardingResult(
            ticker=ticker,
            cik=0,
            company_name="UNKNOWN",
            archetype="A",
            error=f"Could not resolve company: {e}",
        )

    cik = company.cik
    company_name = company.name or ticker
    sic_code = getattr(company.data, "sic", None)

    print(f"  Company: {company_name}")
    print(f"  CIK: {cik}")
    print(f"  SIC: {sic_code}")

    # Step 2: Detect archetype
    archetype = detect_archetype(sic_code)
    excluded = get_archetype_excluded_metrics(archetype)
    print(f"  Archetype: {archetype} ({ARCHETYPE_DEFINITIONS.get(AccountingArchetype[archetype], {}).get('name', 'Unknown')})")
    if excluded:
        print(f"  Default exclusions: {excluded}")

    # Step 3: Detect fiscal year end
    fiscal_year_end = detect_fiscal_year_end(company)
    if fiscal_year_end != "December":
        print(f"  Fiscal year end: {fiscal_year_end}")

    # Build partial result for dry run
    result = OnboardingResult(
        ticker=ticker,
        cik=cik,
        company_name=company_name,
        archetype=archetype,
        sic_code=sic_code,
        fiscal_year_end=fiscal_year_end,
        metrics_excluded=excluded,
    )

    if dry_run:
        result.draft_yaml = generate_yaml_fragment(result)
        print(f"\n  [DRY RUN] Would onboard {ticker}")
        print(f"  Draft YAML:\n{result.draft_yaml}")
        return result

    # Step 3b: Generate yfinance snapshot (idempotent)
    existing_snapshot = load_snapshot(ticker)
    if existing_snapshot is None:
        print(f"  Generating yfinance snapshot...", end=" ", flush=True)
        try:
            fetch_and_save_snapshot(ticker)
            result.snapshot_created = True
            print("OK")
        except Exception as e:
            print(f"FAILED: {e}")
            result.error = f"Snapshot generation failed: {e}"
            result.draft_yaml = generate_yaml_fragment(result)
            return result
    else:
        meta = existing_snapshot.get("_metadata", {})
        fetched = meta.get("fetched_at", "unknown")
        print(f"  Using existing snapshot (fetched {fetched})")

    # Step 4: Run Orchestrator
    # Use _map_company_with_xbrl to get both mapping results AND the XBRL object,
    # which we need for explicit validation below.
    print(f"  Running extraction pipeline...")
    config = get_config(reload=True)
    orchestrator = Orchestrator(config=config, snapshot_mode=snapshot_mode)

    try:
        mapping_results, xbrl, filing_date, form_type = orchestrator._map_company_with_xbrl(
            ticker,
            use_ai=use_ai,
            use_facts=True,
        )
        result.extraction_ran = True

        # Detect silent XBRL failures: all results unmapped with XBRL error reasoning
        if xbrl is None:
            xbrl_errors = [r.reasoning for r in mapping_results.values()
                           if r.reasoning and "XBRL error" in r.reasoning]
            if xbrl_errors:
                result.error = f"XBRL parsing failed: {xbrl_errors[0]}"
                result.draft_yaml = generate_yaml_fragment(result)
                return result
    except Exception as e:
        result.error = f"Extraction failed: {e}"
        result.draft_yaml = generate_yaml_fragment(result)
        return result

    # Step 5: Collect validation results
    # Run explicit validation to get per-metric ValidationResult objects.
    # The internal _validate_layer calls don't store results on the orchestrator
    # for single-company map_company calls.
    validation_results = orchestrator.validator.validate_and_update_mappings(
        ticker, mapping_results, xbrl,
        filing_date=filing_date, form_type=form_type
    ) or {}

    for metric, mapping in mapping_results.items():
        if mapping.source == MappingSource.CONFIG:
            # Excluded by config
            if metric not in result.metrics_excluded:
                result.metrics_excluded.append(metric)
            continue

        if mapping.validation_status == "valid":
            result.metrics_passed.append(metric)
        elif mapping.is_mapped and mapping.validation_status == "pending":
            # Mapped but no reference value to validate against
            result.metrics_passed.append(metric)
        else:
            result.metrics_failed.append(metric)
            # Classify the failure
            vr = validation_results.get(metric)
            if vr:
                result.failures[metric] = classify_failure(metric, vr)
            else:
                result.failures[metric] = FailureDetail(
                    metric=metric,
                    reason=mapping.validation_notes or "Not mapped",
                    pattern="extraction_error",
                )

    # Step 6: Determine remediation complexity
    if len(result.metrics_failed) == 0:
        result.remediation_complexity = "clean"
    elif any(d.pattern == "structural" for d in result.failures.values()):
        result.remediation_complexity = "structural"
    else:
        result.remediation_complexity = "needs_review"

    # Step 6b: Record extraction runs to ledger
    try:
        ledger = ExperimentLedger()
        _record_extraction_runs(result, mapping_results, validation_results, ledger)
    except Exception as e:
        print(f"  Warning: Failed to record extraction runs: {e}")

    # Step 6c: Flush audit log to disk
    try:
        orchestrator.flush_audit_log()
    except Exception:
        pass  # flush_audit_log is best-effort

    # Step 7: Generate YAML
    result.draft_yaml = generate_yaml_fragment(result)

    # Print summary
    print(f"\n  {result.summary_line}")
    if result.metrics_failed:
        print(f"  Failed metrics:")
        for m in result.metrics_failed:
            detail = result.failures.get(m)
            if detail:
                print(f"    - {m}: {detail.reason} [{detail.pattern}]")
            else:
                print(f"    - {m}: unknown failure")

    return result


def onboard_batch(
    tickers: List[str],
    use_ai: bool = True,
    dry_run: bool = False,
    snapshot_mode: bool = True,
) -> List[OnboardingResult]:
    """Onboard multiple companies in sequence.

    Args:
        tickers: List of ticker symbols
        use_ai: Whether to use AI layer
        dry_run: If True, only resolve metadata
        snapshot_mode: Use pinned snapshots

    Returns:
        List of OnboardingResult objects
    """
    results = []
    for i, ticker in enumerate(tickers, 1):
        print(f"\n[{i}/{len(tickers)}] Processing {ticker}...")
        result = onboard_company(
            ticker,
            use_ai=use_ai,
            dry_run=dry_run,
            snapshot_mode=snapshot_mode,
        )
        results.append(result)

        # Brief pause between companies to avoid rate limiting
        if i < len(tickers) and not dry_run:
            time.sleep(1)

    return results


# =============================================================================
# REPORT OUTPUT
# =============================================================================

def save_report(result: OnboardingResult) -> Path:
    """Save onboarding report as JSON."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"{result.ticker}_report.json"
    with open(path, "w") as f:
        json.dump(result.to_dict(), f, indent=2, default=str)
    return path


def print_batch_summary(results: List[OnboardingResult]):
    """Print summary table for batch onboarding."""
    print(f"\n{'='*70}")
    print("ONBOARDING SUMMARY")
    print(f"{'='*70}")

    total_passed = 0
    total_failed = 0
    total_excluded = 0

    for r in results:
        if r.error:
            print(f"  {r.ticker}: ERROR — {r.error}")
        else:
            print(f"  {r.summary_line}")
        total_passed += len(r.metrics_passed)
        total_failed += len(r.metrics_failed)
        total_excluded += len(r.metrics_excluded)

    total = total_passed + total_failed
    pct = (total_passed / total * 100) if total > 0 else 0
    print(f"\n{'='*70}")
    print(f"TOTAL: {total_passed}/{total} passed ({pct:.0f}%)")
    print(f"  Excluded: {total_excluded}")
    if total_failed > 0:
        print(f"  Failed: {total_failed}")
    print(f"{'='*70}")

    # Print combined YAML
    yaml_fragments = [r.draft_yaml for r in results if r.draft_yaml and not r.error]
    if yaml_fragments:
        print(f"\n# === DRAFT YAML (paste into companies.yaml) ===")
        for frag in yaml_fragments:
            print(frag)
            print()


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Onboard companies into the standardized financial metrics system"
    )
    parser.add_argument(
        "ticker",
        nargs="?",
        help="Single ticker to onboard",
    )
    parser.add_argument(
        "--tickers",
        type=str,
        default=None,
        help="Comma-separated tickers for batch onboarding",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only resolve metadata, no extraction",
    )
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Skip AI layer (faster, static-only mapping)",
    )
    parser.add_argument(
        "--no-snapshot-mode",
        action="store_true",
        help="Use live yfinance instead of snapshots",
    )
    parser.add_argument(
        "--no-save-reports",
        action="store_true",
        default=False,
        help="Do not save JSON reports per company",
    )
    args = parser.parse_args()

    # Determine tickers
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",")]
    elif args.ticker:
        tickers = [args.ticker.upper()]
    else:
        parser.print_help()
        sys.exit(1)

    snapshot_mode = not args.no_snapshot_mode

    # Run onboarding
    results = onboard_batch(
        tickers=tickers,
        use_ai=not args.no_ai,
        dry_run=args.dry_run,
        snapshot_mode=snapshot_mode,
    )

    # Save reports
    if not args.no_save_reports and not args.dry_run:
        for r in results:
            if not r.error:
                path = save_report(r)
                print(f"  Report saved: {path.name}")

    # Print batch summary
    print_batch_summary(results)

    # Exit code: non-zero if any company errored
    if any(r.error for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
