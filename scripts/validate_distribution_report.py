"""
Validation harness for DistributionReport extraction accuracy.

Samples 10-D filings across different ABS types and measures:
1. Extraction success rate (did we get a value?)
2. Value validity (is the value reasonable?)
3. Failure patterns (why did extraction fail?)

Usage:
    python scripts/validate_distribution_report.py [--sample-size 50]
"""

import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()


@dataclass
class MetricValidation:
    """Validation result for a single metric."""
    extracted: bool = False
    valid: bool = False
    value: Optional[any] = None
    error: Optional[str] = None


@dataclass
class FilingValidation:
    """Validation results for a single filing."""
    cik: str
    company: str
    filing_date: date
    abs_type: str
    success: bool = True
    error: Optional[str] = None
    metrics: Dict[str, MetricValidation] = field(default_factory=dict)
    num_tables: int = 0
    num_labeled_tables: int = 0


@dataclass
class ValidationSummary:
    """Summary of validation results."""
    total_filings: int = 0
    successful_parses: int = 0
    failed_parses: int = 0

    # Per-metric stats
    metric_extraction_rates: Dict[str, float] = field(default_factory=dict)
    metric_validity_rates: Dict[str, float] = field(default_factory=dict)

    # Per-ABS-type stats
    abs_type_counts: Dict[str, int] = field(default_factory=dict)
    abs_type_success_rates: Dict[str, float] = field(default_factory=dict)

    # Failure analysis
    common_errors: Dict[str, int] = field(default_factory=dict)

    # Individual results
    results: List[FilingValidation] = field(default_factory=list)


# Metrics to validate and their validation rules
METRICS_CONFIG = {
    'distribution_date': {
        'validator': lambda v: isinstance(v, date) and v > date(2020, 1, 1) and v <= date.today() + timedelta(days=30),
        'description': 'Distribution Date',
    },
    'collection_period_start': {
        'validator': lambda v: isinstance(v, date) and v > date(2020, 1, 1),
        'description': 'Collection Period Start',
    },
    'collection_period_end': {
        'validator': lambda v: isinstance(v, date) and v > date(2020, 1, 1),
        'description': 'Collection Period End',
    },
    'beginning_pool_balance': {
        'validator': lambda v: isinstance(v, (int, float)) and v >= 10000,  # At least $10k
        'description': 'Beginning Balance',
    },
    'ending_pool_balance': {
        'validator': lambda v: isinstance(v, (int, float)) and v >= 10000,
        'description': 'Ending Balance',
    },
    'original_pool_balance': {
        'validator': lambda v: isinstance(v, (int, float)) and v >= 100000,  # At least $100k
        'description': 'Original Balance',
    },
    'pool_factor': {
        'validator': lambda v: isinstance(v, (int, float)) and 0 < v <= 100,
        'description': 'Pool Factor',
    },
    'total_principal_distributed': {
        'validator': lambda v: isinstance(v, (int, float)) and v >= 0,
        'description': 'Principal Distributed',
    },
    'total_interest_distributed': {
        'validator': lambda v: isinstance(v, (int, float)) and v >= 0,
        'description': 'Interest Distributed',
    },
    'delinquent_30_59_days': {
        'validator': lambda v: isinstance(v, (int, float)) and v >= 0,
        'description': '30-59 Day Delinquent',
    },
    'delinquent_60_89_days': {
        'validator': lambda v: isinstance(v, (int, float)) and v >= 0,
        'description': '60-89 Day Delinquent',
    },
    'total_delinquent': {
        'validator': lambda v: isinstance(v, (int, float)) and v >= 0,
        'description': 'Total Delinquent',
    },
    'net_losses': {
        'validator': lambda v: isinstance(v, (int, float)),  # Can be negative (gains)
        'description': 'Net Losses',
    },
}


def get_diverse_sample(sample_size: int) -> List[Tuple[str, str]]:
    """
    Get a diverse sample of 10-D filings across different ABS types.

    Returns list of (company_name, cik) tuples.
    """
    from edgar import get_filings

    # Get recent 10-D filings
    filings = get_filings(form="10-D").head(500)

    # Categorize by ABS type keywords
    categories = {
        'auto': ['auto', 'vehicle', 'car', 'motor', 'drive', 'fleet'],
        'credit_card': ['credit card', 'card receivable', 'issuance trust', 'master trust'],
        'mortgage': ['mortgage', 'cmbs', 'rmbs', 'mbs', 'bank5', 'bank 20'],
        'student_loan': ['student', 'education', 'navient', 'slma'],
        'equipment': ['equipment', 'lease', 'rental'],
        'other': [],  # Catch-all
    }

    categorized = defaultdict(list)
    seen_ciks = set()

    for f in filings:
        if f.cik in seen_ciks:
            continue
        seen_ciks.add(f.cik)

        company_lower = f.company.lower()
        assigned = False

        for category, keywords in categories.items():
            if category == 'other':
                continue
            if any(kw in company_lower for kw in keywords):
                categorized[category].append((f.company, f.cik))
                assigned = True
                break

        if not assigned:
            categorized['other'].append((f.company, f.cik))

    # Build sample with proportional representation
    sample = []
    per_category = max(1, sample_size // len(categories))

    for category, items in categorized.items():
        sample.extend(items[:per_category])

    # Fill remaining slots
    remaining = sample_size - len(sample)
    all_items = [item for items in categorized.values() for item in items if item not in sample]
    sample.extend(all_items[:remaining])

    return sample[:sample_size]


def validate_filing(cik: str, company: str) -> FilingValidation:
    """Validate distribution report extraction for a single filing."""
    from edgar import Company

    result = FilingValidation(cik=cik, company=company, filing_date=date.today(), abs_type='UNKNOWN')

    try:
        comp = Company(cik)
        filings = comp.get_filings(form="10-D")

        if not filings or len(filings) == 0:
            result.success = False
            result.error = "No 10-D filings found"
            return result

        filing = filings[0]
        result.filing_date = filing.filing_date

        ten_d = filing.obj()
        result.abs_type = ten_d.abs_type.value if ten_d.abs_type else 'UNKNOWN'

        report = ten_d.distribution_report
        if not report:
            result.success = False
            result.error = "No distribution report (no EX-99 exhibits)"
            return result

        result.num_tables = len(report.tables)
        result.num_labeled_tables = len([t for t in report.tables if t.label])

        # Validate each metric
        metrics = report.metrics
        for metric_name, config in METRICS_CONFIG.items():
            value = getattr(metrics, metric_name, None)
            validation = MetricValidation()

            if value is not None:
                validation.extracted = True
                validation.value = value
                try:
                    validation.valid = config['validator'](value)
                    if not validation.valid:
                        validation.error = f"Value {value} failed validation"
                except Exception as e:
                    validation.valid = False
                    validation.error = str(e)

            result.metrics[metric_name] = validation

    except Exception as e:
        result.success = False
        result.error = str(e)

    return result


def compute_summary(results: List[FilingValidation]) -> ValidationSummary:
    """Compute summary statistics from validation results."""
    summary = ValidationSummary()
    summary.total_filings = len(results)
    summary.results = results

    # Count successes/failures
    summary.successful_parses = sum(1 for r in results if r.success)
    summary.failed_parses = sum(1 for r in results if not r.success)

    # ABS type distribution
    for r in results:
        summary.abs_type_counts[r.abs_type] = summary.abs_type_counts.get(r.abs_type, 0) + 1

    # Per-metric extraction and validity rates
    successful_results = [r for r in results if r.success]

    for metric_name in METRICS_CONFIG.keys():
        extracted_count = sum(1 for r in successful_results if r.metrics.get(metric_name, MetricValidation()).extracted)
        valid_count = sum(1 for r in successful_results if r.metrics.get(metric_name, MetricValidation()).valid)

        if successful_results:
            summary.metric_extraction_rates[metric_name] = extracted_count / len(successful_results) * 100
            summary.metric_validity_rates[metric_name] = valid_count / len(successful_results) * 100 if extracted_count > 0 else 0

    # ABS type success rates
    for abs_type in summary.abs_type_counts.keys():
        type_results = [r for r in results if r.abs_type == abs_type]
        type_successes = [r for r in type_results if r.success]

        # Calculate average extraction rate for this type
        if type_successes:
            rates = []
            for metric_name in METRICS_CONFIG.keys():
                extracted = sum(1 for r in type_successes if r.metrics.get(metric_name, MetricValidation()).extracted)
                rates.append(extracted / len(type_successes) * 100)
            summary.abs_type_success_rates[abs_type] = sum(rates) / len(rates)

    # Common errors
    for r in results:
        if r.error:
            # Normalize error message
            error_key = r.error[:50] if len(r.error) > 50 else r.error
            summary.common_errors[error_key] = summary.common_errors.get(error_key, 0) + 1

    return summary


def print_summary(summary: ValidationSummary):
    """Print validation summary to console."""
    console.print("\n[bold blue]═══════════════════════════════════════════════════════════════[/bold blue]")
    console.print("[bold blue]         Distribution Report Validation Summary[/bold blue]")
    console.print("[bold blue]═══════════════════════════════════════════════════════════════[/bold blue]\n")

    # Overall stats
    console.print(f"[bold]Total Filings Tested:[/bold] {summary.total_filings}")
    console.print(f"[bold]Successful Parses:[/bold] {summary.successful_parses} ({summary.successful_parses/summary.total_filings*100:.1f}%)")
    console.print(f"[bold]Failed Parses:[/bold] {summary.failed_parses} ({summary.failed_parses/summary.total_filings*100:.1f}%)")

    # ABS Type Distribution
    console.print("\n[bold]ABS Type Distribution:[/bold]")
    type_table = Table(show_header=True)
    type_table.add_column("ABS Type")
    type_table.add_column("Count", justify="right")
    type_table.add_column("Avg Extraction Rate", justify="right")

    for abs_type, count in sorted(summary.abs_type_counts.items(), key=lambda x: -x[1]):
        rate = summary.abs_type_success_rates.get(abs_type, 0)
        style = "green" if rate >= 50 else "yellow" if rate >= 25 else "red"
        type_table.add_row(abs_type, str(count), f"[{style}]{rate:.1f}%[/{style}]")

    console.print(type_table)

    # Per-Metric Stats
    console.print("\n[bold]Per-Metric Extraction Rates:[/bold]")
    metric_table = Table(show_header=True)
    metric_table.add_column("Metric")
    metric_table.add_column("Extraction Rate", justify="right")
    metric_table.add_column("Validity Rate", justify="right")
    metric_table.add_column("Status")

    for metric_name, config in METRICS_CONFIG.items():
        extraction_rate = summary.metric_extraction_rates.get(metric_name, 0)
        validity_rate = summary.metric_validity_rates.get(metric_name, 0)

        # Determine status
        if extraction_rate >= 80 and validity_rate >= 95:
            status = "[green]✓ GOOD[/green]"
        elif extraction_rate >= 50 and validity_rate >= 80:
            status = "[yellow]~ OK[/yellow]"
        else:
            status = "[red]✗ NEEDS WORK[/red]"

        extraction_style = "green" if extraction_rate >= 80 else "yellow" if extraction_rate >= 50 else "red"
        validity_style = "green" if validity_rate >= 95 else "yellow" if validity_rate >= 80 else "red"

        metric_table.add_row(
            config['description'],
            f"[{extraction_style}]{extraction_rate:.1f}%[/{extraction_style}]",
            f"[{validity_style}]{validity_rate:.1f}%[/{validity_style}]",
            status
        )

    console.print(metric_table)

    # Overall accuracy assessment
    avg_extraction = sum(summary.metric_extraction_rates.values()) / len(summary.metric_extraction_rates) if summary.metric_extraction_rates else 0
    avg_validity = sum(summary.metric_validity_rates.values()) / len(summary.metric_validity_rates) if summary.metric_validity_rates else 0

    console.print(f"\n[bold]Overall Extraction Rate:[/bold] {avg_extraction:.1f}%")
    console.print(f"[bold]Overall Validity Rate:[/bold] {avg_validity:.1f}%")

    if avg_extraction >= 50 and avg_validity >= 95:
        console.print("\n[bold green]✓ PASS: Extraction accuracy meets 95% threshold[/bold green]")
    else:
        console.print("\n[bold red]✗ FAIL: Extraction accuracy below 95% threshold[/bold red]")

    # Common errors
    if summary.common_errors:
        console.print("\n[bold]Common Errors:[/bold]")
        for error, count in sorted(summary.common_errors.items(), key=lambda x: -x[1])[:5]:
            console.print(f"  [{count}x] {error}")

    # Detailed failures (if few)
    failed = [r for r in summary.results if not r.success]
    if failed and len(failed) <= 10:
        console.print("\n[bold]Failed Filings:[/bold]")
        for r in failed:
            console.print(f"  - {r.company[:40]} (CIK: {r.cik}): {r.error}")


def export_results(summary: ValidationSummary, output_path: str):
    """Export detailed results to CSV."""
    import csv

    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)

        # Header
        headers = ['CIK', 'Company', 'Filing Date', 'ABS Type', 'Success', 'Error', 'Tables', 'Labeled Tables']
        for metric_name in METRICS_CONFIG.keys():
            headers.extend([f'{metric_name}_extracted', f'{metric_name}_valid', f'{metric_name}_value'])
        writer.writerow(headers)

        # Data rows
        for r in summary.results:
            row = [r.cik, r.company, r.filing_date, r.abs_type, r.success, r.error or '', r.num_tables, r.num_labeled_tables]
            for metric_name in METRICS_CONFIG.keys():
                m = r.metrics.get(metric_name, MetricValidation())
                row.extend([m.extracted, m.valid, m.value])
            writer.writerow(row)

    console.print(f"\n[dim]Detailed results exported to: {output_path}[/dim]")


def main():
    parser = argparse.ArgumentParser(description='Validate DistributionReport extraction accuracy')
    parser.add_argument('--sample-size', type=int, default=50, help='Number of filings to test')
    parser.add_argument('--output', type=str, help='Export detailed results to CSV')
    args = parser.parse_args()

    console.print(f"[bold]Sampling {args.sample_size} diverse 10-D filings...[/bold]")

    # Get sample
    sample = get_diverse_sample(args.sample_size)
    console.print(f"[dim]Found {len(sample)} unique issuers to test[/dim]\n")

    # Validate each filing
    results = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Validating filings...", total=len(sample))

        for company, cik in sample:
            progress.update(task, description=f"Testing {company[:30]}...")
            result = validate_filing(cik, company)
            results.append(result)
            progress.advance(task)

    # Compute and print summary
    summary = compute_summary(results)
    print_summary(summary)

    # Export if requested
    if args.output:
        export_results(summary, args.output)

    # Return exit code based on accuracy
    avg_validity = sum(summary.metric_validity_rates.values()) / len(summary.metric_validity_rates) if summary.metric_validity_rates else 0
    return 0 if avg_validity >= 95 else 1


if __name__ == '__main__':
    sys.exit(main())
