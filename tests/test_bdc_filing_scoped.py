"""
Tests for filing-scoped BDC portfolio investment extraction.

Covers `portfolio_investments_from_filing()` and the `filing=` parameter on
`BDCEntity.portfolio_investments()` / `BDCEntity.schedule_of_investments()`,
which let a caller pull holdings from an explicitly chosen filing instead of
always getting the BDC's latest one. This is the library entry point Phase 1
of the Private Credit Evidence Access design uses so the MCP can return
holdings for a filing the caller selected (by accession number or period),
not always the latest 10-K.
"""
from decimal import Decimal

import pytest

from edgar import find, set_identity
from edgar.bdc import BDCEntity, PortfolioInvestments, portfolio_investments_from_filing

# Ground truth measured 2026-09-28 (see global constraints doc, rule 7):
# ARCC (CIK 1287750) 10-Q accession 0001628280-26-050307, period_of_report
# 2026-06-30, 1,481 holdings via facts-based extraction.
ARCC_CIK = 1287750
ARCC_10Q_ACCESSION = "0001628280-26-050307"
ARCC_10Q_PERIOD = "2026-06-30"
ARCC_10Q_HOLDING_COUNT = 1481


@pytest.mark.network
def test_portfolio_investments_from_filing_ground_truth():
    """portfolio_investments_from_filing() on an explicitly chosen ARCC 10-Q.

    Runs LIVE, not against a VCR cassette (rule 7a of the constraints doc):
    the ARCC 10-Q's full submission is ~88 MB, so a recorded cassette for it
    would be an oversized commit. Ground truth values (count, period,
    extraction method, and the hand-checked holding below) were verified
    against the live extraction before being written here; see the task
    report for how.
    """
    set_identity("Test User test@test.com")
    filing = find(ARCC_10Q_ACCESSION)
    assert filing.cik == ARCC_CIK

    investments = portfolio_investments_from_filing(filing)

    assert investments is not None
    assert len(investments) == ARCC_10Q_HOLDING_COUNT
    assert investments.period == ARCC_10Q_PERIOD
    assert investments.extraction_method == "xbrl_facts"

    holdings = [
        inv for inv in investments
        if inv.identifier == "Ivy Hill Asset Management, L.P. | Subordinated revolving loan"
    ]
    assert len(holdings) == 1
    holding = holdings[0]
    assert holding.fair_value == Decimal("946000000")
    assert holding.interest_rate == 0.1023
    assert holding.spread == 0.065
    assert holding.principal_amount == Decimal("946000000")


@pytest.mark.network
def test_bdc_entity_portfolio_investments_with_explicit_filing():
    """BDCEntity.portfolio_investments(filing=...) uses the given filing.

    Runs LIVE (see rule 7a; same ARCC oversized-submission reasoning as
    above). Passing the same ARCC 10-Q by accession number (rather than
    letting BDCEntity look up the latest filing) must return the same
    holding count as the module-level function above.
    """
    set_identity("Test User test@test.com")
    filing = find(ARCC_10Q_ACCESSION)
    arcc = BDCEntity(file_number="814-00663", cik=ARCC_CIK, name="ARES CAPITAL CORP")

    investments = arcc.portfolio_investments(filing=filing)

    assert investments is not None
    assert len(investments) == ARCC_10Q_HOLDING_COUNT


# Small-BDC deterministic VCR fixture (rule 7a). Chosen 2026-09-28 by probing
# candidates' EDGAR filing-index total submission size (via each accession's
# index.json, which lists per-document byte sizes — never by iterating filing
# histories reading period_of_report) and checking which had XBRL
# investment-level dimensional detail. `filing.xbrl()` fetches the full SGML
# submission .txt (confirmed by inspecting a recorded cassette's single large
# interaction), so cassette size tracks total submission size, not just the
# instance document.
#
# Candidates probed, index.json total bytes, and outcome:
#   Equus Total Return 10-Q (CIK 878932, 0001712543-26-000047): ~0.9 MB total,
#     but 0 XBRL facts carry the investment-identifier dimension —
#     portfolio_investments_from_filing() returns None. Rejected.
#   Rand Capital Corp 10-Q (CIK 81955, 0001193125-26-333983): ~19.4 MB total,
#     89 holdings via facts. Recorded cassette measured 21.7 MB — over the
#     10 MB cap. Rejected (cassette deleted, never committed).
#   Princeton Capital Corp 10-Q (CIK 845385, 0001213900-26-090000): ~8.4 MB
#     total, 23 holdings via facts, cassette measured under 10 MB (see task
#     report for the exact number). Selected — reused by Tasks 4-6 as the
#     small-BDC fixture.
PRINCETON_CIK = 845385
PRINCETON_10Q_ACCESSION = "0001213900-26-090000"
PRINCETON_10Q_PERIOD = "2026-06-30"
PRINCETON_10Q_HOLDING_COUNT = 23


@pytest.mark.network
@pytest.mark.vcr
def test_portfolio_investments_from_filing_small_bdc_ground_truth():
    """Deterministic small-BDC ground truth (rule 7a): Princeton Capital's 2026-06-30 10-Q.

    Cassette recorded once and replayed on subsequent runs (see task report
    for its measured size, confirmed under the 10 MB cap). Ground truth
    values were verified against the live extraction before being written
    here (same method as the ARCC holding above): a probe script printed the
    parsed PortfolioInvestments and its fields, and the values below are
    copied from that output.
    """
    set_identity("Test User test@test.com")
    filing = find(PRINCETON_10Q_ACCESSION)
    assert filing.cik == PRINCETON_CIK

    investments = portfolio_investments_from_filing(filing)

    assert investments is not None
    assert len(investments) == PRINCETON_10Q_HOLDING_COUNT
    assert investments.period == PRINCETON_10Q_PERIOD
    assert investments.extraction_method == "xbrl_facts"

    holdings = [
        inv for inv in investments
        if inv.identifier == "Control Investments - Rockfish Seafood Grill, Inc. - Revolving Loan"
    ]
    assert len(holdings) == 1
    holding = holdings[0]
    assert holding.is_debt
    assert holding.fair_value == Decimal("2433581")
    assert holding.principal_amount == Decimal("2251000")
    assert holding.interest_rate == 0.08


@pytest.mark.fast
def test_portfolio_investments_empty_construction_has_no_extraction_method():
    """A directly-constructed PortfolioInvestments has extraction_method None."""
    investments = PortfolioInvestments([])
    assert len(investments) == 0
    assert investments.extraction_method is None


@pytest.mark.fast
def test_bdc_entity_portfolio_investments_rejects_mismatched_filing_cik():
    """Passing a filing for a different CIK raises ValueError naming both CIKs."""

    class _FakeFiling:
        cik = 9999999

    arcc = BDCEntity(file_number="814-00663", cik=ARCC_CIK, name="ARES CAPITAL CORP")

    with pytest.raises(ValueError) as exc_info:
        arcc.portfolio_investments(filing=_FakeFiling())

    message = str(exc_info.value)
    assert str(ARCC_CIK) in message
    assert str(_FakeFiling.cik) in message
