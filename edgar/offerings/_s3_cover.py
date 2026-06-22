"""
S-3 cover-page extraction and offering-type classification.

Mirrors the S-1 layout (``_s1_cover`` / ``_s1_classifier``): the cover-page
model, checkbox parsing, field extraction, and offering-type classification live
here, separate from the ``RegistrationS3`` data object in ``registration_s3``.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Optional, TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from edgar._filings import Filing

__all__ = ['S3OfferingType', 'S3CoverPage', '_extract_s3_cover_page',
           '_classify_s3_offering', '_is_checked']


# ---------------------------------------------------------------------------
# Offering Type
# ---------------------------------------------------------------------------

class S3OfferingType(str, Enum):
    """Classification of S-3 registration types."""
    UNIVERSAL_SHELF = "universal_shelf"
    RESALE = "resale"
    DEBT = "debt"
    AUTO_SHELF = "auto_shelf"  # S-3ASR
    UNKNOWN = "unknown"

    @property
    def display_name(self) -> str:
        return {
            "universal_shelf": "Universal Shelf",
            "resale": "Resale Registration",
            "debt": "Debt Offering",
            "auto_shelf": "Automatic Shelf (S-3ASR)",
            "unknown": "Unknown",
        }[self.value]


# ---------------------------------------------------------------------------
# Cover Page Model
# ---------------------------------------------------------------------------

class S3CoverPage(BaseModel):
    """Extracted cover page fields from an S-3 filing."""
    company_name: str
    registration_number: Optional[str] = None
    state_of_incorporation: Optional[str] = None
    ein: Optional[str] = None

    # Filer category checkboxes
    is_large_accelerated_filer: Optional[bool] = None
    is_accelerated_filer: Optional[bool] = None
    is_non_accelerated_filer: Optional[bool] = None
    is_smaller_reporting_company: Optional[bool] = None
    is_emerging_growth_company: Optional[bool] = None

    # Rule checkboxes
    is_rule_415: bool = False
    is_rule_462b: bool = False
    is_rule_462e: bool = False  # Auto-shelf

    # Extraction confidence
    confidence: str = "low"  # low, medium, high


# ---------------------------------------------------------------------------
# Cover Page Extraction
# ---------------------------------------------------------------------------

# Unicode check marks: \u2612 (checked) = checked; \u2610 (unchecked)
_CHECKED = re.compile(r'[\u2611\u2612\u2713\u2714]|&#9746;|&#9745;')
_UNCHECKED = re.compile(r'[\u2610]|&#9744;')


def _is_checked(text: str, label: str) -> Optional[bool]:
    """Check if a labeled checkbox is checked or unchecked in cover page text.

    SEC filings place checkmarks either before or after the label, often
    separated by HTML tags.  We search a 200-char window in both directions.
    """
    pattern = re.compile(re.escape(label), re.IGNORECASE)
    match = pattern.search(text)
    if not match:
        return None
    # Look 200 chars after the label (checkmark often follows, separated by HTML)
    after_region = text[match.end():match.end() + 200]
    # Look 200 chars before the label
    before_region = text[max(0, match.start() - 200):match.start()]

    # Find the nearest checkmark in either direction
    after_checked = _CHECKED.search(after_region)
    after_unchecked = _UNCHECKED.search(after_region)
    before_checked = _CHECKED.search(before_region)
    before_unchecked = _UNCHECKED.search(before_region)

    # Prefer the closest mark to the label
    # After-label marks
    after_pos = None
    after_val = None
    if after_checked:
        after_pos = after_checked.start()
        after_val = True
    if after_unchecked and (after_pos is None or after_unchecked.start() < after_pos):
        after_pos = after_unchecked.start()
        after_val = False

    # Before-label marks (distance from end of before_region = closer to label)
    before_pos = None
    before_val = None
    if before_checked:
        before_pos = len(before_region) - before_checked.end()
        before_val = True
    if before_unchecked:
        dist = len(before_region) - before_unchecked.end()
        if before_pos is None or dist < before_pos:
            before_pos = dist
            before_val = False

    # Return whichever mark is closest to the label
    if after_pos is not None and before_pos is not None:
        return after_val if after_pos <= before_pos else before_val
    if after_pos is not None:
        return after_val
    if before_pos is not None:
        return before_val
    return None


def _extract_s3_cover_page(filing: 'Filing', html: str) -> S3CoverPage:
    """Extract cover page fields from S-3 HTML."""
    cover_text = html[:25000]

    # Company name from filing metadata
    company_name = filing.company

    # Registration number: 333-XXXXXX
    reg_match = re.search(r'333-(\d{5,7})', cover_text)
    registration_number = f"333-{reg_match.group(1)}" if reg_match else None

    # State of incorporation — appears in a table cell above "(State or other jurisdiction..."
    # Pattern: look for text content in the same column, just before the jurisdiction label
    state_of_incorporation = None
    state_label_match = re.search(
        r'State\s+or\s+other\s+jurisdiction',
        cover_text, re.IGNORECASE
    )
    if state_label_match:
        # Look backwards in the HTML for a text value (state name)
        before = cover_text[max(0, state_label_match.start() - 500):state_label_match.start()]
        # Find bold text content (typically <B>Delaware</B>) or plain text between tags
        state_candidates = re.findall(r'<[Bb]>([A-Z][A-Za-z\s]{2,30}?)</[Bb]>', before)
        if not state_candidates:
            # Try plain text between closing and opening tags
            state_candidates = re.findall(r'>([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)<', before)
        if state_candidates:
            # Take the last one (closest to the label)
            state_of_incorporation = state_candidates[-1].strip()

    # EIN
    ein_match = re.search(r'(\d{2}-\d{7})', cover_text)
    ein = ein_match.group(1) if ein_match else None

    # Filer category checkboxes
    # SEC filings use &nbsp; (\xa0), normal spaces, or HTML entity &nbsp; interchangeably.
    # Try all three variants for each label.
    def _check_label(text, label):
        """Try a label with normal spaces, \xa0, and &nbsp;."""
        result = _is_checked(text, label)
        if result is None:
            result = _is_checked(text, label.replace(' ', '\xa0'))
        if result is None:
            result = _is_checked(text, label.replace(' ', '&nbsp;'))
        return result

    is_large_accelerated = _check_label(cover_text, 'Large accelerated filer')
    is_accelerated = _check_label(cover_text, 'Accelerated filer')
    is_non_accelerated = _check_label(cover_text, 'Non-accelerated filer')
    is_smaller_reporting = _check_label(cover_text, 'Smaller reporting company')
    is_egc = _check_label(cover_text, 'Emerging growth company')

    # Rule checkboxes
    is_rule_415 = bool(_check_label(cover_text, 'Rule 415'))
    is_rule_462b = bool(_check_label(cover_text, 'Rule 462(b)'))
    is_rule_462e = bool(_check_label(cover_text, 'Rule 462(e)')) or 'S-3ASR' in filing.form

    # Confidence
    fields_found = sum(1 for v in [registration_number, state_of_incorporation, ein,
                                    is_large_accelerated, is_smaller_reporting] if v is not None)
    confidence = "high" if fields_found >= 4 else "medium" if fields_found >= 2 else "low"

    return S3CoverPage(
        company_name=company_name,
        registration_number=registration_number,
        state_of_incorporation=state_of_incorporation,
        ein=ein,
        is_large_accelerated_filer=is_large_accelerated,
        is_accelerated_filer=is_accelerated,
        is_non_accelerated_filer=is_non_accelerated,
        is_smaller_reporting_company=is_smaller_reporting,
        is_emerging_growth_company=is_egc,
        is_rule_415=is_rule_415,
        is_rule_462b=is_rule_462b,
        is_rule_462e=is_rule_462e,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Offering Type Classification
# ---------------------------------------------------------------------------

def _classify_s3_offering(filing: 'Filing', fee_table, html: Optional[str] = None) -> S3OfferingType:
    """Classify the S-3 offering type."""
    # S-3ASR is always auto-shelf
    if 'ASR' in filing.form:
        return S3OfferingType.AUTO_SHELF

    # Check fee table for clues
    if fee_table and fee_table.fee_deferred:
        return S3OfferingType.AUTO_SHELF

    # Check HTML for resale indicators
    if html is None:
        html = filing.html()
    if html:
        cover = html[:30000].lower()
        if 'resale' in cover or 'selling stockholder' in cover or 'selling securityholder' in cover:
            return S3OfferingType.RESALE
        if 'debt securities' in cover and 'common stock' not in cover and 'preferred stock' not in cover:
            return S3OfferingType.DEBT

    return S3OfferingType.UNIVERSAL_SHELF
