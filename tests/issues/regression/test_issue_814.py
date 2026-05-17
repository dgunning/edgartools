"""
Regression test for GitHub Issue #814:
Financials.get_net_income() returned a wrong positive value for Micron Technology's
Q2 2013 10-Q (period 2013-02-28) instead of the actual net loss.

Root cause was twofold:
1. _get_standardized_concept_by_xbrl used a substring match on concept names,
   so 'NetIncome' substring-matched the row tagged
   us-gaap:NetIncomeLossAttributableToNoncontrollingInterest ($2M for MU)
   before reaching us-gaap:NetIncomeLoss (-$286M).
2. get_net_income() used only label-regex patterns ('^Net Income') that
   never matched filer-labeled-as-loss rows ('Net loss attributable to ...')
   and would also fall through to the noncontrolling-interest row.

Fix:
- Helper now does exact (case-insensitive) local-name match on concepts.
- get_net_income() runs concept-based lookup first via the helper,
  then falls back to label patterns expanded to handle 'Net Loss' variants
  with explicit noncontrolling-interest exclusion.

The MU 10-Q (accession 0000723125-13-000042) is a structural canary —
it has BOTH a net loss row AND a separate NCI row, exercising the full
failure mode.
"""
import pytest
from edgar import Company


@pytest.mark.network
@pytest.mark.regression
def test_mu_q2_2013_net_income_returns_correct_loss():
    """MU Q2 2013 net income should be -$286M, not +$2M (the NCI row)."""
    filing = (
        Company('MU')
        .get_filings(form='10-Q', amendments=False)
        .filter(accession_number='0000723125-13-000042')[0]
    )

    fin = filing.obj().financials
    revenue = fin.get_revenue()
    net_income = fin.get_net_income()

    assert revenue == 2_078_000_000.0, (
        f"MU Q2 2013 revenue: expected 2,078,000,000, got {revenue}"
    )
    assert net_income == -286_000_000.0, (
        f"MU Q2 2013 net income: expected -286,000,000 "
        f"(us-gaap:NetIncomeLoss attributable to Micron), got {net_income}. "
        f"A value of +2,000,000 indicates the bug has regressed — that's the "
        f"NetIncomeLossAttributableToNoncontrollingInterest row."
    )


@pytest.mark.network
@pytest.mark.regression
def test_helper_exact_concept_match_prefers_netincomeloss_over_nci():
    """_get_standardized_concept_by_xbrl must exact-match concept names.

    Substring matching would pick NetIncomeLossAttributableToNoncontrollingInterest
    when searching for 'NetIncome'. With exact match, only us-gaap_NetIncomeLoss
    matches the 'Net Income' standardized mapping for MU's filing.
    """
    filing = (
        Company('MU')
        .get_filings(form='10-Q', amendments=False)
        .filter(accession_number='0000723125-13-000042')[0]
    )
    fin = filing.obj().financials

    # Direct helper call — should hit the canonical NetIncomeLoss row
    value = fin._get_standardized_concept_by_xbrl('income', ['Net Income'], 0)
    assert value == -286_000_000.0, (
        f"Helper expected -286M (us-gaap:NetIncomeLoss), got {value}. "
        f"+2M means substring-match regression to NCI row."
    )


@pytest.mark.network
@pytest.mark.regression
def test_ifrs_filer_resolves_via_profit_or_loss_concept():
    """get_net_income() must resolve for IFRS 20-F filers via ifrs-full_ProfitLoss.

    Barclays FY2023 20-F is the canary: the canonical net-income row is tagged
    ifrs-full_ProfitLoss and labeled 'Profit after tax' — no label pattern from
    the US-centric fallback list would match. Resolution depends on:
      (a) ifrs-full_ProfitLoss being present in the 'Profit or Loss' concept
          mapping (concept_mappings.json),
      (b) the helper stripping the 'ifrs-full_' namespace prefix in _strip_ns,
      (c) get_net_income() falling through from 'Net Income' to 'Profit or Loss'.

    Without (a)-(c), this filing returns None (regression).
    """
    filing = (
        Company('BCS')
        .get_filings(form='20-F', amendments=False)
        .filter(accession_number='0000312069-24-000026')[0]
    )
    net_income = filing.obj().financials.get_net_income()
    assert net_income == 5_323_000_000.0, (
        f"BCS FY2023 20-F net income: expected 5,323,000,000 (ifrs-full:ProfitLoss "
        f"'Profit after tax' row), got {net_income}. None means the IFRS concept "
        f"mapping or namespace strip has regressed."
    )


@pytest.mark.network
@pytest.mark.regression
def test_concept_iteration_is_deterministic():
    """Helper must iterate the mapped concept set in a deterministic order.

    The standardizer stores mappings as a set, so without explicit sorting the
    iteration order is hash-randomized. For filers (e.g. BCS) whose statement
    contains multiple concepts mapped to the same standardized name, this would
    cause get_net_income() to return different values across runs.
    """
    filing = (
        Company('BCS')
        .get_filings(form='20-F', amendments=False)
        .filter(accession_number='0000312069-24-000026')[0]
    )
    fin = filing.obj().financials
    results = {fin.get_net_income() for _ in range(3)}
    assert len(results) == 1, (
        f"Non-deterministic get_net_income() — got {results} across 3 calls. "
        f"xbrl_concepts iteration order in _get_standardized_concept_by_xbrl "
        f"is not sorted."
    )
