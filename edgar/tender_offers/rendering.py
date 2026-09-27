"""
Rich console rendering for Schedule 14D-9 filings.

This module provides beautiful terminal output for tender offer
solicitation/recommendation statements using the Rich library.
"""

from typing import TYPE_CHECKING

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from edgar.tender_offers.schedule14d9 import Schedule14D9

__all__ = ["render_schedule14d9"]

_RECOMMENDATION_STYLE = {
    "accept": ("bold green", "✓ ACCEPT"),
    "reject": ("bold red", "✗ REJECT"),
    "neutral": ("bold yellow", "● NEUTRAL"),
    None: ("dim italic", "UNCLEAR"),
}


def render_schedule14d9(schedule: "Schedule14D9") -> Panel:
    """
    Render Schedule 14D-9 for Rich console display.

    Args:
        schedule: Schedule14D9 instance

    Returns:
        Rich Panel containing the formatted display
    """
    header = Table.grid(padding=(0, 1))
    header.add_column(style="bold blue")
    header.add_column()

    amendment_text = " (Amendment)" if schedule.is_amendment else ""
    header.add_row("Form:", f"SC 14D-9{amendment_text}")
    header.add_row("Filing Date:", str(schedule.filing_date))
    header.add_row("Subject Company:", f"{schedule.company_name} ({schedule.cik})")

    style, label = _RECOMMENDATION_STYLE[schedule.recommendation]
    header.add_row("Recommendation:", f"[{style}]{label}[/{style}]")

    if schedule.item4_text is None:
        # Amendment that didn't restate Item 4 -- the normal case for SC 14D9/A,
        # not a parsing failure. See Schedule14D9's class docstring.
        recommendation_body = Text(
            "Not restated in this amendment.",
            style="dim italic",
        )
    elif schedule.recommendation_text_truncated:
        recommendation_body = Text.from_markup(
            schedule.recommendation_text + " [dim italic](truncated -- see item4_text for the full section)[/dim italic]"
        )
    else:
        recommendation_body = Text(schedule.recommendation_text, style="italic")

    recommendation_panel = Panel(
        recommendation_body,
        title="[bold yellow]Recommendation Statement (Item 4)[/bold yellow]",
        border_style="yellow",
        padding=(1, 2),
    )

    return Panel(
        Group(header, Text(), recommendation_panel),
        title="[bold white on blue] Schedule 14D-9 - Solicitation/Recommendation Statement [/bold white on blue]",
        expand=False,
        border_style="blue",
    )
