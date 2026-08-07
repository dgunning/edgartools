"""Regression test for edgartools-xvxp.

Cross-repo bug check: the TypeScript sibling (edgartools-workers,
src/lib/ownership-extract.ts) had a regex-based extractor that required
``</value>`` to butt against the field's closing tag. SEC Form 4 XML frequently
nests a ``<footnoteId>`` sibling *after* ``<value>`` inside numeric fields::

    <transactionShares><value>1800</value><footnoteId id="F1"/></transactionShares>

The trailing ``<footnoteId>`` made the TS regex match fail and the value
silently parsed as 0, corrupting net shares / net value / % position.

The Python parser reads these fields via ``child_text`` -> ``el.text.strip()``
(a real DOM walk, not a regex), so the empty ``<footnoteId/>`` contributes no
text and the number survives. These tests lock that behaviour in.

Real repro filing: GLOBALFOUNDRIES Inc. (GFS), accession 0001709048-26-000087,
reporting owner Michael James Hogan -- a Sale of 1800 shares @ $48.31 and a Gift
of 150 shares, both with a ``<footnoteId>`` sibling on ``<transactionShares>``.
"""
import pytest

from edgar.ownership import Ownership


# Minimal, self-contained Form 4 mirroring the GFS filing's footnote shape:
# a <footnoteId> sibling sits AFTER <value> on transactionShares (the field the
# TS bug zeroed), on transactionPricePerShare, and on
# sharesOwnedFollowingTransaction.
GFS_SHAPE_FORM4 = """<?xml version="1.0"?>
<ownershipDocument>
    <documentType>4</documentType>
    <issuer>
        <issuerCik>0001709048</issuerCik>
        <issuerName>GLOBALFOUNDRIES Inc.</issuerName>
        <issuerTradingSymbol>GFS</issuerTradingSymbol>
    </issuer>
    <reportingOwner>
        <reportingOwnerId>
            <rptOwnerCik>0002120107</rptOwnerCik>
            <rptOwnerName>Hogan Michael James</rptOwnerName>
        </reportingOwnerId>
        <reportingOwnerAddress>
            <rptOwnerStreet1>400 Stone Break Road Extension</rptOwnerStreet1>
            <rptOwnerStreet2></rptOwnerStreet2>
            <rptOwnerCity>Malta</rptOwnerCity>
            <rptOwnerState>NY</rptOwnerState>
            <rptOwnerZipCode>12020</rptOwnerZipCode>
        </reportingOwnerAddress>
        <reportingOwnerRelationship>
            <isDirector>0</isDirector>
            <isOfficer>1</isOfficer>
            <officerTitle>Chief Business Officer</officerTitle>
        </reportingOwnerRelationship>
    </reportingOwner>
    <nonDerivativeTable>
        <nonDerivativeTransaction>
            <securityTitle><value>Ordinary Shares</value></securityTitle>
            <transactionDate><value>2026-06-13</value></transactionDate>
            <transactionCoding>
                <transactionFormType>4</transactionFormType>
                <transactionCode>S</transactionCode>
                <equitySwapInvolved>0</equitySwapInvolved>
            </transactionCoding>
            <transactionAmounts>
                <transactionShares><value>1800</value><footnoteId id="F1"/></transactionShares>
                <transactionPricePerShare><value>48.31</value><footnoteId id="F1"/></transactionPricePerShare>
                <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
            </transactionAmounts>
            <postTransactionAmounts>
                <sharesOwnedFollowingTransaction><value>18995</value><footnoteId id="F1"/></sharesOwnedFollowingTransaction>
            </postTransactionAmounts>
            <ownershipNature>
                <directOrIndirectOwnership><value>D</value></directOrIndirectOwnership>
            </ownershipNature>
        </nonDerivativeTransaction>
        <nonDerivativeTransaction>
            <securityTitle><value>Ordinary Shares</value></securityTitle>
            <transactionDate><value>2026-06-13</value></transactionDate>
            <transactionCoding>
                <transactionFormType>4</transactionFormType>
                <transactionCode>G</transactionCode>
                <equitySwapInvolved>0</equitySwapInvolved>
            </transactionCoding>
            <transactionAmounts>
                <transactionShares><value>150</value><footnoteId id="F1"/></transactionShares>
                <transactionPricePerShare><value>0</value></transactionPricePerShare>
                <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
            </transactionAmounts>
            <postTransactionAmounts>
                <sharesOwnedFollowingTransaction><value>18845</value><footnoteId id="F1"/></sharesOwnedFollowingTransaction>
            </postTransactionAmounts>
            <ownershipNature>
                <directOrIndirectOwnership><value>D</value></directOrIndirectOwnership>
            </ownershipNature>
        </nonDerivativeTransaction>
    </nonDerivativeTable>
</ownershipDocument>
"""


@pytest.fixture(scope="module")
def gfs_shape_ownership():
    return Ownership.from_xml(GFS_SHAPE_FORM4)


def test_footnoted_transaction_shares_not_zeroed(gfs_shape_ownership):
    """transactionShares with a trailing <footnoteId> must keep their value."""
    data = gfs_shape_ownership.non_derivative_table.transactions.data

    # Two transactions, in document order.
    assert len(data) == 2

    sale = data.iloc[0]
    gift = data.iloc[1]

    assert sale["Code"] == "S"
    assert sale["Shares"] == 1800        # NOT 0
    assert sale["Price"] == 48.31        # NOT 0
    assert sale["Remaining"] == 18995    # NOT 0

    assert gift["Code"] == "G"
    assert gift["Shares"] == 150          # NOT 0
    assert gift["Remaining"] == 18845


def test_no_footnoted_numeric_field_silently_zeroed_or_none(gfs_shape_ownership):
    """Sweep: no footnoted numeric field collapses to 0/None.

    Every numeric field in this fixture carries a <footnoteId> sibling except
    the gift's price (legitimately 0). Assert none of the share counts are
    silently zeroed/None.
    """
    data = gfs_shape_ownership.non_derivative_table.transactions.data

    for col in ("Shares", "Remaining"):
        values = data[col].tolist()
        assert all(v is not None for v in values), f"{col} has a None: {values}"
        assert all(v > 0 for v in values), f"{col} was silently zeroed: {values}"

    # The sale's price is footnoted and must survive; the gift's price is a
    # genuine 0 (no consideration) and is allowed to be 0.
    assert data.iloc[0]["Price"] == 48.31


@pytest.mark.network
def test_real_gfs_filing_footnoted_shares():
    """End-to-end check against the real GFS Form 4 (network)."""
    from edgar import find

    filing = find("0001709048-26-000087")
    ownership = filing.obj()
    data = ownership.non_derivative_table.transactions.data

    by_code = {row["Code"]: row for _, row in data.iterrows()}

    assert by_code["S"]["Shares"] == 1800
    assert by_code["S"]["Price"] == 48.31
    assert by_code["S"]["Remaining"] == 18995

    assert by_code["G"]["Shares"] == 150
    assert by_code["G"]["Remaining"] == 18845
