"""424B* table classification and extraction.

Classifies tables from filing.parse().tables into semantic types, then extracts
structured data from identified tables. Split into focused submodules:

- ``helpers``      cell/text utilities shared across the package
- ``classifiers``  ``_is_*`` predicates + ``classify_table`` / ``classify_tables_in_document``
- ``extractors``   ``extract_*`` routines that build prospectus models
- ``underwriters`` underwriter/agent-name recognition and extraction

This package preserves the original ``edgar.offerings.prospectus._424b_tables`` import
surface — every name importable from the former single module is re-exported.

See table-classification research for validation results and edge cases.
"""

from __future__ import annotations

from edgar.offerings.prospectus._424b_tables.helpers import (
    _WS_RE,
    _get_table_cells,
    _get_all_cells_including_headers,
    _get_full_text,
    _get_row_texts,
    _fraction_long_cells,
    _has_numeric_cells,
    _prefix_dollar,
    _extract_row_label_and_values,
)
from edgar.offerings.prospectus._424b_tables.classifiers import (
    _PAGE_NUMBER_RE,
    _is_layout_table,
    _is_toc_table,
    _is_pricing_table,
    _is_offering_summary,
    _is_selling_stockholders,
    _is_key_terms,
    _is_dilution,
    _is_capitalization,
    _is_underwriting_syndicate,
    _is_expenses,
    classify_table,
    classify_tables_in_document,
)
from edgar.offerings.prospectus._424b_tables.extractors import (
    extract_pricing_data,
    extract_offering_terms,
    extract_dilution_data,
    extract_capitalization_data,
    _build_column_map,
    _assign_entry_values,
    extract_selling_stockholders_data,
    extract_structured_note_terms,
)
from edgar.offerings.prospectus._424b_tables.underwriters import (
    _ALLOC_SKIP_LABELS,
    _BANK_PATTERNS,
    _count_bank_hits,
    _clean_underwriter_name,
    _UW_NAME_LOWER_OK,
    _UW_NAME_DENYLIST,
    _looks_like_term_fragment,
    is_plausible_underwriter_name,
    extract_underwriting_from_tables,
)

__all__ = [
    'classify_table',
    'classify_tables_in_document',
    'extract_pricing_data',
    'extract_offering_terms',
    'extract_dilution_data',
    'extract_capitalization_data',
    'extract_selling_stockholders_data',
    'extract_structured_note_terms',
    'extract_underwriting_from_tables',
]
