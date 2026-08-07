"""Presentation layer for the crowdfunding ``Offering`` lifecycle view.

``OfferingRenderMixin`` holds the token-efficient ``to_context()`` report and the
Rich visualization (``__rich__`` / ``__repr__``), extracted from ``Offering`` so
``campaign.py`` carries only the lifecycle/property surface. The mixin accesses
everything through ``self`` (properties and methods defined on ``Offering``), so
it needs no import of ``Offering`` and introduces no import cycle.
"""
from __future__ import annotations

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table


class OfferingRenderMixin:
    """Reporting + Rich rendering for ``Offering`` (mixed into the class)."""

    # =========================================================================
    # AI-Native Reporting (to_context Pattern)
    # =========================================================================

    def to_context(self, detail: str = 'standard') -> str:
        """
        Returns token-efficient, AI-optimized text representation of campaign lifecycle.

        Follows the AI-native to_context() pattern for minimal token usage while
        providing complete context for LLM analysis.

        Args:
            detail: Level of detail to include:
                - 'minimal': ~300 tokens, essential info only
                - 'standard': ~700 tokens, most important data (default)
                - 'full': ~1500 tokens, comprehensive view

        Returns:
            Formatted string suitable for AI context windows

        Example:
            >>> campaign.to_context()  # Standard detail
            >>> campaign.to_context(detail='minimal')  # Compact
            >>> campaign.to_context(detail='full')  # Everything
        """
        lines = []

        # Header (always included)
        lines.append("="*80)
        lines.append("CROWDFUNDING CAMPAIGN LIFECYCLE")
        lines.append("="*80)
        lines.append("")

        # Campaign identification
        lines.append(f"CAMPAIGN: {self.company.name}")
        lines.append(f"  CIK: {self.company.cik}")
        lines.append(f"  File Number: {self.file_number}")
        lines.append(f"  Status: {self.current_status}")
        lines.append("")

        # Timeline summary
        lines.append("TIMELINE:")
        if self.launch_date:
            lines.append(f"  Launched: {self.launch_date}")
            lines.append(f"  Latest Activity: {self.latest_activity_date}")
            lines.append(f"  Duration: {self.days_since_launch} days")
        lines.append(f"  Total Filings: {len(self.all_filings)}")
        lines.append("")

        # Lifecycle stages (standard+)
        if detail in ['standard', 'full']:
            lines.append("LIFECYCLE STAGES:")
            lines.append(f"  Initial Offering (C): {len(self.filings_by_stage['initial'])} filing(s)")
            lines.append(f"  Amendments (C/A): {len(self.filings_by_stage['amendment'])} filing(s)")
            lines.append(f"  Progress Updates (C-U): {len(self.filings_by_stage['update'])} filing(s)")
            lines.append(f"  Annual Reports (C-AR): {len(self.filings_by_stage['report'])} filing(s)")
            lines.append(f"  Termination (C-TR): {len(self.filings_by_stage['termination'])} filing(s)")
            lines.append("")

        # Initial offering details (standard+)
        if detail in ['standard', 'full'] and self.initial_offering:
            initial = self.initial_offering
            lines.append("INITIAL OFFERING:")

            if initial.offering_information:
                offer = initial.offering_information
                lines.append(f"  Security: {offer.security_description}")

                if offer.target_amount and offer.maximum_offering_amount:
                    if detail == 'full':
                        lines.append(f"  Target: ${offer.target_amount:,.0f}")
                        lines.append(f"  Maximum: ${offer.maximum_offering_amount:,.0f}")
                    else:
                        lines.append(f"  Target: ${offer.target_amount:,.0f} → Max: ${offer.maximum_offering_amount:,.0f}")

                if offer.deadline_date:
                    days = initial.days_to_deadline
                    if days is not None:
                        if days > 0:
                            status_str = f"{days} days remaining"
                        elif days == 0:
                            status_str = "expires today"
                        else:
                            status_str = f"expired {abs(days)} days ago"
                        lines.append(f"  Deadline: {offer.deadline_date} ({status_str})")

            if detail == 'full' and initial.issuer_information.funding_portal:
                portal = initial.issuer_information.funding_portal
                lines.append(f"  Portal: {portal.name}")

            lines.append("")

        # Latest financials (standard+)
        if detail in ['standard', 'full']:
            fin = self.latest_financials()
            if fin:
                lines.append("LATEST FINANCIALS:")

                if fin.total_asset_most_recent_fiscal_year > 0:
                    lines.append(f"  Assets: ${fin.total_asset_most_recent_fiscal_year:,.0f}")

                if fin.is_pre_revenue:
                    lines.append("  Revenue: $0 (pre-revenue)")
                else:
                    lines.append(f"  Revenue: ${fin.revenue_most_recent_fiscal_year:,.0f}")

                ni = fin.net_income_most_recent_fiscal_year
                if ni < 0:
                    lines.append(f"  Net Income: -${abs(ni):,.0f} (loss)")
                else:
                    lines.append(f"  Net Income: ${ni:,.0f}")

                if detail == 'full':
                    lines.append(f"  Employees: {fin.current_employees}")

                lines.append("")

        # Full timeline (full only)
        if detail == 'full':
            lines.append("COMPLETE TIMELINE:")
            for event in self.timeline():
                lines.append(f"  {event['date']} - {event['form']}: {event['description']}")
            lines.append("")

        return "\n".join(lines)

    # =========================================================================
    # Rich Visualization
    # =========================================================================

    def __rich__(self) -> Panel:
        """Create Rich visualization of campaign lifecycle"""
        # Timeline table
        timeline_table = Table(
            "Date", "Form", "Stage", "Description",
            title="Campaign Timeline",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan"
        )

        for event in self.timeline():
            timeline_table.add_row(
                str(event['date']),
                event['form'],
                event['stage'].capitalize(),
                event['description']
            )

        # Metrics table
        metrics_table = Table(
            "Metric", "Value",
            box=box.SIMPLE,
            show_header=False
        )
        if self.launch_date:
            metrics_table.add_row("Launch Date", str(self.launch_date))
        metrics_table.add_row("Days Active", str(self.days_since_launch))
        metrics_table.add_row("Total Filings", str(len(self.all_filings)))
        metrics_table.add_row("Current Status", self.current_status)

        # Stage breakdown table
        stages_table = Table(
            "Stage", "Count",
            box=box.SIMPLE,
            show_header=True
        )
        for stage, filings in self.filings_by_stage.items():
            if filings:  # Only show stages with filings
                stages_table.add_row(stage.capitalize(), str(len(filings)))

        # Combine into panel
        return Panel(
            Group(
                Panel(metrics_table, title="📊 Metrics", border_style="green"),
                Panel(stages_table, title="📁 Lifecycle Stages", border_style="blue"),
                timeline_table
            ),
            title=f"[bold cyan]Offering Campaign: {self.company.name}[/bold cyan]",
            subtitle=f"File Number: {self.file_number}",
            border_style="cyan"
        )

    def __repr__(self) -> str:
        from edgar.richtools import repr_rich
        return repr_rich(self.__rich__())
