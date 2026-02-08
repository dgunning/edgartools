"""Command-line interface for the Edgar test harness."""

import click
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from .storage import HarnessStorage
from .selectors import FilingSelector
from .runner import (
    ComparisonTestRunner,
    ValidationTestRunner,
    PerformanceTestRunner
)

console = Console()


@click.group()
@click.version_option(version='0.1.0')
def cli():
    """Edgar Test Harness - Validate EdgarTools across live SEC filings.

    A comprehensive testing system for validating EdgarTools functionality
    across real SEC filings with persistent result storage and analytics.
    """
    pass


@cli.command()
@click.option('--session', '-s', help='Session name (creates new if not exists)')
@click.option('--form', '-f', required=True, help='Form type (10-K, 8-K, 10-Q, etc.)')
@click.option('--sample', '-n', type=int, default=10, help='Sample size (default: 10)')
@click.option('--year', '-y', type=int, help='Year to sample from (default: current year)')
@click.option('--date-range', help='Date range (YYYY-MM-DD:YYYY-MM-DD)')
@click.option('--companies', help='Comma-separated ticker list')
@click.option('--test-type', '-t',
              type=click.Choice(['comparison', 'validation', 'performance']),
              default='validation',
              help='Type of test to run (default: validation)')
@click.option('--db-path', type=click.Path(), help='Custom database path')
def run(session, form, sample, year, date_range, companies, test_type, db_path):
    """Run tests on selected SEC filings.

    Examples:

      \b
      # Run validation on 20 random 10-K filings from 2024
      edgar-test run --form 10-K --sample 20 --year 2024

      \b
      # Test specific companies
      edgar-test run --form 10-Q --companies AAPL,MSFT,GOOGL

      \b
      # Test filings in a date range
      edgar-test run --form 8-K --date-range 2024-01-01:2024-03-31
    """
    # Initialize storage
    storage_path = Path(db_path) if db_path else None
    storage = HarnessStorage(storage_path)

    # Create or get session
    if session:
        # Try to find existing session by name
        sessions = storage.list_sessions(limit=100)
        session_obj = next((s for s in sessions if s.name == session), None)
        if not session_obj:
            session_obj = storage.create_session(
                name=session,
                description=f"{form} {test_type} tests"
            )
            console.print(f"[green]Created new session:[/green] {session}")
        else:
            console.print(f"[blue]Using existing session:[/blue] {session}")
    else:
        session_name = f"{form} {test_type} {datetime.now():%Y-%m-%d %H:%M}"
        session_obj = storage.create_session(name=session_name)
        console.print(f"[green]Created session:[/green] {session_name}")

    # Select filings
    console.print(f"\n[bold]Selecting {form} filings...[/bold]")

    try:
        if date_range:
            start, end = date_range.split(':')
            filings = FilingSelector.by_date_range(form, start, end, sample)
        elif companies:
            company_list = [c.strip() for c in companies.split(',')]
            filings = FilingSelector.by_company_list(company_list, form, latest_n=1)
        else:
            current_year = year if year else datetime.now().year
            filings = FilingSelector.by_random_sample(form, current_year, sample)

        console.print(f"[green]Selected {len(filings)} filings[/green]")

    except Exception as e:
        console.print(f"[red]Error selecting filings:[/red] {e}")
        return

    if not filings:
        console.print("[yellow]No filings found matching criteria[/yellow]")
        return

    # Create test run
    config = {
        'form': form,
        'sample': sample,
        'year': year,
        'date_range': date_range,
        'companies': companies,
        'test_type': test_type
    }

    run_obj = storage.create_run(
        session_id=session_obj.id,
        name=f"{form} {test_type}",
        test_type=test_type,
        config=config
    )

    console.print(f"\n[bold]Starting {test_type} tests on {len(filings)} filings[/bold]\n")

    # Execute tests based on type
    try:
        if test_type == 'comparison':
            runner = ComparisonTestRunner(storage)
            # Simple comparison: compare form field with itself (demo)
            results = runner.run(
                run_obj,
                filings,
                old_func=lambda f: f.form,
                new_func=lambda f: f.form
            )
        elif test_type == 'validation':
            runner = ValidationTestRunner(storage)
            # Basic validators
            validators = [
                lambda f: {'passed': f.form == form, 'message': 'Form type matches'},
                lambda f: {'passed': len(f.accession_no) > 0, 'message': 'Has accession number'},
                lambda f: {'passed': len(f.company) > 0, 'message': 'Has company name'}
            ]
            results = runner.run(run_obj, filings, validators)
        else:  # performance
            runner = PerformanceTestRunner(storage)
            results = runner.run(
                run_obj,
                filings,
                test_func=lambda f: f.form,
                thresholds={'max_duration_ms': 1000}
            )

    except Exception as e:
        console.print(f"\n[red]Error during test execution:[/red] {e}")
        storage.update_run_status(run_obj.id, 'failed')
        return

    # Update run status
    storage.update_run_status(run_obj.id, 'completed', datetime.now())

    # Display results summary
    console.print()
    display_results_summary(results, run_obj.id)


@cli.command()
@click.option('--session', '-s', type=int, help='Session ID')
@click.option('--run', '-r', type=int, help='Run ID')
@click.option('--limit', '-l', type=int, default=20, help='Limit results (default: 20)')
@click.option('--db-path', type=click.Path(), help='Custom database path')
def show(session, run, limit, db_path):
    """Show test results, runs, or sessions.

    Examples:

      \b
      # Show all sessions
      edgar-test show

      \b
      # Show runs in a session
      edgar-test show --session 1

      \b
      # Show results from a specific run
      edgar-test show --run 5 --limit 50
    """
    storage_path = Path(db_path) if db_path else None
    storage = HarnessStorage(storage_path)

    if run:
        # Show results for specific run
        run_obj = storage.get_run(run)
        if not run_obj:
            console.print(f"[red]Run {run} not found[/red]")
            return

        results = storage.get_results(run)
        display_run_details(run_obj, results, limit)

    elif session:
        # Show runs in session
        session_obj = storage.get_session(session)
        if not session_obj:
            console.print(f"[red]Session {session} not found[/red]")
            return

        runs = storage.list_runs(session_id=session, limit=limit)
        display_runs_table(runs, session_obj)

    else:
        # Show all sessions
        sessions = storage.list_sessions(limit=limit)
        display_sessions_table(sessions)


@cli.command()
@click.option('--run1', '-r1', type=int, required=True, help='First run ID')
@click.option('--run2', '-r2', type=int, required=True, help='Second run ID')
@click.option('--db-path', type=click.Path(), help='Custom database path')
def compare(run1, run2, db_path):
    """Compare two test runs.

    Example:

      \b
      edgar-test compare --run1 5 --run2 6
    """
    storage_path = Path(db_path) if db_path else None
    storage = HarnessStorage(storage_path)

    comparison = storage.compare_runs(run1, run2)
    display_comparison(comparison)


@cli.command()
@click.option('--test-name', '-t', required=True, help='Test name to analyze')
@click.option('--limit', '-l', type=int, default=20, help='Number of runs (default: 20)')
@click.option('--db-path', type=click.Path(), help='Custom database path')
def trends(test_name, limit, db_path):
    """Show historical trends for a test.

    Example:

      \b
      edgar-test trends --test-name "10-K validation" --limit 30
    """
    storage_path = Path(db_path) if db_path else None
    storage = HarnessStorage(storage_path)

    trend_data = storage.get_trends(test_name, limit)

    if not trend_data:
        console.print(f"[yellow]No trend data found for test: {test_name}[/yellow]")
        return

    display_trends(test_name, trend_data)


# Display helper functions

def display_results_summary(results, run_id=None):
    """Display rich formatted summary of test results."""
    total = len(results)
    passed = sum(1 for r in results if r.status == 'pass')
    failed = sum(1 for r in results if r.status == 'fail')
    errors = sum(1 for r in results if r.status == 'error')
    skipped = sum(1 for r in results if r.status == 'skip')

    # Create summary panel
    summary_text = f"""[bold]Results Summary[/bold]

Total Tests:  {total}
[green]✓ Passed:[/green]   {passed}
[red]✗ Failed:[/red]   {failed}
[yellow]⚠ Errors:[/yellow]   {errors}
[blue]⊘ Skipped:[/blue]  {skipped}

Success Rate: [bold]{passed/total*100:.1f}%[/bold]"""

    if run_id:
        summary_text += f"\n\nRun ID: {run_id}"

    panel = Panel(
        summary_text,
        title="Test Results",
        border_style="green" if failed == 0 and errors == 0 else "yellow",
        box=box.ROUNDED
    )

    console.print(panel)


def display_run_details(run_obj, results, limit):
    """Display detailed results for a run."""
    console.print(f"\n[bold]Run Details:[/bold] {run_obj.name} (ID: {run_obj.id})")
    console.print(f"Type: {run_obj.test_type}")
    console.print(f"Started: {run_obj.started_at}")
    console.print(f"Status: {run_obj.status}")

    if results:
        console.print(f"\n[bold]Results ({len(results)} total, showing {min(limit, len(results))}):[/bold]\n")

        table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
        table.add_column("Company", style="dim", no_wrap=True)
        table.add_column("Form", justify="center")
        table.add_column("Date")
        table.add_column("Status", justify="center")
        table.add_column("Duration (ms)", justify="right")

        for result in results[:limit]:
            status_style = {
                'pass': '[green]✓ PASS[/green]',
                'fail': '[red]✗ FAIL[/red]',
                'error': '[yellow]⚠ ERROR[/yellow]',
                'skip': '[blue]⊘ SKIP[/blue]'
            }.get(result.status, result.status)

            duration_str = f"{result.duration_ms:.1f}" if result.duration_ms else "-"

            table.add_row(
                result.filing_company[:30],
                result.filing_form,
                result.filing_date,
                status_style,
                duration_str
            )

        console.print(table)

        # Show summary
        display_results_summary(results, run_obj.id)
    else:
        console.print("[yellow]No results found for this run[/yellow]")


def display_runs_table(runs, session_obj=None):
    """Display table of test runs."""
    if session_obj:
        console.print(f"\n[bold]Session:[/bold] {session_obj.name} (ID: {session_obj.id})")
        console.print(f"Created: {session_obj.created_at}\n")

    if not runs:
        console.print("[yellow]No runs found[/yellow]")
        return

    table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
    table.add_column("ID", justify="right", style="cyan")
    table.add_column("Name")
    table.add_column("Type", justify="center")
    table.add_column("Started")
    table.add_column("Status", justify="center")

    for run in runs:
        status_style = {
            'running': '[yellow]RUNNING[/yellow]',
            'completed': '[green]COMPLETED[/green]',
            'failed': '[red]FAILED[/red]'
        }.get(run.status, run.status)

        table.add_row(
            str(run.id),
            run.name,
            run.test_type,
            str(run.started_at)[:19] if run.started_at else "-",
            status_style
        )

    console.print(table)


def display_sessions_table(sessions):
    """Display table of sessions."""
    if not sessions:
        console.print("[yellow]No sessions found[/yellow]")
        return

    console.print("\n[bold]Test Sessions[/bold]\n")

    table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
    table.add_column("ID", justify="right", style="cyan")
    table.add_column("Name")
    table.add_column("Created")
    table.add_column("Description", style="dim")

    for session in sessions:
        table.add_row(
            str(session.id),
            session.name,
            str(session.created_at)[:19] if session.created_at else "-",
            session.description or ""
        )

    console.print(table)


def display_comparison(comparison):
    """Display side-by-side comparison of two runs."""
    console.print("\n[bold]Run Comparison[/bold]\n")

    table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
    table.add_column("Metric")
    table.add_column("Run 1", justify="right")
    table.add_column("Run 2", justify="right")
    table.add_column("Difference", justify="right")

    run1 = comparison['run1']
    run2 = comparison['run2']

    metrics = [
        ('Total Tests', 'total'),
        ('Passed', 'passed'),
        ('Failed', 'failed'),
        ('Errors', 'errors')
    ]

    for label, key in metrics:
        val1 = run1.get(key, 0)
        val2 = run2.get(key, 0)
        diff = val2 - val1

        diff_str = f"{diff:+d}" if diff != 0 else "0"
        if key == 'passed' and diff > 0:
            diff_str = f"[green]{diff_str}[/green]"
        elif key in ('failed', 'errors') and diff > 0:
            diff_str = f"[red]{diff_str}[/red]"

        table.add_row(label, str(val1), str(val2), diff_str)

    console.print(table)


def display_trends(test_name, trend_data):
    """Display trend chart for a test."""
    console.print(f"\n[bold]Trends for:[/bold] {test_name}\n")

    table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
    table.add_column("Run ID", justify="right")
    table.add_column("Date")
    table.add_column("Success Rate", justify="right")
    table.add_column("Avg Duration (ms)", justify="right")
    table.add_column("Total Tests", justify="right")

    for trend in reversed(trend_data):  # Show oldest first
        success_rate = trend['success_rate'] * 100
        rate_str = f"{success_rate:.1f}%"

        # Color code success rate
        if success_rate >= 90:
            rate_str = f"[green]{rate_str}[/green]"
        elif success_rate >= 70:
            rate_str = f"[yellow]{rate_str}[/yellow]"
        else:
            rate_str = f"[red]{rate_str}[/red]"

        table.add_row(
            str(trend['run_id']),
            trend['date'][:19] if trend['date'] else "-",
            rate_str,
            f"{trend.get('avg_duration_ms', 0):.1f}",
            str(trend['total'])
        )

    console.print(table)


if __name__ == '__main__':
    cli()
