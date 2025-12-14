"""
Rich console rendering for Schedule 13D and Schedule 13G filings.

This module provides beautiful terminal output for beneficial ownership reports
using the Rich library.
"""
from typing import TYPE_CHECKING

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from edgar.beneficial_ownership.schedule13 import Schedule13D, Schedule13G

__all__ = ['render_schedule13d', 'render_schedule13g']


def render_schedule13d(schedule: 'Schedule13D') -> Panel:
    """
    Render Schedule 13D for Rich console display.

    Args:
        schedule: Schedule13D instance

    Returns:
        Rich Panel containing the formatted display
    """
    # Header information
    header = Table.grid(padding=(0, 1))
    header.add_column(style="bold blue")
    header.add_column()

    amendment_text = ' (Amendment)' if schedule.is_amendment else ''
    header.add_row("Form:", f"Schedule 13D{amendment_text}")
    header.add_row("Filing Date:", str(schedule.filing_date))
    header.add_row("Event Date:", schedule.date_of_event)
    header.add_row("Issuer:", f"{schedule.issuer_info.name} ({schedule.issuer_info.cik})")
    header.add_row("Security:", schedule.security_info.title)
    header.add_row("CUSIP:", schedule.security_info.cusip)

    # Aggregate ownership
    header.add_row("Total Shares:", f"{schedule.total_shares:,}")
    header.add_row("Total Percent:", f"{schedule.total_percent:.2f}%")

    elements = [header, Text()]

    # Reporting Persons table
    persons_table = Table(
        title="Reporting Persons",
        box=box.SIMPLE,
        show_header=True,
        header_style="bold magenta"
    )
    persons_table.add_column("Name", style="cyan")
    persons_table.add_column("CIK", style="dim")
    persons_table.add_column("Shares", justify="right", style="green")
    persons_table.add_column("Percent", justify="right", style="yellow")
    persons_table.add_column("Voting Power", justify="right")
    persons_table.add_column("Dispositive Power", justify="right")

    for person in schedule.reporting_persons:
        persons_table.add_row(
            person.name,
            person.cik or 'N/A',
            f"{person.aggregate_amount:,}",
            f"{person.percent_of_class:.2f}%",
            f"{person.total_voting_power:,}",
            f"{person.total_dispositive_power:,}"
        )

    elements.append(persons_table)

    # Purpose section (Item 4) - Most important for 13D
    if schedule.items and schedule.items.item4_purpose_of_transaction:
        purpose_panel = Panel(
            Text(schedule.items.item4_purpose_of_transaction, style="italic"),
            title="[bold yellow]Purpose of Transaction (Item 4)[/bold yellow]",
            border_style="yellow",
            padding=(1, 2)
        )
        elements.append(Text())
        elements.append(purpose_panel)

    # Source of Funds (Item 3)
    if schedule.items and schedule.items.item3_source_of_funds:
        elements.append(Text())
        elements.append(
            Panel(
                Text(schedule.items.item3_source_of_funds),
                title="[bold blue]Source of Funds (Item 3)[/bold blue]",
                border_style="blue",
                padding=(0, 1)
            )
        )

    # Signatures
    if schedule.signatures:
        signatures_table = Table(
            title="Signatures",
            box=box.SIMPLE,
            show_header=True,
            header_style="bold cyan"
        )
        signatures_table.add_column("Reporting Person", style="cyan")
        signatures_table.add_column("Signed By", style="white")
        signatures_table.add_column("Date", style="dim")

        for sig in schedule.signatures:
            signatures_table.add_row(
                sig.reporting_person or 'N/A',
                sig.signature or 'N/A',
                sig.date or 'N/A'
            )

        elements.append(Text())
        elements.append(signatures_table)

    # Wrap everything in a main panel
    return Panel(
        Group(*elements),
        title="[bold white on blue] Schedule 13D - Beneficial Ownership Report [/bold white on blue]",
        expand=False,
        border_style="blue"
    )


def render_schedule13g(schedule: 'Schedule13G') -> Panel:
    """
    Render Schedule 13G for Rich console display.

    Args:
        schedule: Schedule13G instance

    Returns:
        Rich Panel containing the formatted display
    """
    # Header information
    header = Table.grid(padding=(0, 1))
    header.add_column(style="bold blue")
    header.add_column()

    amendment_text = ' (Amendment)' if schedule.is_amendment else ''
    header.add_row("Form:", f"Schedule 13G{amendment_text}")
    header.add_row("Filing Date:", str(schedule.filing_date))
    header.add_row("Event Date:", schedule.event_date)
    header.add_row("Issuer:", f"{schedule.issuer_info.name} ({schedule.issuer_info.cik})")
    header.add_row("Security:", schedule.security_info.title)
    header.add_row("CUSIP:", schedule.security_info.cusip)

    if schedule.rule_designation:
        header.add_row("Rule:", schedule.rule_designation)

    # Aggregate ownership
    header.add_row("Total Shares:", f"{schedule.total_shares:,}")
    header.add_row("Total Percent:", f"{schedule.total_percent:.2f}%")
    header.add_row("Type:", "Passive Institutional Investor")

    elements = [header, Text()]

    # Reporting Persons table
    persons_table = Table(
        title="Reporting Persons",
        box=box.SIMPLE,
        show_header=True,
        header_style="bold green"
    )
    persons_table.add_column("Name", style="cyan")
    persons_table.add_column("Type", style="dim")
    persons_table.add_column("Shares", justify="right", style="green")
    persons_table.add_column("Percent", justify="right", style="yellow")
    persons_table.add_column("Voting Power", justify="right")
    persons_table.add_column("Dispositive Power", justify="right")

    for person in schedule.reporting_persons:
        persons_table.add_row(
            person.name,
            person.type_of_reporting_person or 'N/A',
            f"{person.aggregate_amount:,}",
            f"{person.percent_of_class:.2f}%",
            f"{person.total_voting_power:,}",
            f"{person.total_dispositive_power:,}"
        )

    elements.append(persons_table)

    # Certification (Item 10) for 13G
    if schedule.items and schedule.items.item10_certification:
        cert_panel = Panel(
            Text(schedule.items.item10_certification, style="dim italic"),
            title="[bold green]Passive Investor Certification (Item 10)[/bold green]",
            border_style="green",
            padding=(0, 1)
        )
        elements.append(Text())
        elements.append(cert_panel)

    # Signatures
    if schedule.signatures:
        signatures_table = Table(
            title="Signatures",
            box=box.SIMPLE,
            show_header=True,
            header_style="bold cyan"
        )
        signatures_table.add_column("Reporting Person", style="cyan")
        signatures_table.add_column("Signed By", style="white")
        signatures_table.add_column("Date", style="dim")

        for sig in schedule.signatures:
            signatures_table.add_row(
                sig.reporting_person or 'N/A',
                sig.signature or 'N/A',
                sig.date or 'N/A'
            )

        elements.append(Text())
        elements.append(signatures_table)

    # Wrap everything in a main panel
    return Panel(
        Group(*elements),
        title="[bold white on green] Schedule 13G - Passive Beneficial Ownership Report [/bold white on green]",
        expand=False,
        border_style="green"
    )
