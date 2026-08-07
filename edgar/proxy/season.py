"""
Proxy season grouping for SEC proxy filings.

Groups all proxy-related filings for a company around an annual meeting,
anchored by management's definitive proxy (DEF 14A or DEFC14A).
"""
import logging
from functools import cached_property
from typing import TYPE_CHECKING, List, Optional

import pandas as pd
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar.richtools import repr_rich

from .contest import ProxyContest, _make_season_filing, _normalize_cik
from .models import (
    ANCHOR_FORMS,
    CONTEST_INDICATOR_FORMS,
    EXEMPT_SOLICITATION_FORMS,
    PRELIMINARY_FORMS,
    PROXY_FORMS,
    SUPPLEMENTAL_FORMS,
    SeasonFiling,
    classify_proxy_tier,
)

if TYPE_CHECKING:
    from edgar.entity.core import Entity

log = logging.getLogger(__name__)

__all__ = ['ProxySeason']


def _base_form(form: str) -> str:
    """Strip /A suffix to get base form type."""
    return form.replace('/A', '').strip()


class ProxySeason:
    """
    All proxy activity around one annual meeting.

    Groups related proxy filings by season, identifies the management anchor
    (DEF 14A or DEFC14A), and detects contests.

    Usage:
        >>> from edgar import Company
        >>> company = Company("AAPL")
        >>> season = ProxySeason.for_company(company)
        >>> print(season.is_contested)
        False
        >>> print(season.proxy)
        DEF 14A: Apple Inc. - 2026-02-24
    """

    def __init__(self,
                 company: 'Entity',
                 anchor: 'Filing',
                 season_filings: List['Filing'],
                 next_anchor_date: Optional[str] = None):
        """
        Args:
            company: The company entity
            anchor: Management's definitive proxy (DEF 14A or DEFC14A by company CIK)
            season_filings: All proxy filings in this season's window
            next_anchor_date: Filing date of the next season's anchor (None if current/open)
        """
        self._company = company
        self._anchor = anchor
        self._season_filings = season_filings
        self._next_anchor_date = next_anchor_date

    @classmethod
    def for_company(cls, company: 'Entity', index: int = 0) -> Optional['ProxySeason']:
        """Build a ProxySeason for the given company.

        Args:
            company: Company entity
            index: 0 = latest season, 1 = previous, etc.

        Returns:
            ProxySeason or None if no proxy filings found
        """
        # Get all anchor filings (DEF 14A and DEFC14A from the company itself)
        anchors = cls._find_anchors(company)
        if not anchors or index >= len(anchors):
            return None

        anchor = anchors[index]
        next_anchor_date = str(anchors[index - 1].filing_date) if index > 0 else None

        # Previous anchor defines the start of this season's window
        prev_anchor_date = str(anchors[index + 1].filing_date) if index + 1 < len(anchors) else None

        # Gather all proxy filings in the window
        season_filings = cls._gather_season_filings(company, anchor, prev_anchor_date, next_anchor_date)

        return cls(company, anchor, season_filings, next_anchor_date)

    @classmethod
    def _find_anchors(cls, company: 'Entity') -> List['Filing']:
        """Find all season anchor filings, sorted most recent first.

        An anchor is a DEF 14A or DEFC14A filed by the company itself
        (not by a dissident). We use the company's CIK to filter.

        Returns filings sorted by filing_date descending (most recent first).
        """
        company_cik = str(company.cik)

        # Get recent DEF 14A filings (the normal case) — cap to avoid materializing decades of history
        def14a = company.get_filings(form='DEF 14A', amendments=False)
        def14a_list = list(def14a.head(20)) if def14a and len(def14a) > 0 else []

        # Get DEFC14A filings (contest years where DEF 14A is absent)
        defc14a = company.get_filings(form='DEFC14A', amendments=False)
        defc14a_list = list(defc14a.head(10)) if defc14a and len(defc14a) > 0 else []

        # Filter DEFC14A to management-only (filer CIK == company CIK)
        mgmt_defc14a = []
        for filing in defc14a_list:
            try:
                header = filing.header
                filer_cik = None
                if header.filers:
                    filer_cik = str(header.filers[0].company_information.cik)
                # If the filer is the company itself, it's a management DEFC14A
                if _normalize_cik(filer_cik) == _normalize_cik(company_cik):
                    mgmt_defc14a.append(filing)
                elif filer_cik is None:
                    if header.subject_companies:
                        subj_cik = header.subject_companies[0].company_information.cik
                        if _normalize_cik(subj_cik) == _normalize_cik(company_cik) and not header.filers:
                            mgmt_defc14a.append(filing)
            except Exception:
                # Can't determine filer — include conservatively
                # (generous inclusion principle)
                mgmt_defc14a.append(filing)

        # Combine and sort by filing_date descending
        all_anchors = def14a_list + mgmt_defc14a
        all_anchors.sort(key=lambda f: str(f.filing_date), reverse=True)

        # Deduplicate by year — if both DEF 14A and DEFC14A exist for the same
        # year (e.g., settlement case), prefer DEF 14A
        seen_years = {}
        deduped = []
        for filing in all_anchors:
            year = str(filing.filing_date)[:4]
            if year not in seen_years:
                seen_years[year] = filing
                deduped.append(filing)
            elif filing.form == 'DEF 14A' and seen_years[year].form != 'DEF 14A':
                # Replace DEFC14A with DEF 14A for same year
                idx = deduped.index(seen_years[year])
                deduped[idx] = filing
                seen_years[year] = filing

        return deduped

    @classmethod
    def _gather_season_filings(cls, company: 'Entity',
                                anchor: 'Filing',
                                prev_anchor_date: Optional[str],
                                next_anchor_date: Optional[str]) -> List['Filing']:
        """Gather all proxy filings within this season's window.

        Window: [prev_anchor_date, next_anchor_date) or open-ended.
        """
        # Build filing_date range
        start = prev_anchor_date or ""
        end = next_anchor_date or ""

        if start and end:
            date_range = f"{start}:{end}"
        elif start:
            date_range = f"{start}:"
        elif end:
            date_range = f":{end}"
        else:
            date_range = None

        # Get ALL proxy filings in the window with a single query
        # Use base forms only (skip /A variants — amendments=True handles them)
        base_forms = sorted({_base_form(f) for f in PROXY_FORMS})
        all_filings = []
        try:
            filings = company.get_filings(
                form=base_forms,
                filing_date=date_range,
                amendments=True,
                sort_by="filing_date",
            )
            if filings and len(filings) > 0:
                all_filings.extend(list(filings))
        except Exception:
            pass

        # Deduplicate by accession number
        seen = set()
        unique = []
        for f in all_filings:
            if f.accession_no not in seen:
                seen.add(f.accession_no)
                unique.append(f)

        # Sort chronologically
        unique.sort(key=lambda f: str(f.filing_date))
        return unique

    # ── Properties ────────────────────────────────────────────────────

    @property
    def anchor(self) -> 'Filing':
        """The management definitive proxy filing (DEF 14A or DEFC14A)."""
        return self._anchor

    @property
    def anchor_form(self) -> str:
        """Form type of the anchor filing."""
        return self._anchor.form

    @property
    def filing_date(self) -> str:
        """Filing date of the anchor."""
        return str(self._anchor.filing_date)

    @property
    def company_name(self) -> str:
        return self._company.name

    @property
    def cik(self) -> str:
        return str(self._company.cik)

    @cached_property
    def proxy(self):
        """ProxyStatement extracted from the anchor filing."""
        from edgar.proxy.core import ProxyStatement
        return ProxyStatement.from_filing(self._anchor)

    @property
    def related_filings(self) -> List['Filing']:
        """All proxy filings in this season."""
        return self._season_filings

    @property
    def num_filings(self) -> int:
        return len(self._season_filings)

    @cached_property
    def _labeled_filings(self) -> List[SeasonFiling]:
        """All season filings with metadata labels."""
        company_cik = str(self._company.cik)
        labeled = [_make_season_filing(f, company_cik) for f in self._season_filings]
        return sorted(labeled, key=lambda sf: sf.filing_date)

    @property
    def preliminary_filings(self) -> List[SeasonFiling]:
        """Tier 3: Preliminary proxy filings."""
        return [sf for sf in self._labeled_filings if sf.tier == 3]

    @property
    def supplemental_filings(self) -> List[SeasonFiling]:
        """Tier 4: Supplemental campaign materials (DEFA14A, DFAN14A, DFRN14A)."""
        return [sf for sf in self._labeled_filings if sf.tier == 4]

    @property
    def exempt_solicitations(self) -> List[SeasonFiling]:
        """Tier 5: Third-party exempt solicitations (PX14A6G, PX14A6N)."""
        return [sf for sf in self._labeled_filings if sf.tier == 5]

    # ── Contest detection ─────────────────────────────────────────────

    @cached_property
    def is_contested(self) -> bool:
        """Whether this proxy season has contest indicator filings."""
        for f in self._season_filings:
            if _base_form(f.form) in CONTEST_INDICATOR_FORMS:
                return True
        return False

    @cached_property
    def contest(self) -> Optional[ProxyContest]:
        """ProxyContest analysis if this season is contested, else None."""
        if not self.is_contested:
            return None

        contest_filings = [
            f for f in self._season_filings
            if _base_form(f.form) in CONTEST_INDICATOR_FORMS
            or _base_form(f.form) in SUPPLEMENTAL_FORMS
            or _base_form(f.form) in EXEMPT_SOLICITATION_FORMS
        ]

        return ProxyContest(
            company_name=self._company.name,
            company_cik=str(self._company.cik),
            contest_filings=contest_filings,
        )

    # ── Display ───────────────────────────────────────────────────────

    def __str__(self) -> str:
        contested = " (contested)" if self.is_contested else ""
        return f"Proxy Season: {self.company_name} {self.filing_date[:4]}{contested} ({self.num_filings} filings)"

    def __rich__(self):
        # Title
        title = Text()
        title.append("Proxy Season", style="bold blue")
        title.append(f" — {self.company_name}", style="bold")
        if self.is_contested:
            title.append(" [CONTESTED]", style="bold red")

        # Info
        info_table = Table(box=None, show_header=False, padding=(0, 2))
        info_table.add_column("Field", style="dim")
        info_table.add_column("Value")

        info_table.add_row("Anchor", f"{self.anchor_form} ({self.filing_date})")
        info_table.add_row("Total Filings", str(self.num_filings))

        # Tier breakdown
        tier_counts = {}
        for sf in self._labeled_filings:
            tier_counts[sf.tier] = tier_counts.get(sf.tier, 0) + 1
        tier_labels = {1: 'Full proxy', 2: 'Contested', 3: 'Preliminary', 4: 'Supplemental', 5: 'Exempt'}
        parts = [f"{tier_labels.get(t, '?')}: {c}" for t, c in sorted(tier_counts.items())]
        if parts:
            info_table.add_row("Breakdown", ', '.join(parts))

        header_panel = Panel(info_table, title=title, border_style="blue")
        elements = [header_panel]

        # Contest summary if applicable
        if self.is_contested and self.contest:
            elements.append(Text())
            elements.append(self.contest.__rich__())

        return Group(*elements)

    def __repr__(self):
        return repr_rich(self.__rich__())

    def to_context(self, detail: str = 'standard') -> str:
        """AI-optimized context string."""
        lines = [f"PROXY SEASON: {self.company_name}"]
        lines.append(f"Anchor: {self.anchor_form} filed {self.filing_date}")
        lines.append(f"Total filings: {self.num_filings}")
        lines.append(f"Contested: {'Yes' if self.is_contested else 'No'}")

        if detail == 'minimal':
            return '\n'.join(lines)

        # Tier breakdown
        tier_counts = {}
        for sf in self._labeled_filings:
            tier_counts[sf.tier] = tier_counts.get(sf.tier, 0) + 1
        tier_labels = {1: 'Full proxy', 2: 'Contested definitive', 3: 'Preliminary', 4: 'Supplemental', 5: 'Exempt solicitation'}
        lines.append("")
        lines.append("FILING BREAKDOWN:")
        for t, c in sorted(tier_counts.items()):
            lines.append(f"  {tier_labels.get(t, 'Other')}: {c}")

        if self.is_contested and self.contest:
            lines.append("")
            lines.append(self.contest.to_context(detail=detail))

        if detail == 'standard':
            return '\n'.join(lines)

        # Full: list all filings
        lines.append("")
        lines.append("ALL FILINGS:")
        for sf in self._labeled_filings:
            lines.append(f"  {sf.filing_date}  {sf.form:12s}  {sf.party_name or '-':30s}  tier={sf.tier}  {sf.party_type}")

        lines.append("")
        lines.append("AVAILABLE ACTIONS:")
        lines.append("  .proxy                    ProxyStatement from anchor filing")
        lines.append("  .contest                  ProxyContest (if contested)")
        lines.append("  .related_filings          All filings in this season")
        lines.append("  .supplemental_filings     Campaign materials")
        lines.append("  .preliminary_filings      Preliminary proxies")
        lines.append("  .exempt_solicitations     Third-party solicitations")

        return '\n'.join(lines)
