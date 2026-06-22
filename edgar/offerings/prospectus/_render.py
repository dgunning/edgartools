"""Presentation layer for Prospectus424B.

A mixin holding the AI-context (`to_context`) and Rich rendering for the main
document object, kept separate from the extraction/logic in ``document.py``.
The methods only read attributes of the host ``Prospectus424B`` instance.
"""

from __future__ import annotations

from functools import cached_property
from typing import Optional

from rich import box
from rich.console import Group, Text
from rich.panel import Panel
from rich.table import Table

from edgar.richtools import repr_rich


class ProspectusRenderMixin:
    """Rich display + LLM context for :class:`Prospectus424B`."""

    # ------------------------------------------------------------------
    # AI context
    # ------------------------------------------------------------------

    def to_context(self, detail: str = 'standard') -> str:
        """Returns AI-optimized prospectus context for language models.

        Args:
            detail: Level of detail - 'minimal', 'standard', or 'full'

        Returns:
            Markdown-KV formatted context string optimized for LLMs
        """
        cp = self._cover_page
        lines = []

        lines.append(f"PROSPECTUS: {self.company} ({self.form})")
        lines.append("")
        lines.append(f"Filed: {self.filing_date}")
        lines.append(f"Offering Type: {self._offering_type.display_name}")

        if cp.security_description:
            lines.append(f"Security: {cp.security_description[:100]}")
        if cp.offering_amount:
            lines.append(f"Offering Amount: {cp.offering_amount}")
        if cp.offering_price:
            lines.append(f"Offering Price: {cp.offering_price}")
        if cp.exchange_ticker:
            lines.append(f"Ticker: {cp.exchange_ticker}")
        if cp.registration_number:
            lines.append(f"Registration No.: {cp.registration_number}")

        flags = []
        if cp.is_atm:
            flags.append("ATM")
        if cp.is_preliminary:
            flags.append("PRELIMINARY")
        if cp.is_supplement:
            flags.append("Supplement")
        if self.is_amendment:
            flags.append("AMENDMENT")
        if flags:
            lines.append(f"Status: {' | '.join(flags)}")

        if detail == 'minimal':
            return "\n".join(lines)

        # Standard: add pricing and underwriting summaries
        if self.pricing and self.pricing.columns:
            lines.append("")
            lines.append("PRICING:")
            for col in self.pricing.columns:
                label = col.column_label or "Value"
                parts = []
                if col.offering_price:
                    parts.append(f"Price: {col.offering_price}")
                if col.proceeds:
                    parts.append(f"Proceeds: {col.proceeds}")
                if parts:
                    lines.append(f"  {label}: {', '.join(parts)}")

        uw = self.underwriting
        if uw and uw.underwriters:
            lines.append("")
            lines.append(f"UNDERWRITING ({uw.fee_type.replace('_', ' ').title()}):")
            for entry in uw.underwriters[:5]:
                lines.append(f"  - {entry.name}")
            if len(uw.underwriters) > 5:
                lines.append(f"  ... +{len(uw.underwriters) - 5} more")

        lc = self.lifecycle
        if lc:
            lines.append("")
            td_num = lc.takedown_number
            if td_num is not None:
                latest = " (latest)" if lc.is_latest_takedown else ""
                lines.append(f"Shelf Position: Takedown #{td_num} of {lc.total_takedowns}{latest}")
            if lc.shelf_expires:
                remaining = lc.days_to_expiry
                if remaining is not None and remaining > 0:
                    lines.append(f"Shelf Expires: {lc.shelf_expires} ({remaining} days remaining)")
                elif remaining is not None:
                    lines.append(f"Shelf Expires: {lc.shelf_expires} (EXPIRED)")

        if detail == 'full':
            lines.append("")
            lines.append("AVAILABLE ACTIONS:")
            lines.append("  - .cover_page -> CoverPageData with all extracted fields")
            lines.append("  - .pricing -> PricingData (offering price, fee, proceeds)")
            lines.append("  - .underwriting -> UnderwritingInfo (syndicate details)")
            lines.append("  - .offering_terms -> OfferingTerms (shares, warrants, use of proceeds)")
            lines.append("  - .selling_stockholders -> SellingStockholdersData")
            lines.append("  - .structured_note_terms -> StructuredNoteTerms (for 424B2)")
            lines.append("  - .dilution -> DilutionData")
            lines.append("  - .capitalization -> CapitalizationData")
            lines.append("  - .filing_fees -> FilingFeesData (from XBRL exhibit)")
            lines.append("  - .lifecycle -> ShelfLifecycle (takedown position, expiry, timeline)")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Rich display
    # ------------------------------------------------------------------

    @cached_property
    def _cover_table(self) -> Table:
        cp = self._cover_page
        t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        t.add_column("field", style="bold deep_sky_blue1", min_width=22)
        t.add_column("value")

        t.add_row("Form", self.form)
        t.add_row("Offering Type", self._offering_type.display_name)
        if cp.security_description:
            t.add_row("Security", cp.security_description[:100])
        if cp.offering_amount:
            t.add_row("Offering Amount", cp.offering_amount)
        if cp.offering_price:
            t.add_row("Offering Price", cp.offering_price)
        if cp.exchange_ticker:
            t.add_row("Ticker", cp.exchange_ticker)
        if cp.registration_number:
            t.add_row("Registration No.", cp.registration_number)
        if cp.base_prospectus_date:
            t.add_row("Base Prospectus", f"To Prospectus dated {cp.base_prospectus_date}")

        flags = []
        if cp.is_atm:
            flags.append("[green]ATM[/green]")
        if cp.is_preliminary:
            flags.append("[yellow]PRELIMINARY[/yellow]")
        if cp.is_supplement:
            flags.append("Supplement")
        if self.is_amendment:
            flags.append("[red]AMENDMENT[/red]")
        if flags:
            t.add_row("Status", " | ".join(flags))

        return t

    @cached_property
    def _pricing_table(self) -> Optional[Table]:
        """Rich Table for pricing data, or None if not available."""
        if not self.pricing or not self.pricing.columns:
            return None
        t = Table(box=box.SIMPLE, padding=(0, 1), title="Pricing")
        t.add_column("", style="bold")
        for col in self.pricing.columns:
            t.add_column(col.column_label or "Value", justify="right", style="deep_sky_blue1")
        if any(c.offering_price for c in self.pricing.columns):
            t.add_row("Offering Price", *[c.offering_price or "" for c in self.pricing.columns])
        if any(c.fee_or_discount for c in self.pricing.columns):
            fee_label = self.pricing.fee_type or "Fee"
            fee_label = fee_label.replace('_', ' ').title()
            t.add_row(fee_label, *[c.fee_or_discount or "" for c in self.pricing.columns])
        if any(c.proceeds for c in self.pricing.columns):
            t.add_row("Proceeds", *[c.proceeds or "" for c in self.pricing.columns])
        return t

    @cached_property
    def _underwriting_table(self) -> Optional[Table]:
        """Rich Table for underwriting info."""
        uw = self.underwriting
        if not uw or not uw.underwriters:
            return None
        t = Table(box=box.SIMPLE, padding=(0, 1), title="Underwriting")
        t.add_column("Name", style="bold")
        t.add_column("Allocation", justify="right", style="deep_sky_blue1")
        for entry in uw.underwriters[:10]:
            t.add_row(entry.name, entry.shares_allocated or "")
        if len(uw.underwriters) > 10:
            t.add_row(f"... +{len(uw.underwriters) - 10} more", "")
        return t

    def __rich__(self):
        title = f"{self.company}  {self.filing_date}"
        subtitle = f"{self.form}  {self._offering_type.display_name}"

        renderables = [self._cover_table]

        pt = self._pricing_table
        if pt is not None:
            renderables.append(Text(""))
            renderables.append(pt)

        ut = self._underwriting_table
        if ut is not None:
            renderables.append(Text(""))
            renderables.append(ut)

        return Panel(
            Group(*renderables),
            title=f"[bold]{title}[/bold]",
            subtitle=subtitle,
            box=box.ROUNDED,
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __str__(self):
        return (
            f"Prospectus424B("
            f"form={self.form!r}, "
            f"company={self.company!r}, "
            f"offering_type={self._offering_type.value!r}, "
            f"date={self.filing_date!r})"
        )
