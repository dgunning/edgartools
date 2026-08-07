from __future__ import annotations

from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from edgar.entity.entity_filings import EntityFilings


def split_list(states, chunk_size=10):
    # Split a list into sublist of size chunk_size
    return [states[i:i + chunk_size] for i in range(0, len(states), chunk_size)]


def maybe_float(value):
    if not value:
        return 0.00
    try:
        return float(value)
    except ValueError:
        return 0.00


def maybe_date(value):
    if not value:
        return None
    # Deferred import: FormC lives in .core, which imports this module — a
    # module-level import would create a cycle.
    from edgar.offerings.crowdfunding.formc.core import FormC
    try:
        return FormC.parse_date(value)
    except ValueError:
        return None


# NOTE: duplicated in edgar/offerings/__init__.py — consolidate in n094.7
def group_offerings_by_file_number(filings) -> Dict[str, 'EntityFilings']:
    """
    Group Form C filings by issuer file number.

    This utility efficiently groups crowdfunding filings using PyArrow operations,
    which is particularly useful for companies with many offerings. Each group
    represents one complete offering lifecycle (initial C, amendments, updates, etc.).

    Args:
        filings: EntityFilings containing Form C variant filings

    Returns:
        Dictionary mapping file numbers (020-XXXXX) to EntityFilings for that offering

    Example:
        >>> company = Company('1881570')  # ViiT Health
        >>> all_filings = company.get_filings(form=['C', 'C/A', 'C-U', 'C-AR'])
        >>> grouped = group_offerings_by_file_number(all_filings)
        >>> for file_num, offering_filings in grouped.items():
        ...     print(f"{file_num}: {len(offering_filings)} filings")
        020-28927: 1 filings
        020-32444: 3 filings
        020-36002: 4 filings

    Note:
        Uses PyArrow for efficient grouping. For small filing sets, a simple loop
        may be clearer, but this approach scales better for companies with many filings.
    """
    # Use PyArrow to get unique file numbers efficiently
    unique_file_numbers = filings.data['fileNumber'].unique()

    # Create grouped dictionary using filter
    return {
        str(fn): filings.filter(file_number=str(fn))
        for fn in unique_file_numbers.to_pylist()
    }
