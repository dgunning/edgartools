"""
Insider ownership forms: Forms 3, 4 and 5 (Section 16), plus Form 144.

Section 16 of the Exchange Act makes officers, directors and 10%-or-more holders
report their own holdings and trades in the company: Form 3 when they become an
insider, Form 4 within two business days of a trade, Form 5 annually for what
Form 4 did not cover. Form 144 (``edgar.ownership.form144``) is the notice of a
proposed sale of restricted or control securities, often filed by the same people.

Which package holds the form you have:

    Forms 3, 4, 5 and 144        edgar.ownership             (this package)
    Schedule 13D / 13G           edgar.beneficial_ownership  Section 13(d)/(g): anyone over 5%
    13F-HR                       edgar.thirteenf             Section 13(f): institutional managers

Forms 3/4/5 report beneficial ownership too, so the package names do not tell
the regimes apart; the statute does. Every one of these classes is also
importable from the top level, e.g. ``from edgar import Form4, Schedule13D``.

Example usage:
    from edgar import Company

    form4 = Company("NVDA").get_filings(form="4").latest().obj()
    print(form4.get_ownership_summary())
"""
from edgar._party import Address
from edgar.ownership.core import translate_ownership
from edgar.ownership.forms import Form3, Form4, Form5, Ownership
from edgar.ownership.html_render import ownership_to_html
from edgar.ownership.models import (
    Footnotes,
    Issuer,
    OwnerSignature,
    PostTransactionAmounts,
    ReportingRelationship,
    TransactionCode,
)
from edgar.ownership.owners import Owner, ReportingOwners
from edgar.ownership.summary import TransactionSummary
from edgar.ownership.tables import (
    DerivativeHolding,
    DerivativeHoldings,
    DerivativeTransaction,
    DerivativeTransactions,
    NonDerivativeHolding,
    NonDerivativeHoldings,
    NonDerivativeTransaction,
    NonDerivativeTransactions,
)
