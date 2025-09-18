"""
Utility functions for entity processing.

This module contains utility functions used throughout the entity package
for data processing, normalization, and validation.
"""
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    import pyarrow

from edgar.entity.constants import COMPANY_FORMS


def has_company_filings(filings_form_array: 'pyarrow.ChunkedArray', max_filings: int = 50) -> bool:
    """
    Efficiently check if any form in the PyArrow ChunkedArray matches company-only forms.
    Limited to checking the first max_filings entries for performance.

    Args:
        filings_form_array: PyArrow ChunkedArray containing form values
        max_filings: Maximum number of filings to check

    Returns:
        True if any form matches a company form, False otherwise
    """

    # Early exit for empty arrays
    if filings_form_array.null_count == filings_form_array.length:
        return False

    # Handle case with fewer than max_filings
    total_filings = filings_form_array.length()
    filings_to_check = min(total_filings, max_filings)

    # Track how many we've checked so far
    checked_count = 0

    # Process chunks in the ChunkedArray until we hit our limit
    for chunk in filings_form_array.chunks:
        chunk_size = len(chunk)

        # If this chunk would exceed our limit, slice it
        if checked_count + chunk_size > filings_to_check:
            # Only check remaining forms needed to reach filings_to_check
            remaining = filings_to_check - checked_count
            sliced_chunk = chunk.slice(0, remaining)

            # Use safer iteration over array values
            for i in range(len(sliced_chunk)):
                # Get value safely, handling nulls
                val = sliced_chunk.take([i]).to_pylist()[0]
                if val is not None and val in COMPANY_FORMS:
                    return True
        else:
            # Process full chunk safely
            for val in chunk.to_pylist():
                if val is not None and val in COMPANY_FORMS:
                    return True

        # Update count of checked filings
        if checked_count + chunk_size > filings_to_check:
            checked_count += (filings_to_check - checked_count)
        else:
            checked_count += chunk_size

        # Stop if we've checked enough
        if checked_count >= filings_to_check:
            break

    return False


def normalize_cik(cik_or_identifier: Union[str, int]) -> int:
    """
    Normalize a CIK to an integer by removing leading zeros.

    Args:
        cik_or_identifier: CIK as string or integer

    Returns:
        Normalized CIK as integer

    Raises:
        ValueError: If the identifier cannot be converted to a valid CIK
    """
    if isinstance(cik_or_identifier, int):
        return cik_or_identifier

    if isinstance(cik_or_identifier, str):
        # Remove leading zeros and convert to int
        try:
            return int(cik_or_identifier.lstrip('0') or '0')
        except ValueError:
            raise ValueError(f"Invalid CIK format: {cik_or_identifier}")

    raise ValueError(f"CIK must be string or integer, got {type(cik_or_identifier)}")


def validate_cik(cik: int) -> bool:
    """
    Validate that a CIK is within the expected range.

    Args:
        cik: CIK to validate

    Returns:
        True if CIK is valid, False otherwise
    """
    # CIKs are typically 1-10 digits, with valid range roughly 1 to 2,000,000,000
    return isinstance(cik, int) and 1 <= cik <= 2_000_000_000


def format_cik(cik: Union[str, int], zero_pad: int = 10) -> str:
    """
    Format a CIK with zero padding for display or API calls.

    Args:
        cik: CIK to format
        zero_pad: Number of digits to pad to (default 10)

    Returns:
        Zero-padded CIK string

    Example:
        >>> format_cik(320193)
        '0000320193'
        >>> format_cik('320193', zero_pad=6)
        '320193'
    """
    normalized_cik = normalize_cik(cik)
    return str(normalized_cik).zfill(zero_pad)