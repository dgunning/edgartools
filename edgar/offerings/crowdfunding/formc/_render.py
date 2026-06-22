"""Presentation layer for :class:`~edgar.offerings.crowdfunding.formc.core.FormC`.

Extracted from the FormC class to keep ``core.py`` focused on parsing/logic.
``FormC`` inherits these methods via ``FormCRenderMixin`` — behaviour is
identical; only the file location changed. Methods reference ``self`` only
(``self.format_date`` rather than ``FormC.format_date``) so the mixin needs no
import of FormC.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from rich import box
from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel
from rich.table import Column, Table
from rich.text import Text

from edgar.display.formatting import yes_no
from edgar.reference import states
from edgar.richtools import repr_rich


class FormCRenderMixin:
    """Rich + AI-context rendering for FormC."""

    def to_context(self, detail: str = 'standard', filing_date: Optional[date] = None) -> str:
        """
        Returns a token-efficient, AI-optimized text representation of the Form C filing.

        This method provides a compact alternative to __rich__() that is optimized for
        LLM context windows. It includes computed fields (status, days remaining, ratios)
        and only displays populated fields.

        Args:
            detail: Level of detail to include:
                - 'minimal': ~100-200 tokens, essential fields only
                - 'standard': ~300-500 tokens, most important data (default)
                - 'full': ~600-1000 tokens, comprehensive view
            filing_date: Optional filing date to include in header

        Returns:
            Formatted string suitable for AI context

        Example:
            >>> formc.to_context()  # Standard detail
            >>> formc.to_context(detail='minimal')  # Minimal tokens
            >>> formc.to_context(detail='full')  # Everything
        """
        lines = []

        # Header (always included)
        header = f"FORM {self.form} - {self.description.upper()}"
        if filing_date:
            header += f" (Filed: {filing_date})"
        lines.append(header)
        lines.append("")

        # Issuer (always included)
        lines.append(f"ISSUER: {self.issuer_information.name}")
        if detail in ['standard', 'full']:
            lines.append(f"  CIK: {self.filer_information.cik}")
            lines.append(f"  Legal: {self.issuer_information.jurisdiction} "
                        f"{self.issuer_information.legal_status}")
            if self.issuer_information.website:
                lines.append(f"  Website: {self.issuer_information.website}")
            if detail == 'full' and self.issuer_information.address:
                city = self.issuer_information.address.city
                state = self.issuer_information.address.state_or_country
                lines.append(f"  Location: {city}, {state}")

        # Funding Portal (standard+)
        if self.issuer_information.funding_portal and detail in ['standard', 'full']:
            portal = self.issuer_information.funding_portal
            lines.append(f"\nFUNDING PORTAL: {portal.name}")
            if detail == 'full':
                lines.append(f"  CIK: {portal.cik} | CRD: {portal.crd or 'N/A'}")
            lines.append(f"  File Number: {portal.file_number}")

        # Offering (if present)
        if self.offering_information:
            lines.append("\nOFFERING:")

            # Security description
            lines.append(f"  Security: {self.offering_information.security_description}")

            # Amounts
            if self.offering_information.target_amount and self.offering_information.maximum_offering_amount:
                target = self.offering_information.target_amount
                max_amt = self.offering_information.maximum_offering_amount
                if detail == 'minimal':
                    # Compact format with K/M abbreviations
                    target_str = f"${target/1000:.0f}K" if target < 1000000 else f"${target/1000000:.1f}M"
                    max_str = f"${max_amt/1000:.0f}K" if max_amt < 1000000 else f"${max_amt/1000000:.1f}M"
                    lines.append(f"  Target: {target_str} → Max: {max_str}")
                else:
                    lines.append(f"  Target: ${target:,.0f} | Maximum: ${max_amt:,.0f}")
                    if self.offering_information.percent_to_maximum:
                        lines.append(f"  Target is {self.offering_information.percent_to_maximum:.0f}% of maximum")

            # Price and units (standard+)
            if detail in ['standard', 'full']:
                if self.offering_information.price_per_security:
                    price_str = f"${self.offering_information.price_per_security:,.2f}/unit"
                    if self.offering_information.number_of_securities:
                        price_str += f" | Units: {self.offering_information.number_of_securities:,}"
                    lines.append(f"  Price: {price_str}")

            # Deadline with computed days remaining
            if self.offering_information.deadline_date:
                days = self.days_to_deadline
                if days is not None:
                    if days > 0:
                        status = f"{days} days remaining"
                    elif days == 0:
                        status = "EXPIRES TODAY"
                    else:
                        status = f"EXPIRED ({abs(days)} days ago)"
                else:
                    status = ""

                if detail == 'minimal':
                    lines.append(f"  Deadline: {self.offering_information.deadline_date} ({status})")
                else:
                    lines.append(f"  Deadline: {self.offering_information.deadline_date}")
                    if status:
                        lines.append(f"  Status: {status}")

            # Over-subscription (full only)
            if detail == 'full' and self.offering_information.over_subscription_accepted == "Y":
                lines.append("  Over-subscription: Accepted")

            # Portal fees (full only)
            if detail == 'full' and self.offering_information.compensation_amount:
                lines.append(f"  Portal Fee: {self.offering_information.compensation_amount}")

        # Financials (if present)
        if self.annual_report_disclosure and detail in ['standard', 'full']:
            fin = self.annual_report_disclosure
            lines.append("\nFINANCIALS (Current vs Prior Year):")

            # Employees
            if detail == 'full':
                lines.append(f"  Employees: {fin.current_employees}")

            # Assets
            assets_curr = fin.total_asset_most_recent_fiscal_year
            assets_prior = fin.total_asset_prior_fiscal_year
            if assets_curr > 0:
                if assets_prior > 0 and fin.asset_growth_yoy is not None:
                    lines.append(f"  Assets: ${assets_curr:,.0f} "
                               f"({fin.asset_growth_yoy:+.0f}% from ${assets_prior:,.0f})")
                else:
                    lines.append(f"  Assets: ${assets_curr:,.0f}")

            # Cash
            if detail == 'full':
                cash_curr = fin.cash_equi_most_recent_fiscal_year
                if cash_curr > 0:
                    lines.append(f"  Cash: ${cash_curr:,.0f}")

            # Revenue status
            if fin.is_pre_revenue:
                lines.append("  Revenue: $0 (pre-revenue)")
            else:
                rev_curr = fin.revenue_most_recent_fiscal_year
                rev_prior = fin.revenue_prior_fiscal_year
                if fin.revenue_growth_yoy is not None and rev_prior > 0:
                    lines.append(f"  Revenue: ${rev_curr:,.0f} ({fin.revenue_growth_yoy:+.0f}% YoY)")
                else:
                    lines.append(f"  Revenue: ${rev_curr:,.0f}")

            # Net income
            ni_curr = fin.net_income_most_recent_fiscal_year
            ni_prior = fin.net_income_prior_fiscal_year
            if ni_curr < 0:
                if ni_prior < 0 and fin.burn_rate_change:
                    if fin.burn_rate_change < 0:
                        trend = "burn rate increasing"
                    else:
                        trend = "burn rate decreasing"
                    lines.append(f"  Net Income: ${ni_curr:,.0f} ({trend})")
                else:
                    lines.append(f"  Net Income: ${ni_curr:,.0f}")
            else:
                lines.append(f"  Net Income: ${ni_curr:,.0f}")

            # Debt
            total_debt = fin.total_debt_most_recent
            if total_debt > 0:
                debt_str = f"${total_debt:,.0f}"
                if detail == 'full':
                    debt_str += f" (short: ${fin.short_term_debt_most_recent_fiscal_year:,.0f}, "
                    debt_str += f"long: ${fin.long_term_debt_most_recent_fiscal_year:,.0f})"
                lines.append(f"  Total Debt: {debt_str}")

            # Debt-to-asset ratio (standard+)
            if fin.debt_to_asset_ratio is not None and detail in ['standard', 'full']:
                lines.append(f"  Debt-to-Asset Ratio: {fin.debt_to_asset_ratio:.0f}%")

        # Campaign status (always included)
        lines.append(f"\nCAMPAIGN STATUS: {self.campaign_status}")

        # Jurisdictions (full only)
        if self.annual_report_disclosure and detail == 'full':
            if self.annual_report_disclosure.is_offered_in_all_states:
                lines.append("  Offered in: All 50 states")
            else:
                num_states = len(self.annual_report_disclosure.offering_jurisdictions)
                lines.append(f"  Offered in: {num_states} jurisdictions")

        # Signatures (full only)
        if detail == 'full' and self.signature_info:
            num_signers = len(self.signature_info.signers)
            lines.append(f"\nSIGNATURES: {num_signers} officer{'s' if num_signers != 1 else ''}")
            if self.signature_info.issuer_signature:
                lines.append(f"  {self.signature_info.issuer_signature.title}: "
                           f"{self.signature_info.issuer_signature.signature}")

        # Available actions (standard+)
        if detail in ['standard', 'full']:
            lines.append("")
            lines.append("AVAILABLE ACTIONS:")
            lines.append("  - Use .get_offering() for complete campaign lifecycle")
            lines.append("  - Use .issuer for IssuerCompany information")
            if self.offering_information:
                lines.append("  - Use .offering_information for offering terms")
            if self.annual_report_disclosure:
                lines.append("  - Use .annual_report_disclosure for financial data")

        return "\n".join(lines)

    def __rich__(self):

        # Filer Panel
        filer_table = Table("Company", "CIK", box=box.SIMPLE)
        if self.filer_information.period:
            filer_table.add_column("Period")
            filer_table.add_row(self.filer_information.company.name, self.filer_information.cik,
                                self.format_date(self.filer_information.period))
        else:
            filer_table.add_row(self.filer_information.company.name, self.filer_information.cik)
        filer_panel = Panel(filer_table, title=Text("Filer", style="bold deep_sky_blue1"), box=box.ROUNDED)

        # Issuers
        issuer_table = Table(Column("Issuer", style="bold"), "Legal Status", "Incorporated", "Jurisdiction",
                             box=box.SIMPLE)
        issuer_table.add_row(self.issuer_information.name,
                             self.issuer_information.legal_status,
                             self.format_date(self.issuer_information.date_of_incorporation),
                             states.get(self.issuer_information.jurisdiction, self.issuer_information.jurisdiction))

        # Address Panel
        address_panel = Panel(
            Text(str(self.issuer_information.address)),
            title='\U0001F3E2 Business Address', width=40)

        # Address and website
        contact_columns = Columns([address_panel, Panel(Text(self.issuer_information.website), title="Website")])

        issuer_panel = Panel(
            Group(*[issuer_table, contact_columns]),
            title=Text("Issuer", style="bold deep_sky_blue1"),
            box=box.ROUNDED
        )

        # Funding Portal
        funding_portal_panel = None
        if self.issuer_information.funding_portal is not None:
            intermediary_table = Table(Column("Name", style="bold"), "CIK", "CRD Number", "File Number", box=box.SIMPLE)
            intermediary_table.add_row(
                self.issuer_information.funding_portal.name,
                self.issuer_information.funding_portal.cik,
                self.issuer_information.funding_portal.crd or "",
                self.issuer_information.funding_portal.file_number)
            funding_portal_panel = Panel(
                intermediary_table,
                title=Text("CrowdFunding Portal", style="bold deep_sky_blue1"),
                box=box.ROUNDED
            )

        offering_panel = None

        if self.offering_information:
            # Offering Information
            offering_table = Table(Column("", style='bold'), "", box=box.SIMPLE, row_styles=["", "bold"])
            offering_table.add_row("Compensation Amount", self.offering_information.compensation_amount)
            offering_table.add_row("Financial Interest", self.offering_information.financial_interest)
            offering_table.add_row("Type of Security", self.offering_information.security_offered_type)
            offering_table.add_row("Number of Securities", self.offering_information.no_of_security_offered)
            offering_table.add_row("Price", self.offering_information.price)
            offering_table.add_row("Price (or Method for Determining Price)",
                                   self.offering_information.price_determination_method)
            offering_table.add_row("Target Offering Amount", f"${self.offering_information.offering_amount:,.2f}")
            offering_table.add_row("Maximum Offering Amount",
                                   f"${self.offering_information.maximum_offering_amount:,.2f}")
            offering_table.add_row("Over-Subscription Accepted",
                                   yes_no(self.offering_information.over_subscription_accepted == "Y")),
            offering_table.add_row("How will over-subscriptions be allocated",
                                   self.offering_information.over_subscription_allocation_type)
            offering_table.add_row("Describe over-subscription plan",
                                   self.offering_information.desc_over_subscription)
            offering_table.add_row("Deadline Date", self.format_date(
                self.offering_information.deadline_date) if self.offering_information.deadline_date else "")

            offering_panel = Panel(
                offering_table,
                title=Text("Offering Information", style="bold deep_sky_blue1"),
                box=box.ROUNDED
            )

        # Annual Report Disclosure
        if self.annual_report_disclosure:
            annual_report_panel = Panel(
                self.annual_report_disclosure.__rich__(),
                title=Text("Annual Report Disclosures", style="bold deep_sky_blue1"),
                box=box.ROUNDED
            )
        else:
            annual_report_panel = None

        # Signature Info
        # The signature of the issuer
        issuer_signature_table = Table(Column("Signature", style="bold"), "Title", "Issuer", box=box.SIMPLE)
        issuer_signature_table.add_row(self.signature_info.issuer_signature.signature,
                                       self.signature_info.issuer_signature.title,
                                       self.signature_info.issuer_signature.issuer)

        # Person Signatures
        person_signature_table = Table(Column("Signature", style="bold"), "Title", "Date", box=box.SIMPLE,
                                       row_styles=["", "bold"])
        for signature in self.signature_info.signatures:
            person_signature_table.add_row(signature.signature, signature.title,
                                           self.format_date(signature.date))

        signature_panel = Panel(
            Group(
                Panel(issuer_signature_table, box=box.ROUNDED, title="Issuer"),
                Panel(person_signature_table, box=box.ROUNDED, title="Persons")
            ),
            title=Text("Signatures", style="bold deep_sky_blue1"),
            box=box.ROUNDED
        )

        renderables = [
            filer_panel,
            issuer_panel,
        ]
        if funding_portal_panel is not None:
            renderables.append(funding_portal_panel)
        if self.offering_information is not None:
            renderables.append(offering_panel)
        if self.annual_report_disclosure is not None:
            renderables.append(annual_report_panel)
        renderables.append(signature_panel)

        panel = Panel(
            Group(*renderables),
            title=Text(self.description, style="bold dark_sea_green4"),
        )
        return panel

    def __repr__(self):
        return repr_rich(self.__rich__())
