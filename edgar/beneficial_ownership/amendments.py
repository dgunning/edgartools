"""
Amendment tracking and comparison for Schedule 13D/G filings.

This module provides utilities for linking amendments to original filings
and comparing ownership changes between filings.
"""
import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from edgar.beneficial_ownership.schedule13 import Schedule13D, Schedule13G

__all__ = ['AmendmentInfo', 'OwnershipComparison']


@dataclass
class AmendmentInfo:
    """
    Amendment metadata and links.

    Tracks whether a filing is an amendment and provides information
    about the amendment number and links to the original filing.
    """
    is_amendment: bool
    amendment_number: Optional[int]  # /A, /A 1, /A 2, etc.
    original_accession: Optional[str]

    @classmethod
    def from_filing(cls, filing):
        """
        Extract amendment information from a Filing object.

        Args:
            filing: Filing object

        Returns:
            AmendmentInfo instance
        """
        is_amend = '/A' in filing.form

        # Parse amendment number from form
        amend_num = None
        if is_amend:
            # Extract from "SCHEDULE 13D/A" or "SCHEDULE 13D/A 1"
            parts = filing.form.split('/A')
            if len(parts) > 1 and parts[1].strip():
                try:
                    amend_num = int(parts[1].strip())
                except ValueError:
                    amend_num = 1
            else:
                amend_num = 1

        return cls(
            is_amendment=is_amend,
            amendment_number=amend_num,
            original_accession=None  # Populated separately if needed
        )


def _reported_sum(schedule: 'Schedule13D | Schedule13G', figure: str):
    """Sum of one figure over the reporting persons, or None when the filing does not report it.

    A figure is unreported when a reporting person leaves it out (an amendment may,
    and a pre-2025 filing read from its SGML header has identities only), or when
    the filing has no reporting-person rows at all. None of those means zero shares.
    """
    if not schedule.has_structured_data or not schedule.reporting_persons:
        return None
    values = [p.reported(figure) for p in schedule.reporting_persons]
    if None in values:
        return None
    return sum(values)


def _placeholder_sum(schedule: 'Schedule13D | Schedule13G', figure: str):
    """Sum of one figure over the reporting persons, reading an unreported figure as 0 (the 5.x values)."""
    return sum(getattr(p, figure) for p in schedule.reporting_persons)


def _warn_unreported(name: str, replacement: str) -> None:
    # The text is fixed per property so Python's default filter shows it once per call site.
    warnings.warn(
        f"OwnershipComparison.{name} is computed from figures a filing does not report, read as 0. "
        f"It will be None in edgartools 6.0. Use OwnershipComparison.{replacement}, which is None today.",
        FutureWarning,
        stacklevel=3,
    )


@dataclass
class OwnershipComparison:
    """
    Compare two Schedule 13D or 13G filings.

    Useful for tracking ownership changes between the original filing
    and an amendment, or between two amendments.

    A change is known only when both filings report the figure for every
    reporting person. An amendment may leave the figures out, a pre-2025 filing
    read from its SGML header has none, and a filing may have no reporting-person
    rows. ``reported_shares_change`` and ``reported_percent_change`` are None then,
    and ``is_accumulating``, ``is_liquidating`` and ``is_unchanged`` are all False.

    Example:
        original = Schedule13D.from_filing(original_filing)
        amendment = Schedule13D.from_filing(amended_filing)
        comparison = OwnershipComparison(current=amendment, previous=original)

        if comparison.reported_shares_change is not None:
            print(f"Shares changed by: {comparison.reported_shares_change:,}")
        print(f"Is accumulating: {comparison.is_accumulating}")
    """
    current: 'Schedule13D | Schedule13G'
    previous: 'Schedule13D | Schedule13G'

    @property
    def reported_shares_change(self) -> Optional[int]:
        """
        Change in total shares owned, or None when either filing does not report its share counts.

        Returns:
            Net change in share count (positive = increased, negative = decreased),
            or None for a figure left out of an amendment, a pre-2025 header-only
            filing, or a filing with no reporting-person rows. A reported 0 is a number.
        """
        curr_shares = _reported_sum(self.current, 'aggregate_amount')
        prev_shares = _reported_sum(self.previous, 'aggregate_amount')
        if curr_shares is None or prev_shares is None:
            return None
        return curr_shares - prev_shares

    @property
    def reported_percent_change(self) -> Optional[float]:
        """
        Change in ownership percentage, or None when either filing does not report its percentages.

        Returns:
            Net change in ownership percentage (e.g., 1.5 means increased by 1.5%),
            or None as for ``reported_shares_change``
        """
        curr_pct = _reported_sum(self.current, 'percent_of_class')
        prev_pct = _reported_sum(self.previous, 'percent_of_class')
        if curr_pct is None or prev_pct is None:
            return None
        return curr_pct - prev_pct

    @property
    def shares_change(self) -> int:
        """
        Change in total shares owned.

        Returns:
            Net change in share count (positive = increased, negative = decreased).
            A figure a filing does not report counts as 0 here and emits a
            ``FutureWarning``: in edgartools 6.0 this returns None instead, as
            ``reported_shares_change`` does today.
        """
        if self.reported_shares_change is None:
            _warn_unreported('shares_change', 'reported_shares_change')
        return _placeholder_sum(self.current, 'aggregate_amount') - _placeholder_sum(self.previous, 'aggregate_amount')

    @property
    def percent_change(self) -> float:
        """
        Change in ownership percentage.

        Returns:
            Net change in ownership percentage (e.g., 1.5 means increased by 1.5%).
            A figure a filing does not report counts as 0 here and emits a
            ``FutureWarning``: in edgartools 6.0 this returns None instead, as
            ``reported_percent_change`` does today.
        """
        if self.reported_percent_change is None:
            _warn_unreported('percent_change', 'reported_percent_change')
        return _placeholder_sum(self.current, 'percent_of_class') - _placeholder_sum(self.previous, 'percent_of_class')

    @property
    def is_accumulating(self) -> bool:
        """Check if shares increased (False when the change is unknown)"""
        change = self.reported_shares_change
        return change is not None and change > 0

    @property
    def is_liquidating(self) -> bool:
        """Check if shares decreased (False when the change is unknown)"""
        change = self.reported_shares_change
        return change is not None and change < 0

    @property
    def is_unchanged(self) -> bool:
        """Check if shareholding is unchanged (False when the change is unknown)"""
        return self.reported_shares_change == 0

    def get_summary(self) -> dict:
        """
        Get summary of changes.

        Returns:
            Dictionary with change metrics. The share and percent values read a
            figure a filing does not report as 0, as ``shares_change`` does, and
            emit the same ``FutureWarning``; ``reported_shares_change`` and
            ``reported_percent_change`` are None for them.
        """
        return {
            'previous_filing_date': self.previous.filing_date,
            'current_filing_date': self.current.filing_date,
            'previous_shares': _placeholder_sum(self.previous, 'aggregate_amount'),
            'current_shares': _placeholder_sum(self.current, 'aggregate_amount'),
            'shares_change': self.shares_change,
            'previous_percent': _placeholder_sum(self.previous, 'percent_of_class'),
            'current_percent': _placeholder_sum(self.current, 'percent_of_class'),
            'percent_change': self.percent_change,
            'reported_shares_change': self.reported_shares_change,
            'reported_percent_change': self.reported_percent_change,
            'is_accumulating': self.is_accumulating,
            'is_liquidating': self.is_liquidating,
            'is_unchanged': self.is_unchanged
        }


def get_amendment_info(schedule: 'Schedule13D | Schedule13G') -> AmendmentInfo:
    """
    Get amendment information for a schedule.

    Args:
        schedule: Schedule13D or Schedule13G instance

    Returns:
        AmendmentInfo instance
    """
    return AmendmentInfo.from_filing(schedule._filing)


def get_original_filing(schedule: 'Schedule13D | Schedule13G') -> Optional['Schedule13D | Schedule13G']:
    """
    Get the original filing that this schedule amends.

    Args:
        schedule: Schedule13D or Schedule13G amendment

    Returns:
        Original Schedule13D/G instance or None if not found/not an amendment
    """
    if not schedule.is_amendment:
        return None

    # Search for original filing using related_filings for efficiency
    try:
        # Determine base form
        base_form = schedule._filing.form.split('/A')[0].strip()

        # Use related_filings() for more efficient lookup (same filer)
        # Filter for non-amendments before this filing date
        filings = schedule._filing.related_filings(
            filing_date=f':{schedule.filing_date}',
            amendments=False
        )

        # Get the most recent non-amendment (last in chronological order)
        if filings:
            original_filing = filings[-1]

            # Create instance of same type
            if base_form == 'SCHEDULE 13D':
                from edgar.beneficial_ownership.schedule13 import Schedule13D
                return Schedule13D.from_filing(original_filing)
            else:
                from edgar.beneficial_ownership.schedule13 import Schedule13G
                return Schedule13G.from_filing(original_filing)

    except Exception:
        # If filing search fails, return None
        pass

    return None


def compare_to_previous(schedule: 'Schedule13D | Schedule13G',
                       previous: Optional['Schedule13D | Schedule13G'] = None) -> Optional[OwnershipComparison]:
    """
    Compare schedule with previous filing.

    Args:
        schedule: Current schedule
        previous: Previous schedule (if None, will attempt to find original)

    Returns:
        OwnershipComparison instance or None if no previous filing found
    """
    if previous is None:
        previous = get_original_filing(schedule)

    if previous is None:
        return None

    return OwnershipComparison(current=schedule, previous=previous)
