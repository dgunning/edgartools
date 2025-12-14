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

        print(f"Shares changed by: {comparison.shares_change:,}")
        print(f"Is accumulating: {comparison.is_accumulating}")
    """
    current: 'Schedule13D | Schedule13G'
    previous: 'Schedule13D | Schedule13G'

    @property
    def shares_change(self) -> int:
        """
        Change in total shares owned.

        Returns:
            Net change in share count (positive = increased, negative = decreased)
        """
        curr_shares = sum(p.aggregate_amount for p in self.current.reporting_persons)
        prev_shares = sum(p.aggregate_amount for p in self.previous.reporting_persons)
        return curr_shares - prev_shares

    @property
    def percent_change(self) -> float:
        """
        Change in ownership percentage.

        Returns:
            Net change in ownership percentage (e.g., 1.5 means increased by 1.5%)
        """
        curr_pct = sum(p.percent_of_class for p in self.current.reporting_persons)
        prev_pct = sum(p.percent_of_class for p in self.previous.reporting_persons)
        return curr_pct - prev_pct

    @property
    def is_accumulating(self) -> bool:
        """Check if shares increased"""
        return self.shares_change > 0

    @property
    def is_liquidating(self) -> bool:
        """Check if shares decreased"""
        return self.shares_change < 0

    @property
    def is_unchanged(self) -> bool:
        """Check if shareholding is unchanged"""
        return self.shares_change == 0

    def get_summary(self) -> dict:
        """
        Get summary of changes.

        Returns:
            Dictionary with change metrics
        """
        return {
            'previous_filing_date': self.previous.filing_date,
            'current_filing_date': self.current.filing_date,
            'previous_shares': sum(p.aggregate_amount for p in self.previous.reporting_persons),
            'current_shares': sum(p.aggregate_amount for p in self.current.reporting_persons),
            'shares_change': self.shares_change,
            'previous_percent': sum(p.percent_of_class for p in self.previous.reporting_persons),
            'current_percent': sum(p.percent_of_class for p in self.current.reporting_persons),
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
