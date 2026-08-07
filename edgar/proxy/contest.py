"""
Proxy contest detection and analysis for SEC proxy filings.

Detects contested proxy situations, identifies management vs. dissident parties,
and assembles chronological timelines from filing metadata.
"""
import logging
from functools import cached_property
from typing import TYPE_CHECKING, Dict, List, Optional

import pandas as pd
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar.richtools import repr_rich

from .models import (
    CONTEST_INDICATOR_FORMS,
    DISSIDENT_ONLY_FORMS,
    SeasonFiling,
    classify_proxy_tier,
)

if TYPE_CHECKING:
    from edgar._filings import Filing

log = logging.getLogger(__name__)

__all__ = ['ProxyContest']


def _strip_amendment(form: str) -> str:
    """Strip /A suffix to get base form type."""
    return form.replace('/A', '').strip()


def _normalize_cik(cik) -> Optional[int]:
    """Normalize CIK to int for comparison (handles zero-padded strings)."""
    if cik is None:
        return None
    try:
        return int(str(cik).lstrip('0') or '0')
    except (ValueError, TypeError):
        return None


def identify_party(filing: 'Filing', company_cik: str) -> tuple[str, str]:
    """Identify who filed a proxy filing and their role.

    Returns:
        (party_name, party_type) where party_type is
        'management', 'dissident', 'third_party', or 'unknown'.
    """
    base_form = _strip_amendment(filing.form)

    # N-suffix forms are always dissident
    if base_form in DISSIDENT_ONLY_FORMS:
        party_type = 'dissident'
        try:
            header = filing.header
            if header.filers:
                return header.filers[0].company_information.name, party_type
            # Filer info might be in subject_companies for some formats
        except Exception:
            pass
        return 'Unknown Dissident', party_type

    # C-suffix forms (DEFC14A, PREC14A) — compare CIKs
    if base_form in {'DEFC14A', 'DEFC14C', 'PREC14A', 'PREC14C'}:
        try:
            header = filing.header
            filer_cik = None
            filer_name = None

            if header.filers:
                filer_cik = header.filers[0].company_information.cik
                filer_name = header.filers[0].company_information.name
            elif header.subject_companies:
                filer_cik = header.subject_companies[0].company_information.cik
                filer_name = header.subject_companies[0].company_information.name

            if filer_cik and _normalize_cik(company_cik) != _normalize_cik(filer_cik):
                return filer_name or 'Unknown Dissident', 'dissident'
            elif filer_cik:
                return filer_name or 'Management', 'management'
        except Exception as e:
            log.debug(f"Header parse failed for {filing.accession_no}: {e}")

        return 'Unknown', 'unknown'

    # DEFA14A from the company itself = management supplemental
    # PX14A6G = third-party exempt solicitation
    if base_form in {'PX14A6G', 'PX14A6N'}:
        try:
            header = filing.header
            if header.filers:
                return header.filers[0].company_information.name, 'third_party'
        except Exception:
            pass
        return 'Unknown Third Party', 'third_party'

    # For other forms (DEFA14A, PRE 14A, etc.), check CIK
    try:
        header = filing.header
        filer_cik = None
        filer_name = None
        if header.filers:
            filer_cik = header.filers[0].company_information.cik
            filer_name = header.filers[0].company_information.name
        if filer_cik and _normalize_cik(company_cik) != _normalize_cik(filer_cik):
            return filer_name or 'Unknown', 'dissident'
        return filer_name or 'Management', 'management'
    except Exception:
        return 'Unknown', 'unknown'


def _get_filer_cik(filing: 'Filing') -> Optional[str]:
    """Extract filer CIK from header, or None."""
    try:
        header = filing.header
        if header.filers:
            return str(header.filers[0].company_information.cik)
    except Exception:
        pass
    return None


def _make_season_filing(filing: 'Filing', company_cik: str) -> SeasonFiling:
    """Create a SeasonFiling with best-effort metadata."""
    party_name, party_type = identify_party(filing, company_cik)
    return SeasonFiling(
        filing=filing,
        form=filing.form,
        filing_date=str(filing.filing_date),
        accession_no=filing.accession_no,
        file_number=getattr(filing, 'file_number', None),
        party_type=party_type,
        party_name=party_name,
        filer_cik=_get_filer_cik(filing),
        tier=classify_proxy_tier(filing.form),
    )


class ProxyContest:
    """
    Analyzes a contested proxy situation.

    Identifies management vs. dissident parties, lists distinct dissidents,
    and assembles a chronological timeline of contest filings.

    Created by ProxySeason when contest indicator forms are detected.
    Not intended to be constructed directly by users.
    """

    def __init__(self, company_name: str, company_cik: str, contest_filings: List['Filing']):
        self._company_name = company_name
        self._company_cik = str(company_cik)
        self._contest_filings = contest_filings

    @cached_property
    def _labeled_filings(self) -> List[SeasonFiling]:
        """Lazily label each filing with party identification.

        This triggers header parsing (network calls) only when
        party/timeline data is accessed.
        """
        labeled = []
        for filing in self._contest_filings:
            labeled.append(_make_season_filing(filing, self._company_cik))
        return sorted(labeled, key=lambda sf: sf.filing_date)

    @property
    def is_contested(self) -> bool:
        """Always True — if no contest, ProxySeason.contest returns None."""
        return True

    @property
    def company_name(self) -> str:
        return self._company_name

    @property
    def num_filings(self) -> int:
        """Total number of contest-related filings."""
        return len(self._contest_filings)

    @cached_property
    def dissidents(self) -> List[str]:
        """Names of dissident parties (unique, ordered by first appearance)."""
        seen = {}
        for sf in self._labeled_filings:
            if sf.party_type == 'dissident' and sf.party_name not in seen:
                seen[sf.party_name] = True
        return list(seen.keys())

    @cached_property
    def parties(self) -> Dict[str, str]:
        """All parties involved: {name: party_type}."""
        result = {}
        for sf in self._labeled_filings:
            if sf.party_name and sf.party_name not in result:
                result[sf.party_name] = sf.party_type
        return result

    @property
    def management_filings(self) -> List[SeasonFiling]:
        """Filings from management."""
        return [sf for sf in self._labeled_filings if sf.party_type == 'management']

    @property
    def dissident_filings(self) -> List[SeasonFiling]:
        """Filings from dissidents."""
        return [sf for sf in self._labeled_filings if sf.party_type == 'dissident']

    @property
    def third_party_filings(self) -> List[SeasonFiling]:
        """Exempt solicitations from third parties (ISS, Glass Lewis, etc.)."""
        return [sf for sf in self._labeled_filings if sf.party_type == 'third_party']

    @cached_property
    def is_settled(self) -> bool:
        """Whether the contest appears to have been settled.

        Settlement fingerprint: contest indicator forms exist but management
        never filed DEFC14A — they reverted to standard DEF 14A.
        """
        mgmt_forms = {_strip_amendment(sf.form) for sf in self.management_filings}
        return 'DEFC14A' not in mgmt_forms

    @cached_property
    def timeline(self) -> pd.DataFrame:
        """Chronological timeline of all contest filings.

        Columns: date, form, party, party_type, tier, accession_no
        """
        rows = []
        for sf in self._labeled_filings:
            rows.append({
                'date': sf.filing_date,
                'form': sf.form,
                'party': sf.party_name,
                'party_type': sf.party_type,
                'tier': sf.tier,
                'accession_no': sf.accession_no,
            })
        return pd.DataFrame(rows, columns=['date', 'form', 'party', 'party_type', 'tier', 'accession_no'])

    def __str__(self) -> str:
        dissident_str = ', '.join(self.dissidents) if self.dissidents else 'Unknown'
        settled = ' (settled)' if self.is_settled else ''
        return f"Proxy Contest: {self._company_name} vs {dissident_str}{settled} ({self.num_filings} filings)"

    def __rich__(self):
        # Title
        title = Text()
        title.append("Proxy Contest", style="bold red")
        title.append(f" — {self._company_name}", style="bold")

        # Info section
        info_table = Table(box=None, show_header=False, padding=(0, 2))
        info_table.add_column("Field", style="dim")
        info_table.add_column("Value")

        info_table.add_row("Company", self._company_name)
        info_table.add_row("Filings", str(self.num_filings))
        info_table.add_row("Dissidents", ', '.join(self.dissidents) if self.dissidents else 'Unknown')
        if self.is_settled:
            info_table.add_row("Status", "Settled (no DEFC14A from management)")
        else:
            info_table.add_row("Status", "Contested")

        header_panel = Panel(info_table, title=title, border_style="red")

        elements = [header_panel]

        # Timeline table
        if self._labeled_filings:
            tl_table = Table(
                title="Contest Timeline",
                box=box.SIMPLE,
                show_header=True,
            )
            tl_table.add_column("Date", style="dim", width=12)
            tl_table.add_column("Form", width=12)
            tl_table.add_column("Party", ratio=2)
            tl_table.add_column("Role", width=12)

            for sf in self._labeled_filings:
                role_style = "red" if sf.party_type == 'dissident' else "green" if sf.party_type == 'management' else "dim"
                tl_table.add_row(
                    sf.filing_date,
                    sf.form,
                    sf.party_name or 'Unknown',
                    Text(sf.party_type, style=role_style),
                )

            elements.append(Text())
            elements.append(tl_table)

        return Group(*elements)

    def __repr__(self):
        return repr_rich(self.__rich__())

    def to_context(self, detail: str = 'standard') -> str:
        """AI-optimized context string.

        Args:
            detail: 'minimal' (~50 tokens), 'standard' (~200 tokens), 'full' (~500+ tokens)
        """
        lines = [f"PROXY CONTEST: {self._company_name}"]
        lines.append(f"Dissidents: {', '.join(self.dissidents) if self.dissidents else 'Unknown'}")
        lines.append(f"Status: {'Settled' if self.is_settled else 'Contested'}")
        lines.append(f"Filings: {self.num_filings}")

        if detail == 'minimal':
            return '\n'.join(lines)

        # Standard: add party breakdown
        lines.append("")
        for name, role in self.parties.items():
            lines.append(f"  {name}: {role}")

        if detail == 'standard':
            return '\n'.join(lines)

        # Full: add timeline
        lines.append("")
        lines.append("TIMELINE:")
        for sf in self._labeled_filings:
            lines.append(f"  {sf.filing_date}  {sf.form:12s}  {sf.party_name} ({sf.party_type})")

        return '\n'.join(lines)
