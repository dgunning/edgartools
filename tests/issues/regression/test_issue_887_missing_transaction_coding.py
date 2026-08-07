"""
Regression test for GitHub Issue #887:
Form 4 obj()/to_dataframe() raised
`AttributeError: 'DataFrame' object has no attribute 'Code'` for filings whose
transactions have no <transactionCoding> element.

Root cause: the Code/form/EquitySwap columns are only populated for transactions
that carry <transactionCoding>. When *no* transaction in a table has coding, the
DataFrame lacked the 'Code' column and the downstream
`df.Code.apply(...)` aborted the parse of the entire filing.

Fix: _ensure_coding_columns() guarantees those columns exist (default None) in
both NonDerivativeTable.extract_transactions and
DerivativeTable.extract_transactions, so uncoded rows degrade to
TransactionType=None instead of crashing.
"""
import pytest
from bs4 import BeautifulSoup

from edgar.ownership.table_containers import DerivativeTable, NonDerivativeTable


def _table(xml: str):
    return BeautifulSoup(xml, "xml").find(True)  # first (root) tag


# --- Offline: non-derivative table with NO transactionCoding (the crash case) ---

_NONDERIV_NO_CODING = """
<nonDerivativeTable>
  <nonDerivativeTransaction>
    <securityTitle><value>Common Stock</value></securityTitle>
    <transactionDate><value>2026-01-05</value></transactionDate>
    <transactionAmounts>
      <transactionShares><value>56332</value></transactionShares>
      <transactionPricePerShare><value>3.88</value></transactionPricePerShare>
      <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
    </transactionAmounts>
    <postTransactionAmounts>
      <sharesOwnedFollowingTransaction><value>0</value></sharesOwnedFollowingTransaction>
    </postTransactionAmounts>
    <ownershipNature>
      <directOrIndirectOwnership><value>D</value></directOrIndirectOwnership>
    </ownershipNature>
  </nonDerivativeTransaction>
</nonDerivativeTable>
"""

# Same shape but WITH coding, to prove no regression.
_NONDERIV_WITH_CODING = _NONDERIV_NO_CODING.replace(
    "</transactionAmounts>",
    "</transactionAmounts>\n    <transactionCoding>"
    "<transactionCode>S</transactionCode><equitySwapInvolved>0</equitySwapInvolved>"
    "</transactionCoding>",
)


def test_nonderivative_without_coding_does_not_crash():
    txns = NonDerivativeTable.extract_transactions(_table(_NONDERIV_NO_CODING))
    df = txns.data
    assert len(df) == 1
    row = df.iloc[0]
    assert int(row["Shares"]) == 56332
    assert float(row["Price"]) == 3.88
    assert row["AcquiredDisposed"] == "D"
    # Missing coding degrades gracefully.
    assert row["Code"] is None
    assert row["TransactionType"] is None


def test_nonderivative_with_coding_still_resolves_transaction_type():
    txns = NonDerivativeTable.extract_transactions(_table(_NONDERIV_WITH_CODING))
    row = txns.data.iloc[0]
    assert row["Code"] == "S"
    # 'S' resolves to a human-readable transaction type (not left as the raw code).
    assert row["TransactionType"] not in (None, "S")


# --- Offline: derivative table with NO transactionCoding (same latent bug) ---

_DERIV_NO_CODING = """
<derivativeTable>
  <derivativeTransaction>
    <securityTitle><value>Stock Option</value></securityTitle>
    <transactionDate><value>2026-01-05</value></transactionDate>
    <transactionAmounts>
      <transactionShares><value>1000</value></transactionShares>
      <transactionPricePerShare><value>0</value></transactionPricePerShare>
      <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
    </transactionAmounts>
    <underlyingSecurity>
      <underlyingSecurityShares><value>1000</value></underlyingSecurityShares>
    </underlyingSecurity>
    <postTransactionAmounts>
      <sharesOwnedFollowingTransaction><value>1000</value></sharesOwnedFollowingTransaction>
    </postTransactionAmounts>
    <ownershipNature>
      <directOrIndirectOwnership><value>D</value></directOrIndirectOwnership>
    </ownershipNature>
  </derivativeTransaction>
</derivativeTable>
"""


def test_derivative_without_coding_does_not_crash():
    txns = DerivativeTable.extract_transactions(_table(_DERIV_NO_CODING))
    df = txns.data
    assert len(df) == 1
    assert df.iloc[0]["Code"] is None
    assert df.iloc[0]["TransactionType"] is None


# --- Network: ground truth on the reporter's accessions ---

@pytest.mark.network
@pytest.mark.regression
@pytest.mark.parametrize("accession,rows", [
    ("0001133416-26-000010", 1),
    ("0000897069-26-001304", 1),
    ("0000912282-25-001299", 2),
])
def test_reported_form4_filings_parse(accession, rows):
    from edgar import find

    obj = find(accession).obj()
    df = obj.to_dataframe()
    assert len(df) == rows
