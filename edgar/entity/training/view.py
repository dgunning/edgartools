#!/usr/bin/env python3
"""
View Learning Results

A Rich-based viewer for financial statement concept learning outputs.
Displays comprehensive statistics about what was learned from SEC filings.

Usage:
    python -m edgar.entity.training.view
    python -m edgar.entity.training.view --output training/output
    python -m edgar.entity.training.view --top 20  # Show top 20 companies
"""

import argparse
import json
from pathlib import Path
from datetime import datetime

from . import get_output_dir

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich import box
from rich.tree import Tree
from rich.progress import Progress, BarColumn, TextColumn


console = Console()


def load_json(path: Path) -> dict | None:
    """Load a JSON file, returning None if not found."""
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


def format_duration(seconds: float) -> str:
    """Format seconds into human-readable duration."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.0f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def format_rate(rate: float) -> str:
    """Format a rate as percentage with color coding."""
    pct = rate * 100
    if pct >= 80:
        return f"[green]{pct:.1f}%[/green]"
    elif pct >= 50:
        return f"[yellow]{pct:.1f}%[/yellow]"
    else:
        return f"[red]{pct:.1f}%[/red]"


def format_number(n: int | float) -> str:
    """Format a number with thousands separator."""
    if isinstance(n, float):
        return f"{n:,.2f}"
    return f"{n:,}"


def render_summary_panel(summary: dict, stats: dict) -> Panel:
    """Render the main summary panel."""
    metadata = stats.get("metadata", {})
    data = stats.get("data_summary", {})

    # Calculate success rate color
    success_rate = data.get("success_rate", 0)
    if success_rate >= 0.8:
        rate_color = "green"
    elif success_rate >= 0.6:
        rate_color = "yellow"
    else:
        rate_color = "red"

    timestamp = metadata.get("generated", "Unknown")
    if timestamp != "Unknown":
        try:
            dt = datetime.fromisoformat(timestamp)
            timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            pass

    lines = [
        f"[bold]Generated:[/bold] {timestamp}",
        f"[bold]Min Occurrence Rate:[/bold] {metadata.get('min_occurrence_rate', 0.3) * 100:.0f}%",
        "",
        f"[bold]Companies Attempted:[/bold] {format_number(data.get('companies_processed', 0))}",
        f"[bold]Companies Successful:[/bold] {format_number(data.get('companies_successful', 0))} [{rate_color}]({success_rate*100:.1f}%)[/{rate_color}]",
        f"[bold]Companies Failed:[/bold] {format_number(data.get('companies_failed', 0))}",
        "",
        f"[bold]Total Observations:[/bold] {format_number(data.get('total_observations', 0))}",
        f"[bold]Avg Processing Time:[/bold] {data.get('avg_processing_time_ms', 0):.0f}ms per company",
        f"[bold]Total Processing Time:[/bold] {format_duration(data.get('total_processing_time_s', 0))}",
    ]

    return Panel(
        "\n".join(lines),
        title="[bold cyan]Learning Run Summary[/bold cyan]",
        border_style="cyan",
        padding=(1, 2)
    )


def render_concept_counts_table(stats: dict) -> Table:
    """Render the concept counts table."""
    counts = stats.get("concept_counts", {})

    table = Table(
        title="[bold]Concept Analysis[/bold]",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta"
    )
    table.add_column("Metric", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Rate", justify="right")

    total = counts.get("total_unique_concepts", 0)
    standard = counts.get("standard_concepts", 0)
    custom = counts.get("custom_concepts", 0)
    canonical = counts.get("canonical_concepts", 0)
    filtered = counts.get("filtered_out", 0)

    table.add_row("Total Unique Concepts", format_number(total), "100%")
    table.add_row("├─ Standard (us-gaap)", format_number(standard), f"{(standard/total*100) if total else 0:.1f}%")
    table.add_row("└─ Custom (company-specific)", format_number(custom), f"[yellow]{counts.get('custom_rate', 0)*100:.1f}%[/yellow]")
    table.add_row("", "", "")
    table.add_row("[bold]Canonical Concepts[/bold]", f"[green bold]{format_number(canonical)}[/green bold]", f"[green]{counts.get('canonical_rate', 0)*100:.1f}%[/green]")
    table.add_row("[dim]Filtered Out[/dim]", f"[dim]{format_number(filtered)}[/dim]", f"[dim]{counts.get('filtered_rate', 0)*100:.1f}%[/dim]")

    return table


def render_statement_table(stats: dict, summary: dict) -> Table:
    """Render the per-statement breakdown table."""
    by_statement = stats.get("by_statement", {})
    canonical = summary.get("canonical_concepts", {})

    table = Table(
        title="[bold]Concepts by Financial Statement[/bold]",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold blue"
    )
    table.add_column("Statement", style="cyan")
    table.add_column("Total Observed", justify="right")
    table.add_column("Canonical", justify="right", style="green")
    table.add_column("Canonical Rate", justify="right")

    # Order statements logically
    statement_order = [
        "BalanceSheet",
        "IncomeStatement",
        "CashFlowStatement",
        "StatementOfEquity",
        "ComprehensiveIncome"
    ]

    statement_labels = {
        "BalanceSheet": "Balance Sheet",
        "IncomeStatement": "Income Statement",
        "CashFlowStatement": "Cash Flow Statement",
        "StatementOfEquity": "Statement of Equity",
        "ComprehensiveIncome": "Comprehensive Income"
    }

    total_observed = 0
    total_canonical = 0

    for stmt in statement_order:
        if stmt in by_statement:
            data = by_statement[stmt]
            observed = data.get("total_concepts", 0)
            canon = canonical.get(stmt, data.get("canonical_concepts", 0))
            rate = data.get("canonical_rate", 0)

            total_observed += observed
            total_canonical += canon

            table.add_row(
                statement_labels.get(stmt, stmt),
                format_number(observed),
                format_number(canon),
                format_rate(rate)
            )

    table.add_row("", "", "", "")
    table.add_row(
        "[bold]Total[/bold]",
        f"[bold]{format_number(total_observed)}[/bold]",
        f"[bold green]{format_number(total_canonical)}[/bold green]",
        ""
    )

    return table


def render_company_stats_panel(stats: dict) -> Panel:
    """Render per-company statistics panel."""
    per_company = stats.get("per_company_stats", {})

    concepts = per_company.get("concepts", {})
    custom = per_company.get("custom_concepts", {})
    coverage = per_company.get("coverage", {})

    lines = [
        "[bold underline]Concepts per Company[/bold underline]",
        f"  Min: {concepts.get('min', 0)}  |  Max: {concepts.get('max', 0)}  |  Mean: {concepts.get('mean', 0):.0f}  |  Median: {concepts.get('median', 0):.0f}",
        "",
        "[bold underline]Custom Concepts per Company[/bold underline]",
        f"  Min: {custom.get('min', 0)}  |  Max: {custom.get('max', 0)}  |  Mean: {custom.get('mean', 0):.1f}  |  Median: {custom.get('median', 0):.0f}",
        "",
        "[bold underline]Canonical Coverage Rate[/bold underline]",
        f"  Min: {coverage.get('min', 0)*100:.1f}%  |  Max: {coverage.get('max', 0)*100:.1f}%  |  Mean: {coverage.get('mean', 0)*100:.1f}%  |  Median: {coverage.get('median', 0)*100:.1f}%",
    ]

    return Panel(
        "\n".join(lines),
        title="[bold yellow]Per-Company Statistics[/bold yellow]",
        border_style="yellow",
        padding=(1, 2)
    )


def render_failure_analysis(stats: dict) -> Panel | None:
    """Render failure analysis panel."""
    failure_analysis = stats.get("failure_analysis", {})
    if not failure_analysis:
        return None

    by_reason = failure_analysis.get("by_reason", {})
    total_failures = failure_analysis.get("total_failures", 0)

    if total_failures == 0:
        return None

    reason_labels = {
        "no_10k_filings": "No 10-K filings (likely foreign filer)",
        "no_latest_filing": "Could not get latest filing",
        "no_xbrl_data": "No XBRL data in filing",
        "processing_error": "Processing error"
    }

    lines = [
        f"[bold]Total Failures:[/bold] {total_failures}",
        ""
    ]

    for reason, data in by_reason.items():
        count = data.get("count", 0)
        tickers = data.get("tickers", [])
        label = reason_labels.get(reason, reason)
        lines.append(f"[bold]{label}:[/bold] {count}")
        if tickers:
            ticker_str = ", ".join(tickers[:10])
            if len(tickers) > 10:
                ticker_str += f" ... (+{len(tickers) - 10} more)"
            lines.append(f"  [dim]{ticker_str}[/dim]")

    return Panel(
        "\n".join(lines),
        title="[bold orange1]Failure Analysis[/bold orange1]",
        border_style="orange1",
        padding=(1, 2)
    )


def render_custom_concepts_table(stats: dict, top_n: int = 10) -> Table:
    """Render table of companies with most custom concepts."""
    custom_by_company = stats.get("custom_concepts_by_company", {})

    # Sort by count
    sorted_companies = sorted(
        custom_by_company.items(),
        key=lambda x: x[1].get("count", 0),
        reverse=True
    )[:top_n]

    table = Table(
        title=f"[bold]Top {top_n} Companies by Custom Concepts[/bold]",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold red"
    )
    table.add_column("#", style="dim", width=3)
    table.add_column("Ticker", style="cyan")
    table.add_column("Custom", justify="right")
    table.add_column("Example Concepts", style="dim", max_width=60)

    for i, (ticker, data) in enumerate(sorted_companies, 1):
        count = data.get("count", 0)
        examples = data.get("examples", [])[:2]
        example_str = ", ".join(examples) if examples else ""
        if len(example_str) > 57:
            example_str = example_str[:57] + "..."

        table.add_row(
            str(i),
            ticker.upper(),
            str(count),
            example_str
        )

    return table


def render_outliers_panel(stats: dict) -> Panel | None:
    """Render outliers panel if any exist."""
    outliers = stats.get("outliers", {})

    lines = []

    high_concept = outliers.get("high_concept_count", [])
    if high_concept:
        lines.append("[bold]High Concept Count[/bold] (3+ std dev above mean)")
        for item in high_concept[:5]:
            lines.append(f"  • {item.get('ticker', 'N/A')}: {item.get('total_concepts', 0)} concepts (+{item.get('deviation', 0):.1f}σ)")
        lines.append("")

    high_custom = outliers.get("high_custom_rate", [])
    if high_custom:
        lines.append("[bold]High Custom Rate[/bold] (unusual amount of custom concepts)")
        for item in high_custom[:5]:
            lines.append(f"  • {item.get('ticker', 'N/A')}: {item.get('custom_rate', 0)*100:.1f}% custom ({item.get('custom_concepts', 0)} concepts)")
        lines.append("")

    low_coverage = outliers.get("low_coverage", [])
    if low_coverage:
        lines.append("[bold]Low Coverage[/bold] (poor canonical coverage)")
        for item in low_coverage[:5]:
            lines.append(f"  • {item.get('ticker', 'N/A')}: {item.get('coverage_rate', 0)*100:.1f}% coverage")

    if not lines:
        return None

    return Panel(
        "\n".join(lines),
        title="[bold red]Outliers[/bold red]",
        border_style="red",
        padding=(1, 2)
    )


def render_company_details_table(stats: dict, top_n: int = 15) -> Table:
    """Render detailed company-level results."""
    details = stats.get("company_details", [])

    # Sort by coverage rate descending
    sorted_details = sorted(details, key=lambda x: x.get("coverage_rate", 0), reverse=True)

    table = Table(
        title=f"[bold]Company Details (Top {top_n} by Coverage)[/bold]",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold green"
    )
    table.add_column("Ticker", style="cyan")
    table.add_column("Name", max_width=30)
    table.add_column("Concepts", justify="right")
    table.add_column("Canonical", justify="right")
    table.add_column("Coverage", justify="right")
    table.add_column("Custom", justify="right")
    table.add_column("Time (ms)", justify="right", style="dim")

    for item in sorted_details[:top_n]:
        coverage = item.get("coverage_rate", 0)
        if coverage >= 0.7:
            cov_style = "green"
        elif coverage >= 0.5:
            cov_style = "yellow"
        else:
            cov_style = "red"

        name = item.get("name", "")
        if len(name) > 28:
            name = name[:28] + "…"

        table.add_row(
            item.get("ticker", "N/A"),
            name,
            str(item.get("total_concepts", 0)),
            str(item.get("canonical_covered", 0)),
            f"[{cov_style}]{coverage*100:.1f}%[/{cov_style}]",
            str(item.get("custom_concepts", 0)),
            f"{item.get('processing_time_ms', 0):.0f}"
        )

    return table


def render_linkages_summary(linkages: dict) -> Panel | None:
    """Render concept linkages summary."""
    if not linkages:
        return None

    metadata = linkages.get("metadata", {})
    summary = linkages.get("summary", {})
    categories = linkages.get("categories", {})

    lines = [
        f"[bold]Total Unique Concepts:[/bold] {format_number(metadata.get('total_unique_concepts', 0))}",
        f"[bold]Single-Statement Concepts:[/bold] {format_number(metadata.get('single_statement_concepts', 0))}",
        f"[bold]Multi-Statement Concepts:[/bold] {format_number(metadata.get('multi_statement_concepts', 0))}",
        f"[bold]Key Linkage Concepts:[/bold] {format_number(metadata.get('linkage_concepts', 0))}",
        "",
        "[bold underline]By Statement Count[/bold underline]",
    ]

    by_count = summary.get("by_statement_count", {})
    for count, num in sorted(by_count.items(), key=lambda x: int(x[0])):
        lines.append(f"  Appears in {count} statements: {num} concepts")

    if categories:
        lines.append("")
        lines.append("[bold underline]Linkage Categories[/bold underline]")

        category_labels = {
            "income_to_cashflow": "Income → Cash Flow",
            "balance_to_equity": "Balance Sheet → Equity",
            "balance_to_cashflow": "Balance Sheet → Cash Flow",
            "comprehensive_income": "Comprehensive Income",
            "xbrl_structural": "XBRL Structural"
        }

        for cat, concepts in categories.items():
            if concepts:
                label = category_labels.get(cat, cat)
                lines.append(f"  {label}: {len(concepts)} concepts")

    return Panel(
        "\n".join(lines),
        title="[bold magenta]Cross-Statement Linkages[/bold magenta]",
        border_style="magenta",
        padding=(1, 2)
    )


def render_files_table(output_dir: Path) -> Table:
    """Render table of output files."""
    table = Table(
        title="[bold]Output Files[/bold]",
        box=box.SIMPLE,
        show_header=True,
        header_style="bold"
    )
    table.add_column("File", style="cyan")
    table.add_column("Size", justify="right")
    table.add_column("Description")

    file_descriptions = {
        "learned_mappings.json": "Concept → statement mappings",
        "virtual_trees.json": "Hierarchical statement structures",
        "statement_mappings_v1.json": "Versioned statement mappings",
        "canonical_structures.json": "Full statistical analysis",
        "concept_linkages.json": "Multi-statement concept tracking",
        "learning_summary.json": "Run summary metadata",
        "learning_statistics.json": "Comprehensive statistics",
        "structural_learning_report.md": "Human-readable report"
    }

    for file_path in sorted(output_dir.glob("*.json")) + sorted(output_dir.glob("*.md")):
        if file_path.name.startswith("."):
            continue
        size = file_path.stat().st_size
        if size >= 1_000_000:
            size_str = f"{size / 1_000_000:.2f} MB"
        elif size >= 1000:
            size_str = f"{size / 1000:.1f} KB"
        else:
            size_str = f"{size} B"

        desc = file_descriptions.get(file_path.name, "")
        table.add_row(file_path.name, size_str, desc)

    return table


def main():
    parser = argparse.ArgumentParser(description="View financial statement concept learning results")
    parser.add_argument("--output", "-o", type=str, default=None,
                       help="Output directory containing learning results (default: training/output)")
    parser.add_argument("--top", "-t", type=int, default=15,
                       help="Number of top companies to show in details")
    args = parser.parse_args()

    output_dir = Path(args.output) if args.output else get_output_dir()

    if not output_dir.exists():
        console.print(f"[red]Error: Output directory not found: {output_dir}[/red]")
        return 1

    # Load data files
    summary = load_json(output_dir / "learning_summary.json")
    stats = load_json(output_dir / "learning_statistics.json")
    linkages = load_json(output_dir / "concept_linkages.json")

    if not summary or not stats:
        console.print("[red]Error: Required files not found (learning_summary.json, learning_statistics.json)[/red]")
        return 1

    # Render header
    console.print()
    console.print("[bold blue]═══════════════════════════════════════════════════════════════════════════════[/bold blue]")
    console.print("[bold blue]                    FINANCIAL STATEMENT CONCEPT LEARNING RESULTS              [/bold blue]")
    console.print("[bold blue]═══════════════════════════════════════════════════════════════════════════════[/bold blue]")
    console.print()

    # Summary panel
    console.print(render_summary_panel(summary, stats))
    console.print()

    # Failure analysis (if any failures)
    failure_panel = render_failure_analysis(stats)
    if failure_panel:
        console.print(failure_panel)
        console.print()

    # Concept counts and statement breakdown side by side
    concept_table = render_concept_counts_table(stats)
    statement_table = render_statement_table(stats, summary)

    console.print(Columns([concept_table, statement_table], padding=(0, 2)))
    console.print()

    # Per-company statistics
    console.print(render_company_stats_panel(stats))
    console.print()

    # Custom concepts by company
    console.print(render_custom_concepts_table(stats, top_n=10))
    console.print()

    # Linkages summary
    linkages_panel = render_linkages_summary(linkages)
    if linkages_panel:
        console.print(linkages_panel)
        console.print()

    # Outliers
    outliers_panel = render_outliers_panel(stats)
    if outliers_panel:
        console.print(outliers_panel)
        console.print()

    # Company details
    console.print(render_company_details_table(stats, top_n=args.top))
    console.print()

    # Output files
    console.print(render_files_table(output_dir))
    console.print()

    return 0


if __name__ == "__main__":
    exit(main())
