"""
Guard the public import surface of the edgar.ownership package.

The ownership domain model was split out of the former 2,279-line
``ownershipforms.py`` god-module into focused submodules (models, tables,
owners, summary, forms, core, text_render). This test pins the public names so
that the structural refactor — and any future one — cannot silently drop or
rename a name that users import. See beads edgartools-40p8.
"""
import pytest

import edgar.ownership as ownership
import edgar.ownership.ownershipforms as ownershipforms

# Pure import-surface checks — no network. Mark explicitly so the conftest
# auto-marker (which would tag any 'test_ownership*' file as network) is skipped.
pytestmark = pytest.mark.fast

# Names that must remain importable from the `edgar.ownership` package.
EXPECTED_PACKAGE_NAMES = {
    'Address',
    'DerivativeHolding',
    'DerivativeHoldings',
    'DerivativeTransaction',
    'DerivativeTransactions',
    'Footnotes',
    'Form3',
    'Form4',
    'Form5',
    'Issuer',
    'NonDerivativeHolding',
    'NonDerivativeHoldings',
    'NonDerivativeTransaction',
    'NonDerivativeTransactions',
    'Owner',
    'Ownership',
    'OwnerSignature',
    'PostTransactionAmounts',
    'ReportingOwners',
    'ReportingRelationship',
    'TransactionCode',
    'TransactionSummary',
    'translate_ownership',
    'ownership_to_html',
}

# Names that must remain importable from the legacy `ownershipforms` shim
# (a superset of the package surface — preserves `from
# edgar.ownership.ownershipforms import X` for everything that module exposed).
EXPECTED_SHIM_NAMES = EXPECTED_PACKAGE_NAMES | {
    'DataHolder',
    'DerivativeTable',
    'InitialOwnershipSummary',
    'NonDerivativeTable',
    'OwnerSignatures',
    'OwnershipSummary',
    'SecurityHolding',
    'TransactionActivity',
    'Underyling',  # intentional historical spelling — part of the public surface
    'describe_ownership',
    'detect_10b5_1_plan',
    'format_amount',
    'format_currency',
    'format_numeric',
    'get_footnotes',
    'safe_numeric',
    'transaction_footnote_id',
    'translate',
    'translate_buy_sell',
    'translate_transaction_types',
    'BUY_SELL',
    'DIRECT_OR_INDIRECT_OWNERSHIP',
    'FORM_DESCRIPTIONS',
}


def test_ownership_package_surface_is_stable():
    missing = {n for n in EXPECTED_PACKAGE_NAMES if not hasattr(ownership, n)}
    assert not missing, f"edgar.ownership lost public names: {sorted(missing)}"


def test_ownershipforms_shim_surface_is_stable():
    missing = {n for n in EXPECTED_SHIM_NAMES if not hasattr(ownershipforms, n)}
    assert not missing, f"ownershipforms shim lost backward-compat names: {sorted(missing)}"


def test_class_identity_is_consistent_across_import_paths():
    # The same class object must be reachable from the package, the canonical
    # submodule, and the legacy shim — no accidental duplicate definitions.
    from edgar.ownership.forms import Form4 as canonical_form4
    from edgar.ownership.models import Issuer as canonical_issuer

    assert ownership.Form4 is canonical_form4 is ownershipforms.Form4
    assert ownership.Issuer is canonical_issuer is ownershipforms.Issuer


def test_split_modules_share_one_class_object():
    # The table containers and summary records were split into their own
    # modules; the legacy shim (and the summary re-export) must expose the same
    # object, not a copy.
    from edgar.ownership.summary import SecurityHolding as summary_holding
    from edgar.ownership.summary import TransactionActivity as summary_activity
    from edgar.ownership.summary_records import SecurityHolding, TransactionActivity
    from edgar.ownership.table_containers import DerivativeTable, NonDerivativeTable

    assert SecurityHolding is summary_holding is ownershipforms.SecurityHolding
    assert TransactionActivity is summary_activity is ownershipforms.TransactionActivity
    assert NonDerivativeTable is ownershipforms.NonDerivativeTable
    assert DerivativeTable is ownershipforms.DerivativeTable
