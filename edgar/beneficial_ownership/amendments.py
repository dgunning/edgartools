"""
Amendment tracking and comparison for Schedule 13D/G filings.

This module provides utilities for linking amendments to original filings
and comparing ownership changes between filings.
"""
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


def _reported_shares(schedule: 'Schedule13D | Schedule13G') -> Optional[int]:
    """Sum of the reporting persons' shares, or None when the filing reports none.

    A pre-2025 header-only filing (``has_structured_data`` is False) carries its
    reporting persons as identities with placeholder zeros, and a filing parsed
    with no reporting-person rows has no numbers at all. Neither holds zero shares.
    """
    if not schedule.has_structured_data or not schedule.reporting_persons:
        return None
    return sum(p.aggregate_amount for p in schedule.reporting_persons)


def _reported_percent(schedule: 'Schedule13D | Schedule13G') -> Optional[float]:
    """Sum of the reporting persons' percentages, or None as for ``_reported_shares``."""
    if not schedule.has_structured_data or not schedule.reporting_persons:
        return None
    return sum(p.percent_of_class for p in schedule.reporting_persons)


@dataclass
class OwnershipComparison:
    """
    Compare two Schedule 13D or 13G filings.

    Useful for tracking ownership changes between the original filing
    and an amendment, or between two amendments.

    Example:
        original = Schedule13D.from_filing(original_filing)
        amendment = Schedule13D.from_filing(amended_filing)
        comparison = OwnershipComparison(current=amendment, previous=original)

        if comparison.shares_change is not None:
            print(f"Shares changed by: {comparison.shares_change:,}")
        print(f"Is accumulating: {comparison.is_accumulating}")
    """
    current: 'Schedule13D | Schedule13G'
    previous: 'Schedule13D | Schedule13G'

    @property
    def shares_change(self) -> Optional[int]:
        """
        Change in total shares owned.

        Returns:
            Net change in share count (positive = increased, negative = decreased),
            or None when either filing has no reporting-person share data
            (a pre-2025 header-only filing, or no reporting-person rows)
        """
        curr_shares = _reported_shares(self.current)
        prev_shares = _reported_shares(self.previous)
        if curr_shares is None or prev_shares is None:
            return None
        return curr_shares - prev_shares

    @property
    def percent_change(self) -> Optional[float]:
        """
        Change in ownership percentage.

        Returns:
            Net change in ownership percentage (e.g., 1.5 means increased by 1.5%),
            or None when either filing has no reporting-person data
        """
        curr_pct = _reported_percent(self.current)
        prev_pct = _reported_percent(self.previous)
        if curr_pct is None or prev_pct is None:
            return None
        return curr_pct - prev_pct

    @property
    def is_accumulating(self) -> bool:
        """Check if shares increased (False when the change is unknown)"""
        change = self.shares_change
        return change is not None and change > 0

    @property
    def is_liquidating(self) -> bool:
        """Check if shares decreased (False when the change is unknown)"""
        change = self.shares_change
        return change is not None and change < 0

    @property
    def is_unchanged(self) -> bool:
        """Check if shareholding is unchanged (False when the change is unknown)"""
        return self.shares_change == 0

    def get_summary(self) -> dict:
        """
        Get summary of changes.

        Returns:
            Dictionary with change metrics. Share and percent values are None
            for a filing without reporting-person data.
        """
        return {
            'previous_filing_date': self.previous.filing_date,
            'current_filing_date': self.current.filing_date,
            'previous_shares': _reported_shares(self.previous),
            'current_shares': _reported_shares(self.current),
            'shares_change': self.shares_change,
            'previous_percent': _reported_percent(self.previous),
            'current_percent': _reported_percent(self.current),
            'percent_change': self.percent_change,
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
