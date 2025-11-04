"""
Offering Lifecycle Tracking for Crowdfunding Filings (Regulation CF)

This module provides the Offering class for tracking the complete lifecycle
of crowdfunding offerings through Form C filings.

Lifecycle Stages:
  C      → Initial offering
  C/A    → Amendments to offering
  C-U    → Progress updates (50% or 100% milestones)
  C-U/A  → Amendments to progress updates
  C-AR   → Annual reports (yearly compliance)
  C-AR/A → Amendments to annual reports
  C-TR   → Termination (offering closed)

File Number System:
  The Offering class tracks TWO file numbers:
  - Issuer file number (020-XXXXX): Identifies ONE specific offering
  - Portal file number (007-XXXXX): Identifies the funding portal

  The issuer file number is used as the primary identifier for tracking
  a single offering's lifecycle. The portal file number is tracked for
  reference but not used as the primary identifier.

Usage:
    from edgar import Company
    from edgar.offerings import Offering

    # Method 1: From FormC object (recommended)
    company = Company('1881570')
    filing = company.get_filings(form='C')[0]
    formc = filing.obj()
    offering = formc.get_offering(filing)

    # Method 2: Direct construction from filing
    offering = Offering(filing)

    # Method 3: From issuer file number
    offering = Offering('020-36002', cik='1881570')

    # Access file numbers
    print(offering.issuer_file_number)  # 020-36002 (offering identifier)
    print(offering.portal_file_number)  # 007-00033 (portal identifier)

    # Access cached FormC
    formc = offering.initial_formc  # Parsed at initialization

    # Access lifecycle stages
    print(offering.initial_offering)
    print(offering.amendments)
    print(offering.updates)
    print(offering.annual_reports)

    # Get status and metrics
    print(offering.current_status)
    print(offering.days_since_launch)

    # Generate token-efficient reports
    print(offering.to_context(detail='minimal'))    # ~300 tokens
    print(offering.to_context(detail='standard'))   # ~700 tokens
    print(offering.to_context(detail='full'))       # ~1500 tokens

    # Rich visualization
    print(offering)

Performance Optimization:
    Offering performs early conversion and caching at initialization:
    - Filing → EntityFiling conversion (once)
    - FormC parsing (once)
    - Both file numbers extracted (once)
    - All results cached for reuse

    This avoids repeated expensive operations throughout the lifecycle.
"""
from datetime import date
from functools import cached_property
from typing import Dict, List, Optional, Union
from collections import defaultdict

from edgar import Filing, Company
from edgar.entity import EntityFilings
from edgar.offerings.formc import FormC, AnnualReportDisclosure
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich import box

__all__ = ['Offering', 'Campaign']  # Campaign kept for backwards compatibility


class Offering:
    """
    Wrapper for a complete crowdfunding offering lifecycle.

    This class provides a high-level interface for tracking all filings
    related to a single crowdfunding offering (Regulation CF), organized by lifecycle stage.

    Attributes:
        file_number: Offering file number (issuer file number, unique identifier)
        company: Company object for the issuer
        all_filings: List of all offering filings (sorted by date)

    AI-Native Features:
        - to_context() method for token-efficient reporting
        - Convenience properties for common queries
        - Rich visualization support
    """

    def __init__(self, filing_or_file_number: Union[Filing, str], cik: Optional[str] = None):
        """
        Initialize a Campaign from a filing or file number.

        Optimization: Converts Filing→EntityFiling and parses FormC immediately
        to avoid repeated expensive operations. Results are cached for reuse.

        Args:
            filing_or_file_number: Either:
                - A Filing object (Form C variant)
                - A file number string (requires cik parameter)
            cik: Required if filing_or_file_number is a file number string

        Raises:
            ValueError: If file_number string is provided without cik

        Examples:
            # From filing (recommended - enables caching)
            campaign = Campaign(filing)

            # From file number (less efficient - no caching)
            campaign = Campaign('020-36002', cik='1234567')
        """
        if isinstance(filing_or_file_number, Filing):
            # Do ALL expensive operations NOW (once)
            self._entity_filing = filing_or_file_number.as_company_filing()
            self._formc = filing_or_file_number.obj()  # Parse FormC once

            # Extract BOTH file numbers from cached data
            self._issuer_file_number = self._entity_filing.file_number  # 020-XXXXX (offering ID)
            self._portal_file_number = self._formc.portal_file_number  # 007-XXXXX (portal ID)

            self._cik = filing_or_file_number.cik

            # Use issuer file number as the primary identifier
            # This represents ONE specific offering (not all offerings through portal)
            self._file_number = self._issuer_file_number

        elif isinstance(filing_or_file_number, str):
            # Initialize from file number (less efficient - no caching)
            if not cik:
                raise ValueError("cik parameter required when initializing from file_number")

            self._file_number = filing_or_file_number
            self._issuer_file_number = filing_or_file_number
            self._cik = cik

            # Cannot cache without filing object
            self._entity_filing = None
            self._formc = None
            self._portal_file_number = None

        else:
            raise TypeError(f"Expected Filing or str, got {type(filing_or_file_number)}")

        # Lazy-loaded attributes are implemented as cached_property methods

    # =========================================================================
    # Core Properties
    # =========================================================================

    @property
    def file_number(self) -> str:
        """
        Issuer file number for this offering (e.g., '020-36002').

        This is the primary identifier that links all filings for ONE specific
        offering (Form C, amendments, updates, annual reports, termination).
        """
        return self._file_number

    @property
    def issuer_file_number(self) -> str:
        """
        Issuer's SEC file number (e.g., '020-36002').

        Format: 020-XXXXX
        Identifies: ONE specific Regulation CF offering
        Use for: Finding all filings for this offering (C, C/A, C-U, C-AR, C-TR)
        """
        return self._issuer_file_number

    @property
    def portal_file_number(self) -> Optional[str]:
        """
        Portal's SEC commission file number (e.g., '007-00033').

        Format: 007-XXXXX
        Identifies: The funding portal facilitating this offering
        Use for: Multi-offering analysis (all offerings through same portal)

        Note: Only available when initialized from Filing (cached at init).
        Returns None when initialized from file_number string.
        """
        return self._portal_file_number

    @property
    def initial_formc(self) -> Optional[FormC]:
        """
        The parsed FormC object (cached at initialization).

        Only available when initialized from Filing object.
        Provides fast access to offering details without re-parsing.

        Returns None when initialized from file_number string.
        """
        return self._formc

    @cached_property
    def company(self) -> Company:
        """Company object for the issuer"""
        return Company(self._cik)

    @cached_property
    def all_filings(self) -> EntityFilings:
        """
        All filings for this offering, sorted by filing date (ascending).

        Uses issuer file number (020-XXXXX) to get all filings for ONE specific
        offering (initial Form C + amendments, updates, annual reports, termination).

        IMPORTANT: This returns filings for ONE offering only, not all offerings
        through the same portal.

        Returns empty list if no filings found.
        """
        # Use issuer file number to query directly - no need to parse each filing!
        filings = self.company.get_filings(
            file_number=self._issuer_file_number,
            sort_by=[("filing_date", "ascending")]
        )

        return filings

    # =========================================================================
    # Lifecycle Stage Properties
    # =========================================================================

    @cached_property
    def filings_by_stage(self) -> Dict[str, List[Filing]]:
        """Group filings by lifecycle stage (cached)"""
        categorized = defaultdict(list)

        for filing in self.all_filings:
            stage = self._classify_filing(filing.form)
            categorized[stage].append(filing)

        # Ensure all stages exist
        for stage in ['initial', 'amendment', 'update', 'report', 'termination']:
            if stage not in categorized:
                categorized[stage] = []

        return dict(categorized)

    @staticmethod
    def _classify_filing(form: str) -> str:
        """Classify filing by lifecycle stage"""
        if form == 'C':
            return 'initial'
        elif form == 'C/A':
            return 'amendment'
        elif form in ['C-U', 'C-U/A']:
            return 'update'
        elif form in ['C-AR', 'C-AR/A']:
            return 'report'
        elif form == 'C-TR':
            return 'termination'
        else:
            return 'unknown'

    @property
    def initial_offering(self) -> Optional[FormC]:
        """Initial Form C offering (None if not filed)"""
        initial_filings = self.filings_by_stage['initial']
        if initial_filings:
            return initial_filings[0].obj()
        return None

    @property
    def amendments(self) -> List[FormC]:
        """All Form C/A amendments (empty list if none)"""
        return [f.obj() for f in self.filings_by_stage['amendment']]

    @property
    def updates(self) -> List[FormC]:
        """All progress updates (Form C-U and C-U/A) (empty list if none)"""
        return [f.obj() for f in self.filings_by_stage['update']]

    @property
    def annual_reports(self) -> List[FormC]:
        """All annual reports (Form C-AR and C-AR/A) (empty list if none)"""
        return [f.obj() for f in self.filings_by_stage['report']]

    @property
    def termination(self) -> Optional[FormC]:
        """Termination report (Form C-TR) (None if not terminated)"""
        termination_filings = self.filings_by_stage['termination']
        if termination_filings:
            return termination_filings[0].obj()
        return None

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    def timeline(self) -> List[Dict]:
        """
        Chronological timeline of all campaign events.

        Returns:
            List of dictionaries with keys:
            - date: Filing date
            - form: Form type (C, C/A, etc.)
            - stage: Lifecycle stage
            - description: Human-readable description
            - filing: Filing object
        """
        timeline = []

        for filing in self.all_filings:
            stage = self._classify_filing(filing.form)

            # Generate description
            descriptions = {
                'initial': "Campaign launched",
                'amendment': "Offering amended",
                'update': "Progress update filed",
                'report': "Annual report filed",
                'termination': "Campaign terminated"
            }
            description = descriptions.get(stage, f"{filing.form} filed")

            timeline.append({
                'date': filing.filing_date,
                'form': filing.form,
                'stage': stage,
                'description': description,
                'filing': filing
            })

        return timeline

    def latest_financials(self) -> Optional[AnnualReportDisclosure]:
        """
        Get the most recent financial data from any filing.

        Search order: C-AR → C-U → C → C/A

        Returns:
            AnnualReportDisclosure or None if no financials available
        """
        # Try annual reports first
        for filing in reversed(self.filings_by_stage['report']):
            try:
                formc = filing.obj()
                if formc.annual_report_disclosure:
                    return formc.annual_report_disclosure
            except:
                continue

        # Try updates
        for filing in reversed(self.filings_by_stage['update']):
            try:
                formc = filing.obj()
                if formc.annual_report_disclosure:
                    return formc.annual_report_disclosure
            except:
                continue

        # Try initial
        if self.filings_by_stage['initial']:
            try:
                formc = self.filings_by_stage['initial'][0].obj()
                if formc.annual_report_disclosure:
                    return formc.annual_report_disclosure
            except:
                pass

        return None

    # =========================================================================
    # Status Properties (AI-Native Convenience Pattern)
    # =========================================================================

    @property
    def is_active(self) -> bool:
        """
        True if campaign is currently accepting investments.

        A campaign is active if:
        - Not terminated (no C-TR filing)
        - Deadline has not passed (if deadline exists)
        """
        if self.is_terminated:
            return False

        # Check deadline from initial offering
        initial = self.initial_offering
        if initial and initial.offering_information:
            deadline = initial.offering_information.deadline_date
            if deadline and deadline < date.today():
                return False

        return True

    @property
    def is_terminated(self) -> bool:
        """True if campaign filed Form C-TR (termination report)"""
        return len(self.filings_by_stage['termination']) > 0

    @property
    def status(self) -> str:
        """
        User-friendly campaign status string.

        Returns:
            'terminated' - Campaign filed Form C-TR
            'expired' - Deadline has passed
            'active' - Currently accepting investments
        """
        if self.is_terminated:
            return 'terminated'
        elif self.is_expired:
            return 'expired'
        elif self.is_active:
            return 'active'
        else:
            return 'inactive'

    @property
    def is_expired(self) -> bool:
        """True if offering deadline has passed"""
        initial = self.initial_offering
        if initial and initial.offering_information:
            deadline = initial.offering_information.deadline_date
            if deadline and deadline < date.today():
                return True
        return False

    @property
    def current_status(self) -> str:
        """
        User-friendly current status string.

        Possible values:
        - "Terminated" - Filed C-TR
        - "Reporting Phase" - Has annual reports
        - "Active (with updates)" - Has progress updates
        - "Expired" - Deadline passed
        - "Active" - Currently accepting investments
        - "Unknown" - No filings found
        """
        if not self.all_filings:
            return "Unknown"

        if self.is_terminated:
            return "Terminated"

        if self.annual_reports:
            return "Reporting Phase"

        if self.updates:
            return "Active (with updates)"

        if self.is_expired:
            return "Expired"

        return "Active"

    @property
    def days_since_launch(self) -> int:
        """Days since initial Form C filing (0 if no filings)"""
        if not self.all_filings:
            return 0

        initial_filings = self.filings_by_stage['initial']
        launch_date = initial_filings[0].filing_date if initial_filings else self.all_filings[0].filing_date

        return (date.today() - launch_date).days

    @property
    def launch_date(self) -> Optional[date]:
        """Date of initial Form C filing"""
        if not self.all_filings:
            return None

        initial_filings = self.filings_by_stage['initial']
        return initial_filings[0].filing_date if initial_filings else self.all_filings[0].filing_date

    @property
    def latest_activity_date(self) -> Optional[date]:
        """Date of most recent filing"""
        if not self.all_filings:
            return None
        return self.all_filings[-1].filing_date

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
                    lines.append(f"  Revenue: $0 (pre-revenue)")
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


# Backwards compatibility alias
Campaign = Offering
