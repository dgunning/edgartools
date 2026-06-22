"""
Registration fee table extraction from EX-FILING FEES exhibits (Exhibit 107).

Parses the HTML fee table attached to registration statements (S-3, F-3, S-1, etc.)
to extract total offering capacity, per-security breakdowns, and fee calculations.

Works with both plain HTML and inline XBRL exhibits (2022-2025+). For pre-EX-107
registration statements (~pre-2022) that carried the fee table inline in the
document body instead of an exhibit, falls back to _extract_inline_fee_table.

Split into focused submodules (this package preserves the original
``edgar.offerings.prospectus._fee_table`` import surface — every name importable from the
former single module is re-exported here):

- ``parsing``  pure HTML/text/number parsing of fee tables into dicts
- ``extract``  attachment resolution + orchestration + dict -> RegistrationFeeTable

See: docs-internal/research/sec-filings/forms/s-3/registration-fee-table-analysis.md
"""

from __future__ import annotations

from edgar.offerings.prospectus._fee_table.parsing import (
    _NUMERIC_TOKEN_RE,
    _parse_dollar_amount,
    _FEE_RATE_BASIS_RE,
    _parse_fee_rate,
    _FEE_RATE_MIN,
    _FEE_RATE_MAX,
    _refine_fee_columns,
    _join_dollar_cells,
    _extract_dollar_values,
    _is_placeholder,
    _table_text,
    _find_fee_table,
    _parse_fee_table_html,
    _parse_security_row_no_category,
    _has_data,
    _parse_security_row,
    _DOLLAR_RE,
    _DEFERRAL_MARKERS,
    _parse_inline_fee_table,
)
from edgar.offerings.prospectus._fee_table.extract import (
    _get_filing_fees_attachment,
    _FEE_BEARING_BASE_FORMS,
    _is_registration_form,
    _resolve_fee_source,
    _data_to_fee_table,
    _extract_inline_fee_table,
    extract_registration_fee_table,
)

__all__ = ['extract_registration_fee_table']
