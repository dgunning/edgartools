"""Shelf lifecycle position and insights for a 424B filing.

Computes shelf registration vintage, effectiveness, Rule 415(a)(5) expiry,
takedown cadence, re-registration continuity, and a timeline from the related
filings under a shelf.
"""

from __future__ import annotations

import logging
from datetime import date
from functools import cached_property
from typing import List, Optional, TYPE_CHECKING

from rich import box
from rich.console import Group, Text
from rich.panel import Panel
from rich.table import Table

from edgar.richtools import repr_rich
from edgar.offerings.prospectus.parsing import _parse_filing_date, _plus_three_years

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from edgar._filings import Filing, Filings
    from edgar.offerings.prospectus.models import RegistrationFeeTable

# Registration forms that start a shelf
_SHELF_BASE_FORMS = {'S-3', 'S-3ASR', 'F-3', 'F-3ASR', 'S-1'}
_TAKEDOWN_FORMS = {'424B1', '424B2', '424B3', '424B4', '424B5', '424B7', '424B8'}

_ASR_BASE_FORMS = {'S-3ASR', 'F-3ASR'}
# 'RW' withdraws the registration; 'RW WD' rescinds an earlier 'RW' (the
# registration is then NOT withdrawn). 'AW' withdraws only an amendment, not the
# registration, so it is deliberately excluded.


class ShelfLifecycle:
    """Lifecycle position and insights for a 424B filing within its shelf registration.

    Computes actionable insights from the related filings returned by
    Filing.related_filings(): shelf registration date, SEC review period,
    shelf expiration, takedown position, offering cadence, and a timeline.

    Usage:
        prospectus = filing.obj()  # Prospectus424B
        lc = prospectus.lifecycle
        lc.takedown_number       # e.g. 5
        lc.total_takedowns       # e.g. 5
        lc.shelf_expires         # e.g. date(2026, 8, 2)
        lc.avg_days_between_takedowns  # e.g. 228.0
    """

    def __init__(self, current_filing: 'Filing', related: 'Filings'):
        self._current = current_filing
        self._related = related

    # ------------------------------------------------------------------
    # Core properties
    # ------------------------------------------------------------------

    @property
    def filing(self) -> 'Filing':
        """The current 424B filing this lifecycle was computed from."""
        return self._current

    @property
    def filings(self) -> 'Filings':
        """The full set of related filings under this shelf."""
        return self._related

    @cached_property
    def shelf_registration(self) -> Optional['Filing']:
        """The S-3/F-3/S-1 filing that *initiated* this shelf.

        The earliest shelf-base-form filing in the family (selected explicitly by
        filing date, not by ``_related`` ordering). Establishes the shelf's vintage;
        for the date the expiry clock currently runs from, see
        :attr:`current_effective_date`.
        """
        candidates = [f for f in self._related
                      if f.form.replace('/A', '') in _SHELF_BASE_FORMS]
        return min(candidates, key=lambda f: f.filing_date) if candidates else None

    @cached_property
    def _initial_effective_filing(self) -> Optional['Filing']:
        """The EFFECT filing that *first* declared the shelf effective (earliest)."""
        effects = [f for f in self._related if f.form == 'EFFECT']
        return min(effects, key=lambda f: f.filing_date) if effects else None

    @cached_property
    def _current_effective_filing(self) -> Optional['Filing']:
        """The filing establishing *current* effectiveness (latest).

        The most recent effectiveness event — an EFFECT notice or an automatic
        (S-3ASR/F-3ASR) shelf filing, whichever is later. Automatic shelves are
        effective on filing and never receive an EFFECT notice, so both kinds are
        considered together; a genuine Rule 415(a)(6) re-registration of either
        kind advances this past cosmetic amendments. Stays consistent with
        :attr:`_generations`.
        """
        candidates = [f for f in self._related
                      if f.form == 'EFFECT'
                      or f.form.replace('/A', '') in _ASR_BASE_FORMS]
        return max(candidates, key=lambda f: f.filing_date) if candidates else None

    @cached_property
    def shelf_filed_date(self) -> Optional[str]:
        """Date the shelf registration was *originally* filed (string)."""
        reg = self.shelf_registration
        return str(reg.filing_date) if reg else None

    @cached_property
    def effective_date(self) -> Optional[str]:
        """Date the shelf *first* became effective (string).

        The original effectiveness; immutable for a given registration statement
        and used to measure the initial SEC review period. For the operative
        effectiveness today (which advances on re-registration), see
        :attr:`current_effective_date`.
        """
        eff = self._initial_effective_filing
        return str(eff.filing_date) if eff else None

    @cached_property
    def current_effective_date(self) -> Optional[str]:
        """Date of the shelf's *current* effectiveness (string).

        The latest EFFECT (or, for automatic shelves, the latest ASR filing).
        This is the date the Rule 415(a)(5) three-year clock currently runs from,
        so a re-registration moves it forward while cosmetic amendments do not.
        Equals :attr:`effective_date` for a shelf that has never been re-registered.
        """
        eff = self._current_effective_filing
        return str(eff.filing_date) if eff else None

    @cached_property
    def shelf_expires(self) -> Optional[date]:
        """Expiration date of the shelf (current effective date + 3 years).

        Anchored on *current* effectiveness per Rule 415(a)(5): a genuine
        415(a)(6) re-registration resets the clock, while a cosmetic POS AM or
        S-3/A does not. Returns None for a shelf that is not yet effective.
        """
        eff = _parse_filing_date(self.current_effective_date)
        return _plus_three_years(eff) if eff else None

    @cached_property
    def days_to_expiry(self) -> Optional[int]:
        """Days remaining until the shelf expires. Negative if expired."""
        exp = self.shelf_expires
        if not exp:
            return None
        return (exp - date.today()).days

    @cached_property
    def review_period_days(self) -> Optional[int]:
        """Days between shelf filing (S-3) and declared effective (EFFECT)."""
        if not self.shelf_filed_date or not self.effective_date:
            return None
        filed = _parse_filing_date(self.shelf_filed_date)
        eff = _parse_filing_date(self.effective_date)
        if filed and eff:
            return (eff - filed).days
        return None

    @cached_property
    def takedowns(self) -> List['Filing']:
        """All 424B* takedown filings, in chronological order."""
        result = []
        for f in self._related:
            base_form = f.form.replace('/A', '')
            if base_form in _TAKEDOWN_FORMS:
                result.append(f)
        # Enforce chronological order here rather than trusting _related's
        # ordering — avg_days_between_takedowns, days_since_last_takedown, and
        # the takedown-based expiry bound all depend on ascending filing_date.
        result.sort(key=lambda f: (_parse_filing_date(f.filing_date) or date.min,
                                    f.accession_no))
        return result

    @cached_property
    def total_takedowns(self) -> int:
        """Total number of takedowns under this shelf."""
        return len(self.takedowns)

    @cached_property
    def takedown_number(self) -> Optional[int]:
        """1-based position of the current filing among takedowns."""
        for i, f in enumerate(self.takedowns, 1):
            if f.accession_no == self._current.accession_no:
                return i
        return None

    @cached_property
    def is_latest_takedown(self) -> bool:
        """Whether the current filing is the most recent takedown."""
        return self.takedown_number == self.total_takedowns

    @cached_property
    def avg_days_between_takedowns(self) -> Optional[float]:
        """Average days between consecutive takedowns."""
        if len(self.takedowns) < 2:
            return None
        dates = []
        for f in self.takedowns:
            d = _parse_filing_date(f.filing_date)
            if d:
                dates.append(d)
        if len(dates) < 2:
            return None
        gaps = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
        return sum(gaps) / len(gaps)

    @cached_property
    def related_8k(self) -> Optional['Filing']:
        """8-K filed on the same day as the current filing, if any."""
        for f in self._related:
            if f.form == '8-K' and str(f.filing_date) == str(self._current.filing_date):
                return f
        return None

    # ------------------------------------------------------------------
    # Derived lifecycle signals
    # ------------------------------------------------------------------

    @cached_property
    def _generations(self) -> List[date]:
        """Effective dates of each shelf generation, ascending.

        One entry per effectiveness event: each EFFECT notice, plus each
        automatic (ASR) shelf filing — automatic shelves are effective on
        filing and never receive an EFFECT notice. A re-registration adds a
        generation; this underpins re-registration and continuity detection.
        """
        dates = {_parse_filing_date(f.filing_date)
                 for f in self._related if f.form == 'EFFECT'}
        dates |= {_parse_filing_date(f.filing_date) for f in self._related
                  if f.form.replace('/A', '') in _ASR_BASE_FORMS}
        return sorted(d for d in dates if d is not None)

    @cached_property
    def is_automatic_shelf(self) -> bool:
        """Whether this is an automatic (WKSI) shelf — S-3ASR/F-3ASR.

        Automatic shelves are effective on filing with no SEC review. An
        issuer-class signal: only well-known seasoned issuers may use them.
        """
        return any(f.form.replace('/A', '') in _ASR_BASE_FORMS for f in self._related)

    @cached_property
    def is_effective(self) -> bool:
        """Whether the shelf has been declared effective.

        True if an effectiveness event exists (EFFECT or automatic shelf) OR any
        takedown exists — a takedown proves effectiveness even when the EFFECT
        notice has scrolled out of the recent filing window.
        """
        return bool(self._generations) or self.total_takedowns > 0

    @cached_property
    def is_withdrawn(self) -> bool:
        """Whether the shelf registration has been withdrawn and not rescinded.

        A shelf is withdrawn if it has an 'RW' (Registration Withdrawal) request
        that has not been undone by a later 'RW WD' (withdrawal of that request).
        'AW' (withdrawal of an amendment) does not withdraw the registration.
        """
        rw_dates = [_parse_filing_date(f.filing_date)
                    for f in self._related if f.form == 'RW']
        rw_dates = [d for d in rw_dates if d is not None]
        if not rw_dates:
            return False
        rescind_dates = [_parse_filing_date(f.filing_date)
                         for f in self._related if f.form == 'RW WD']
        rescind_dates = [d for d in rescind_dates if d is not None]
        if not rescind_dates:
            return True
        # Withdrawn only if the latest request is more recent than the latest rescission.
        return max(rw_dates) > max(rescind_dates)

    @cached_property
    def is_re_registered(self) -> bool:
        """Whether the shelf has been re-registered (more than one generation).

        When true, the visible vintage (:attr:`shelf_filed_date`) is not the
        operative document; the operative effectiveness is
        :attr:`current_effective_date`.
        """
        return len(self._generations) > 1

    @cached_property
    def continuity(self) -> Optional[str]:
        """Whether shelf coverage has been continuous across re-registrations.

        ``'continuous'`` when each generation became effective on or before the
        prior generation's expiry (Rule 415(a)(6) renewal — securities and fees
        carry forward, no gap). ``'lapsed'`` when any generation became effective
        only after the prior one expired (a revival after a gap with no shelf
        access). None when there is no effectiveness event. A single generation
        is trivially continuous.
        """
        gens = self._generations
        if not gens:
            return None
        for prev, nxt in zip(gens, gens[1:]):
            if nxt > _plus_three_years(prev):
                return 'lapsed'
        return 'continuous'

    @cached_property
    def has_registration_gap(self) -> bool:
        """Data-quality flag: a generation became effective after the prior expired.

        Within a single file number this should not happen under Rule 415 — it
        usually means a revival (a fresh registration reusing the file number)
        and is worth investigating the filing linkage rather than treating the
        shelf as continuously registered.
        """
        return self.continuity == 'lapsed'

    @cached_property
    def status(self) -> str:
        """Lifecycle status: withdrawn | expired | effective | registered.

        Precedence: a withdrawal is terminal; then an effective shelf past its
        expiry is expired; then effective; otherwise registered (filed but not
        yet effective).
        """
        if self.is_withdrawn:
            return 'withdrawn'
        if self.is_effective:
            exp = self.shelf_expires
            if exp and date.today() > exp:
                return 'expired'
            if exp is None and self.takedowns:
                # Effectiveness proven by a takedown but the EFFECT/ASR date is
                # outside the loaded window, so shelf_expires is unknown. A shelf
                # cannot take down after it expires, so the latest takedown + 3y
                # is a guaranteed upper bound on expiry: past it means expired.
                last_td = _parse_filing_date(self.takedowns[-1].filing_date)
                if last_td and date.today() > _plus_three_years(last_td):
                    return 'expired'
            return 'effective'
        return 'registered'

    @cached_property
    def program_mode(self) -> str:
        """Takedown cadence: 'high_frequency' (> 50 takedowns) else 'standard'."""
        return 'high_frequency' if self.total_takedowns > 50 else 'standard'

    @cached_property
    def days_since_last_takedown(self) -> Optional[int]:
        """Days from the most recent takedown to today. None if no takedowns."""
        if not self.takedowns:
            return None
        last = _parse_filing_date(self.takedowns[-1].filing_date)
        return (date.today() - last).days if last else None

    @cached_property
    def program_age_days(self) -> Optional[int]:
        """Age of the shelf program in days.

        Measured from the *original* effectiveness only when coverage has been
        continuous; for a lapsed/revived shelf it measures from the *current*
        effectiveness, since the original program no longer applies. None when
        not yet effective.
        """
        gens = self._generations
        if not gens:
            return None
        anchor = gens[0] if self.continuity == 'continuous' else gens[-1]
        return (date.today() - anchor).days

    # ------------------------------------------------------------------
    # Shelf capacity
    # ------------------------------------------------------------------

    @cached_property
    def shelf_capacity(self) -> Optional['RegistrationFeeTable']:
        """Fee table from the shelf registration (S-3/F-3/S-1).

        Parses the EX-FILING FEES exhibit on the shelf registration to extract
        the total registered offering amount and per-security breakdowns.
        Returns None if no shelf registration found or no fee exhibit.
        """
        reg = self.shelf_registration
        if not reg:
            return None
        try:
            from edgar.offerings.prospectus._fee_table import extract_registration_fee_table
            return extract_registration_fee_table(reg)
        except Exception as e:
            log.debug("Failed to extract shelf capacity for %s: %s",
                      self._current.accession_no, e)
            return None

    @cached_property
    def total_offering_capacity(self) -> Optional[float]:
        """Total registered offering amount from the shelf's fee table (dollars)."""
        ft = self.shelf_capacity
        return ft.total_offering_amount if ft else None

    # ------------------------------------------------------------------
    # Rich display
    # ------------------------------------------------------------------

    def __rich__(self):
        company_name = self._current.company

        # Summary table
        summary = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        summary.add_column("field", style="bold deep_sky_blue1", min_width=24)
        summary.add_column("value")

        status_label = self.status.capitalize()
        if self.continuity == 'lapsed':
            status_label += " (re-registered after a gap)"
        elif self.is_re_registered:
            status_label += " (re-registered)"
        summary.add_row("Status", status_label)

        reg = self.shelf_registration
        if reg:
            summary.add_row("Shelf Registration", f"{reg.form} filed {reg.filing_date}")

        eff = self._initial_effective_filing
        if eff:
            review = f" ({self.review_period_days} days review)" if self.review_period_days is not None else ""
            summary.add_row("Effective Date", f"{eff.filing_date}{review}")

        cur = self._current_effective_filing
        if cur and (eff is None or cur.filing_date != eff.filing_date):
            summary.add_row("Current Effective", f"{cur.filing_date} (re-registered)")

        exp = self.shelf_expires
        if exp:
            remaining = self.days_to_expiry
            if remaining is not None and remaining > 0:
                summary.add_row("Shelf Expires", f"{exp} ({remaining} days remaining)")
            elif remaining is not None and remaining == 0:
                summary.add_row("Shelf Expires", f"{exp} (expires today)")
            elif remaining is not None:
                summary.add_row("Shelf Expires", f"{exp} (EXPIRED)")
            else:
                summary.add_row("Shelf Expires", str(exp))

        td_num = self.takedown_number
        if td_num is not None:
            latest = " (latest)" if self.is_latest_takedown else ""
            summary.add_row("Takedown Position", f"#{td_num} of {self.total_takedowns}{latest}")

        avg = self.avg_days_between_takedowns
        if avg is not None:
            summary.add_row("Avg Cadence", f"{avg:.0f} days between takedowns")

        # Timeline table
        timeline = Table(box=box.SIMPLE, padding=(0, 1))
        timeline.add_column("#", style="dim", justify="right")
        timeline.add_column("Form", style="bold")
        timeline.add_column("Date")
        timeline.add_column("Description")

        takedown_idx = 0
        for i, f in enumerate(self._related, 1):
            base_form = f.form.replace('/A', '')
            is_current = f.accession_no == self._current.accession_no

            if base_form in _SHELF_BASE_FORMS:
                desc = "Shelf registration"
            elif f.form == 'EFFECT':
                desc = "Declared effective"
            elif base_form in _TAKEDOWN_FORMS:
                takedown_idx += 1
                desc = f"Takedown #{takedown_idx}"
            elif f.form == '8-K':
                desc = "Current report"
            else:
                desc = ""

            marker = "  << current" if is_current else ""
            style = "bold green" if is_current else None
            timeline.add_row(str(i), f.form, str(f.filing_date), f"{desc}{marker}", style=style)

        return Panel(
            Group(summary, Text(""), timeline),
            title=f"[bold]Shelf Lifecycle: {company_name}[/bold]",
            box=box.ROUNDED,
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __str__(self):
        td = self.takedown_number
        pos = f"#{td}/{self.total_takedowns}" if td else "?"
        return f"ShelfLifecycle(takedown={pos}, takedowns={self.total_takedowns})"

    # ------------------------------------------------------------------
    # AI context
    # ------------------------------------------------------------------

    def to_context(self, detail: str = 'standard') -> str:
        """Returns AI-optimized shelf lifecycle context for language models.

        Args:
            detail: Level of detail - 'minimal', 'standard', or 'full'

        Returns:
            Markdown-KV formatted context string optimized for LLMs
        """
        lines = []
        lines.append(f"SHELF LIFECYCLE: {self._current.company}")
        lines.append("")

        reg = self.shelf_registration
        if reg:
            lines.append(f"Shelf Registration: {reg.form} filed {reg.filing_date}")
        if self.effective_date:
            review = f" ({self.review_period_days} days review)" if self.review_period_days is not None else ""
            lines.append(f"Effective Date: {self.effective_date}{review}")
        if self.shelf_expires:
            remaining = self.days_to_expiry
            if remaining is not None and remaining > 0:
                lines.append(f"Shelf Expires: {self.shelf_expires} ({remaining} days remaining)")
            elif remaining is not None and remaining == 0:
                lines.append(f"Shelf Expires: {self.shelf_expires} (expires today)")
            elif remaining is not None:
                lines.append(f"Shelf Expires: {self.shelf_expires} (EXPIRED)")

        td_num = self.takedown_number
        if td_num is not None:
            latest = " (latest)" if self.is_latest_takedown else ""
            lines.append(f"Takedown Position: #{td_num} of {self.total_takedowns}{latest}")

        avg = self.avg_days_between_takedowns
        if avg is not None:
            lines.append(f"Avg Cadence: {avg:.0f} days between takedowns")

        if detail in ('standard', 'full'):
            lines.append("")
            lines.append("TIMELINE:")
            takedown_idx = 0
            for f in self._related:
                base_form = f.form.replace('/A', '')
                is_current = f.accession_no == self._current.accession_no
                marker = " << current" if is_current else ""

                if base_form in _SHELF_BASE_FORMS:
                    desc = "Shelf registration"
                elif f.form == 'EFFECT':
                    desc = "Declared effective"
                elif base_form in _TAKEDOWN_FORMS:
                    takedown_idx += 1
                    desc = f"Takedown #{takedown_idx}"
                elif f.form == '8-K':
                    desc = "Current report"
                else:
                    desc = ""

                lines.append(f"  {f.form:10s} {f.filing_date}  {desc}{marker}")

        if detail == 'full':
            lines.append("")
            lines.append("AVAILABLE ACTIONS:")
            lines.append("  - .shelf_registration -> Filing object for the S-3/F-3/S-1")
            lines.append("  - .takedowns -> list of all 424B* takedown Filing objects")
            lines.append("  - .filings -> full Filings set under this shelf")

        return "\n".join(lines)
