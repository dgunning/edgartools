"""
Auto-Eval Dashboard: Morning review terminal display.

Rich-based dashboard showing overnight auto-eval session results:
- CQS trajectory
- Experiments kept/discarded
- Config diff summary
- Graveyard patterns (metrics flagged for Tier 3)
- Golden master status
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

# SLA targets — shared between dashboard display and compliance checks
EF_CQS_TARGET = 0.95
HEADLINE_EF_TARGET = 0.99

from edgar.xbrl.standardization.ledger.schema import ExperimentLedger
from edgar.xbrl.standardization.tools.auto_eval import (
    CQSResult,
    compute_cqs,
    print_cqs_report,
    QUICK_EVAL_COHORT,
)
from edgar.xbrl.standardization.tools.auto_eval_loop import OvernightReport

logger = logging.getLogger(__name__)


def show_dashboard(
    ledger: Optional[ExperimentLedger] = None,
    session_id: Optional[str] = None,
    last_n_experiments: int = 20,
):
    """
    Display the morning review dashboard.

    Shows the current state of the auto-eval system including recent
    experiments, CQS trajectory, graveyard patterns, and golden masters.

    Args:
        ledger: ExperimentLedger instance.
        session_id: Filter to a specific overnight session.
        last_n_experiments: How many recent experiments to show.
    """
    if ledger is None:
        ledger = ExperimentLedger()

    try:
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        from rich.columns import Columns
        from rich import box
        _show_rich_dashboard(ledger, session_id, last_n_experiments)
    except ImportError:
        _show_plain_dashboard(ledger, session_id, last_n_experiments)


def _show_rich_dashboard(
    ledger: ExperimentLedger,
    session_id: Optional[str],
    last_n: int,
):
    """Rich-based dashboard with tables and panels."""
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box

    console = Console()

    console.print()
    console.print(Panel.fit(
        "[bold cyan]Auto-Eval Dashboard[/bold cyan]\n"
        f"[dim]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]",
        border_style="cyan",
    ))

    # Section 1: Current Quality Status
    console.print("\n[bold]Quality Status[/bold]")
    try:
        cqs = compute_cqs(eval_cohort=QUICK_EVAL_COHORT, snapshot_mode=True)
        _render_cqs_panel(console, cqs)
        # SLA Compliance Indicators
        _render_sla_compliance(console, cqs)
    except Exception as e:
        console.print(f"  [red]Error computing CQS: {e}[/red]")

    # Section 2: Recent Experiments
    console.print("\n[bold]Recent Experiments[/bold]")
    experiments = ledger.get_experiments(limit=last_n)
    if experiments:
        _render_experiments_table(console, experiments)
    else:
        console.print("  [dim]No experiments recorded yet.[/dim]")

    # Section 3: Experiment Stats
    if experiments:
        console.print("\n[bold]Session Summary[/bold]")
        _render_session_stats(console, experiments, session_id)

    # Section 4: Graveyard Patterns
    console.print("\n[bold]Graveyard Patterns (Dead Ends)[/bold]")
    graveyard = ledger.get_graveyard_entries(limit=50)
    if graveyard:
        _render_graveyard_patterns(console, graveyard)
    else:
        console.print("  [dim]No graveyard entries yet.[/dim]")

    # Section 5: Golden Masters
    console.print("\n[bold]Golden Master Status[/bold]")
    golden = ledger.get_all_golden_masters(active_only=True)
    if golden:
        console.print(f"  Active golden masters: [green]{len(golden)}[/green]")
        # Group by ticker
        by_ticker: Dict[str, int] = {}
        for gm in golden:
            by_ticker[gm.ticker] = by_ticker.get(gm.ticker, 0) + 1
        for ticker in sorted(by_ticker.keys()):
            console.print(f"    {ticker}: {by_ticker[ticker]} metrics")
    else:
        console.print("  [dim]No golden masters yet.[/dim]")

    console.print()


def _render_cqs_panel(console, cqs: CQSResult):
    """Render CQS as a Rich panel with EF-CQS as headline."""
    from rich.table import Table
    from rich import box

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    veto_str = " [red]VETOED[/red]" if cqs.vetoed else ""

    # EF-CQS is the headline metric (primary KPI)
    ef_color = "green" if cqs.ef_cqs >= EF_CQS_TARGET else ("yellow" if cqs.ef_cqs >= 0.85 else "red")
    table.add_row("EF-CQS", f"[bold {ef_color}]{cqs.ef_cqs:.4f}[/bold {ef_color}]{veto_str}")
    table.add_row("", "")  # spacer

    # Sub-scores
    table.add_row("RFA Rate", f"{cqs.rfa_rate:.1%}")
    table.add_row("SMA Rate", f"{cqs.sma_rate:.1%}")
    table.add_row("SA-CQS", f"{cqs.sa_cqs:.4f}")
    table.add_row("", "")  # spacer

    # Traditional CQS components
    table.add_row("CQS (composite)", f"[dim]{cqs.cqs:.4f}[/dim]")
    table.add_row("Pass Rate", f"{cqs.pass_rate:.1%}")
    table.add_row("Mean Variance", f"{cqs.mean_variance:.1f}%")
    table.add_row("Coverage", f"{cqs.coverage_rate:.1%}")
    table.add_row("Golden Masters", f"{cqs.golden_master_rate:.1%}")
    table.add_row("Regressions", f"{cqs.total_regressions}")
    table.add_row("Explained Gaps", f"{cqs.explained_variance_count}")
    table.add_row("", "")  # spacer
    table.add_row("Companies", f"{cqs.companies_evaluated}")
    table.add_row("Duration", f"{cqs.duration_seconds:.1f}s")

    # Unverified metrics count
    unverified = sum(cs.unverified_count for cs in cqs.company_scores.values())
    if unverified:
        table.add_row("", "")
        table.add_row("Unverified Metrics", f"{unverified}")

    console.print(table)


def _render_sla_compliance(console, cqs: CQSResult):
    """Render SLA compliance indicators."""
    from rich.table import Table
    from rich import box

    table = Table(box=box.SIMPLE, show_header=True, padding=(0, 2))
    table.add_column("SLA Check", style="bold", min_width=25)
    table.add_column("Value", justify="right", min_width=8)
    table.add_column("Target", justify="right", min_width=8)
    table.add_column("Status", justify="center", min_width=8)

    # EF-CQS overall
    ef_ok = cqs.ef_cqs >= EF_CQS_TARGET
    table.add_row(
        "EF-CQS (overall)",
        f"{cqs.ef_cqs:.4f}",
        f">= {EF_CQS_TARGET:.4f}",
        "[green]PASS[/green]" if ef_ok else "[red]FAIL[/red]",
    )

    # Headline EF Rate
    headline_ef = cqs.headline_ef_rate
    headline_ok = headline_ef >= HEADLINE_EF_TARGET
    table.add_row(
        "Headline EF Rate",
        f"{headline_ef:.4f}",
        f">= {HEADLINE_EF_TARGET:.4f}",
        "[green]PASS[/green]" if headline_ok else "[red]FAIL[/red]",
    )

    # Zero regressions
    reg_ok = cqs.total_regressions == 0
    table.add_row(
        "Zero Regressions",
        str(cqs.total_regressions),
        "0",
        "[green]PASS[/green]" if reg_ok else "[red]FAIL[/red]",
    )

    # Overall SLA
    all_pass = ef_ok and headline_ok and reg_ok
    console.print(table)
    if all_pass:
        console.print("  [bold green]SLA: COMPLIANT[/bold green]")
    else:
        console.print("  [bold red]SLA: NOT YET COMPLIANT[/bold red]")
    console.print()


def _render_experiments_table(console, experiments: List[Dict]):
    """Render experiments as a Rich table."""
    from rich.table import Table
    from rich import box

    table = Table(box=box.ROUNDED, show_lines=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("Time", width=8)
    table.add_column("Metric", width=22)
    table.add_column("Type", width=14)
    table.add_column("CQS Before", justify="right", width=10)
    table.add_column("CQS After", justify="right", width=10)
    table.add_column("Delta", justify="right", width=8)
    table.add_column("Decision", width=10)

    for i, exp in enumerate(experiments, 1):
        ts = exp.get("timestamp", "")
        time_str = ts[11:19] if len(ts) > 19 else ts[:8]

        cqs_before = exp.get("cqs_before", 0)
        cqs_after = exp.get("cqs_after", 0)
        delta = cqs_after - cqs_before

        decision = exp.get("decision", "")
        if decision == "KEEP":
            decision_str = "[green]KEEP[/green]"
        elif decision == "VETO":
            decision_str = "[red]VETO[/red]"
        else:
            decision_str = "[yellow]DISCARD[/yellow]"

        delta_color = "green" if delta > 0 else ("red" if delta < 0 else "dim")
        delta_str = f"[{delta_color}]{delta:+.4f}[/{delta_color}]"

        table.add_row(
            str(i),
            time_str,
            exp.get("target_metric", "")[:22],
            exp.get("change_type", "")[:14],
            f"{cqs_before:.4f}",
            f"{cqs_after:.4f}",
            delta_str,
            decision_str,
        )

    console.print(table)


def _render_session_stats(console, experiments: List[Dict], session_id: Optional[str]):
    """Render session aggregate stats."""
    # Filter by session if specified
    if session_id:
        experiments = [e for e in experiments if e.get("run_id") == session_id]

    total = len(experiments)
    kept = sum(1 for e in experiments if e.get("decision") == "KEEP")
    discarded = sum(1 for e in experiments if e.get("decision") == "DISCARD")
    vetoed = sum(1 for e in experiments if e.get("decision") == "VETO")

    cqs_values = [e.get("cqs_after", 0) for e in experiments if e.get("cqs_after")]
    cqs_start = experiments[-1].get("cqs_before", 0) if experiments else 0
    cqs_end = experiments[0].get("cqs_after", 0) if experiments else 0
    cqs_peak = max(cqs_values) if cqs_values else 0

    console.print(f"  Total experiments: {total}")
    console.print(f"  Kept: [green]{kept}[/green] | Discarded: [yellow]{discarded}[/yellow] | Vetoed: [red]{vetoed}[/red]")
    console.print(f"  CQS trajectory: {cqs_start:.4f} -> {cqs_end:.4f} (peak: {cqs_peak:.4f})")

    if total > 0:
        success_rate = kept / total * 100
        console.print(f"  Success rate: {success_rate:.0f}%")

    # Show LIS-based KEEP count if available
    lis_keeps = sum(1 for e in experiments if e.get("decision") == "KEEP" and "LIS KEEP" in e.get("notes", ""))
    if lis_keeps > 0:
        console.print(f"  LIS-based KEEPs: [green]{lis_keeps}[/green] (would have been discarded by CQS alone)")


def _render_graveyard_patterns(console, graveyard: List[Dict]):
    """Render graveyard patterns — metrics that repeatedly fail."""
    from rich.table import Table
    from rich import box

    # Aggregate by metric
    metric_counts: Dict[str, Dict] = {}
    for entry in graveyard:
        metric = entry.get("target_metric", "unknown")
        if metric not in metric_counts:
            metric_counts[metric] = {
                "count": 0,
                "reasons": {},
                "companies": set(),
            }
        metric_counts[metric]["count"] += 1
        reason = entry.get("discard_reason", "unknown")
        metric_counts[metric]["reasons"][reason] = metric_counts[metric]["reasons"].get(reason, 0) + 1
        companies = entry.get("target_companies", "")
        if companies:
            metric_counts[metric]["companies"].add(companies)

    # Sort by failure count
    sorted_metrics = sorted(metric_counts.items(), key=lambda x: -x[1]["count"])

    # Only show metrics with 2+ failures
    flagged = [(m, d) for m, d in sorted_metrics if d["count"] >= 2]

    if not flagged:
        console.print("  [dim]No recurring failures detected.[/dim]")
        return

    table = Table(box=box.SIMPLE, show_lines=False)
    table.add_column("Metric", width=25)
    table.add_column("Failures", justify="right", width=8)
    table.add_column("Top Reason", width=18)
    table.add_column("Companies", width=25)
    table.add_column("Status", width=12)

    for metric, data in flagged[:15]:
        top_reason = max(data["reasons"], key=data["reasons"].get)
        companies = ", ".join(sorted(data["companies"]))[:25]

        if data["count"] >= 3:
            status = "[red]DEAD END[/red]"
        else:
            status = "[yellow]STRUGGLING[/yellow]"

        table.add_row(
            metric[:25],
            str(data["count"]),
            top_reason,
            companies,
            status,
        )

    console.print(table)

    dead_ends = sum(1 for _, d in flagged if d["count"] >= 3)
    if dead_ends > 0:
        console.print(f"\n  [red]{dead_ends} metrics flagged as dead ends — need Tier 3 (Python) or human review[/red]")


# =============================================================================
# PLAIN TEXT FALLBACK
# =============================================================================

def _show_plain_dashboard(
    ledger: ExperimentLedger,
    session_id: Optional[str],
    last_n: int,
):
    """Plain text dashboard (no Rich dependency)."""
    print()
    print("=" * 70)
    print("  AUTO-EVAL DASHBOARD")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Current CQS
    print("\nCURRENT CQS:")
    try:
        cqs = compute_cqs(eval_cohort=QUICK_EVAL_COHORT, snapshot_mode=True)
        print_cqs_report(cqs)
    except Exception as e:
        print(f"  Error: {e}")

    # Recent experiments
    print("\nRECENT EXPERIMENTS:")
    experiments = ledger.get_experiments(limit=last_n)
    if experiments:
        print(f"  {'#':>3} {'Metric':<22} {'Type':<14} {'Before':>8} {'After':>8} {'Decision':<10}")
        print("  " + "-" * 70)
        for i, exp in enumerate(experiments, 1):
            print(
                f"  {i:>3} {exp.get('target_metric', ''):<22} "
                f"{exp.get('change_type', ''):<14} "
                f"{exp.get('cqs_before', 0):>8.4f} "
                f"{exp.get('cqs_after', 0):>8.4f} "
                f"{exp.get('decision', ''):<10}"
            )
    else:
        print("  No experiments recorded yet.")

    # Graveyard
    print("\nGRAVEYARD PATTERNS:")
    graveyard = ledger.get_graveyard_entries(limit=50)
    if graveyard:
        metric_counts: Dict[str, int] = {}
        for entry in graveyard:
            metric = entry.get("target_metric", "unknown")
            metric_counts[metric] = metric_counts.get(metric, 0) + 1

        for metric, count in sorted(metric_counts.items(), key=lambda x: -x[1]):
            status = "DEAD END" if count >= 3 else "struggling"
            print(f"  {metric:<25} failures={count}  [{status}]")
    else:
        print("  No graveyard entries yet.")

    # Golden masters
    print("\nGOLDEN MASTERS:")
    golden = ledger.get_all_golden_masters(active_only=True)
    print(f"  Active: {len(golden)}")

    print("=" * 70)
    print()


def print_overnight_report(report: OvernightReport):
    """Print an overnight session report."""
    print()
    print("=" * 70)
    print("OVERNIGHT AUTO-EVAL REPORT")
    print("=" * 70)

    print(f"\n  Session:     {report.session_id}")
    print(f"  Started:     {report.started_at}")
    print(f"  Finished:    {report.finished_at}")
    print(f"  Duration:    {report.duration_hours:.1f} hours")
    if report.focus_area:
        print(f"  Focus:       {report.focus_area}")

    print(f"\n  Experiments: {report.experiments_total}")
    print(f"    Kept:      {report.experiments_kept}")
    print(f"    Discarded: {report.experiments_discarded}")
    print(f"    Vetoed:    {report.experiments_vetoed}")

    print(f"\n  CQS Trajectory:")
    print(f"    Start:     {report.cqs_start:.4f}")
    print(f"    End:       {report.cqs_end:.4f}")
    print(f"    Peak:      {report.cqs_peak:.4f}")
    print(f"    Delta:     {report.cqs_improvement:+.4f}")

    print(f"\n  Two-Score Architecture:")
    print(f"    EF-CQS:    {report.ef_cqs_start:.4f} -> {report.ef_cqs_end:.4f}")
    print(f"    SA-CQS:    {report.sa_cqs_start:.4f} -> {report.sa_cqs_end:.4f}")
    if report.solver_proposals > 0:
        print(f"    Solver:    {report.solver_kept}/{report.solver_proposals} proposals kept")

    if report.stopped_early:
        print(f"\n  Early Stop:  {report.stop_reason}")

    if report.config_diffs:
        print(f"\n  Config Changes ({len(report.config_diffs)}):")
        for i, diff in enumerate(report.config_diffs, 1):
            for line in diff.split("\n"):
                print(f"    {line}")

    print("=" * 70)
    print()
