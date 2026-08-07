"""
Backward-compatibility shim for the former ``ownershipforms`` god-module.

The domain model for Forms 3, 4 and 5 now lives in focused submodules:

- ``edgar.ownership.models``  — leaf value objects (Issuer, TransactionCode, ...)
- ``edgar.ownership.tables``  — holdings/transactions tables
- ``edgar.ownership.owners``  — Owner / ReportingOwners
- ``edgar.ownership.summary`` — OwnershipSummary hierarchy
- ``edgar.ownership.forms``   — Ownership / Form3 / Form4 / Form5
- ``edgar.ownership.core``    — formatting + translation helpers
- ``edgar.ownership.text_render`` / ``html_render`` — rendering

This module re-exports every previously public name so that existing imports
like ``from edgar.ownership.ownershipforms import Form4`` keep working. Prefer
importing from the ``edgar.ownership`` package or the submodules above.
"""
from edgar._party import Address
from edgar.ownership.core import (
    BUY_SELL,
    DIRECT_OR_INDIRECT_OWNERSHIP,
    FORM_DESCRIPTIONS,
    describe_ownership,
    detect_10b5_1_plan,
    format_amount,
    format_currency,
    format_numeric,
    get_footnotes,
    safe_numeric,
    transaction_footnote_id,
    translate,
    translate_buy_sell,
    translate_ownership,
    translate_transaction_types,
)
from edgar.ownership.forms import Form3, Form4, Form5, Ownership
from edgar.ownership.html_render import ownership_to_html
from edgar.ownership.models import (
    Footnotes,
    Issuer,
    OwnerSignature,
    OwnerSignatures,
    PostTransactionAmounts,
    ReportingRelationship,
    TransactionCode,
    Underyling,
)
from edgar.ownership.owners import Owner, ReportingOwners
from edgar.ownership.summary import (
    InitialOwnershipSummary,
    OwnershipSummary,
    TransactionSummary,
)
from edgar.ownership.summary_records import SecurityHolding, TransactionActivity
from edgar.ownership.table_containers import DerivativeTable, NonDerivativeTable
from edgar.ownership.tables import (
    DataHolder,
    DerivativeHolding,
    DerivativeHoldings,
    DerivativeTransaction,
    DerivativeTransactions,
    NonDerivativeHolding,
    NonDerivativeHoldings,
    NonDerivativeTransaction,
    NonDerivativeTransactions,
)

__all__ = [
    'Owner',
    'Issuer',
    'Address',
    'Footnotes',
    'OwnerSignature',
    'TransactionCode',
    'Ownership',
    'Form3',
    'Form4',
    'Form5',
    'DerivativeHolding',
    'DerivativeHoldings',
    'translate_ownership',
    'NonDerivativeHolding',
    'NonDerivativeHoldings',
    'DerivativeTransaction',
    'DerivativeTransactions',
    'ReportingOwners',
    'ReportingRelationship',
    'PostTransactionAmounts',
    'NonDerivativeTransaction',
    'NonDerivativeTransactions',
    'TransactionActivity',
    'TransactionSummary',
    'OwnershipSummary',
]
