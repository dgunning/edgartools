"""
Regression tests for edgartools-y4yp: three `Financials` scalar getters that
returned the wrong row, or no row, because they identified a line by matching
loose patterns and taking the first hit.

GH #1279 -- `get_total_liabilities()` passed r'Liabilities$' to a helper that
runs `df['label'].str.contains(...)` and returns the first numeric match. That
pattern matches "TOTAL LIABILITIES AND SHAREHOLDERS' EQUITY", which is what a
balance sheet carries when it reports no standalone `us-gaap:Liabilities`
total. NIKE's FY2026 10-K returned $38,410,000,000 -- its TOTAL ASSETS -- as
its liabilities, so `get_financial_metrics()['debt_to_assets']` came back as
exactly 1.0 against an actual 0.613. The getter now identifies the concept and
returns None when the filing reports no total, because a misleading finite
number is worse than an absent one.

GH #1294 -- `get_revenue()` asked for 'Contract Revenue' BEFORE 'Revenue'. A
contract-revenue fact can be one COMPONENT of `us-gaap:Revenues` rather than
the top line: Cato files both in one face statement, and its calculation
linkbase defines Revenues = RevenueFromContractWithCustomerIncludingAssessedTax
+ IncomeOther. `Statement.REVENUE_CONCEPTS` already ordered these the right way
round, so the same object's `get_revenue()` and `analyze_trends()` disagreed.

GH #1291 -- `get_shares_outstanding_basic()` went through `_get_concept_value`,
the one helper of the three that neither dropped abstract rows nor looked past
`matches.iloc[0]`. An abstract heading sorts above the row it introduces and
never carries a value, so Auburn National's populated share row was shadowed
and the getter returned None for a figure sitting in the rendered statement.

THE COMMON SHAPE, and why the fixes differ. All three helpers exist to answer
"what is this line's value", and they had drifted into three different answers
about how to find a row. `_get_concept_value` is now aligned with its two
siblings rather than special-cased for shares.

MEASURED. Across the fixture corpus these changes move exactly four values, all
of them `total_liabilities`, and every one was previously EQUAL TO TOTAL ASSETS
-- the bug was already reproducing inside our own corpus, in Coca-Cola's 10-K
across three fixtures and Amazon's, and no test caught it because none asserted
the value. Revenue changes nowhere: no fixture resolves both revenue concepts
to different values, and the seven filings that resolve only the contract
concept (Apple, Microsoft, Amazon, Tesla) fall through as before.
"""

from decimal import Decimal
from pathlib import Path

import pytest

from edgar.financials import Financials
from edgar.xbrl import XBRL

NKE = Path("tests/fixtures/xbrl/nke/10k_2026")
CATO = Path("tests/fixtures/xbrl/cato/10k_2023")
AUBN = Path("tests/fixtures/xbrl/aubn/10k_2023")
KO = Path("tests/fixtures/xbrl/ko/10k_2024")


def _financials(directory):
    return Financials(XBRL.from_directory(directory))


@pytest.fixture(scope="module")
def nke():
    return _financials(NKE)


@pytest.fixture(scope="module")
def cato():
    return _financials(CATO)


@pytest.fixture(scope="module")
def aubn():
    return _financials(AUBN)


@pytest.fixture(scope="module")
def ko():
    return _financials(KO)


def filed_value(financials, local_name, period_key):
    """Read one dimensionless filed fact straight out of the instance."""
    rows = (financials.xb.facts.query()
            .by_concept(f"us-gaap:{local_name}", exact=True)
            .by_period_key(period_key)
            # Filers spell the unit id either way ('usd', 'USD'); the measure
            # is what matters and both resolve to iso4217:USD.
            .by_custom(lambda f: not f["is_dimensioned"]
                       and (f["unit_ref"] or "").lower() == "usd")
            .execute())
    values = {Decimal(f["value"]) for f in rows}
    assert len(values) == 1, f"{local_name}: expected one filed value, got {values}"
    return values.pop()


# --------------------------------------------------------------------------
# GH #1279 -- total liabilities
# --------------------------------------------------------------------------

def test_nke_does_not_report_assets_as_liabilities(nke):
    """The reported defect: liabilities == assets, and a 100% debt ratio."""
    assets = nke.get_total_assets()
    assert assets == 38410000000.0

    liabilities = nke.get_total_liabilities()
    assert liabilities != assets, "returned liabilities-and-equity as liabilities"
    # NIKE files no standalone us-gaap:Liabilities total, so there is nothing
    # to report. None is the correct answer; a derived total is tracked
    # separately (bead edgartools-y4yp.5) because it needs a noncontrolling
    # interest rule to be right in general.
    assert liabilities is None

    metrics = nke.get_financial_metrics()
    assert metrics["debt_to_assets"] != 1.0
    assert metrics["debt_to_assets"] is None


def test_nke_filed_components_show_what_the_real_total_is(nke):
    """Ground truth from the instance, independent of any getter.

    This is what the getter must not contradict: the liabilities NIKE actually
    reports sum to $23.545B, so a 100% ratio was never plausible.
    """
    period = "instant_2026-05-31"
    components = sum(filed_value(nke, name, period) for name in [
        "LiabilitiesCurrent",
        "LongTermDebtNoncurrent",
        "OperatingLeaseLiabilityNoncurrent",
        "DeferredIncomeTaxesAndOtherLiabilitiesNoncurrent",
    ])
    assert components == Decimal("23545000000")

    assets = filed_value(nke, "Assets", period)
    equity = filed_value(nke, "StockholdersEquity", period)
    assert assets - equity == components
    # The value the getter used to return was the combined caption.
    assert filed_value(nke, "LiabilitiesAndStockholdersEquity", period) == assets
    assert components / assets < Decimal("0.62")


@pytest.mark.parametrize("directory", [
    KO,
    Path("tests/fixtures/xbrl/ko/10k_2012"),
    Path("tests/fixtures/xbrl/special_cases/dimensional/ko"),
    Path("tests/fixtures/xbrl/special_cases/segments/amzn"),
])
def test_corpus_filings_no_longer_report_assets_as_liabilities(directory):
    """The four fixture filings that carried this bug all along."""
    financials = _financials(directory)
    assets = financials.get_total_assets()
    liabilities = financials.get_total_liabilities()
    assert assets is not None
    assert liabilities != assets


def test_aubn_still_returns_a_filed_liabilities_total(aubn):
    """Positive control: a filing that DOES report the total still gets it.

    Returning None everywhere would satisfy the tests above and be useless, so
    this pins the other direction.
    """
    liabilities = aubn.get_total_liabilities()
    assert liabilities == 898748000.0
    assert liabilities != aubn.get_total_assets()
    assert 0.0 < aubn.get_financial_metrics()["debt_to_assets"] < 1.0


# --------------------------------------------------------------------------
# GH #1294 -- revenue
# --------------------------------------------------------------------------

def test_cato_revenue_is_the_filed_total_not_the_component(cato):
    """Total revenues, not the retail-sales line that rolls up into it."""
    assert [cato.get_revenue(i) for i in range(3)] == [
        708059000.0, 759260000.0, 761358000.0 + 7913000.0,
    ]
    assert cato.get_financial_metrics()["revenue"] == 708059000.0


def test_cato_revenue_agrees_with_the_statement_helpers(cato):
    """The same object disagreed with itself; it must not any more."""
    trends = cato.income_statement().analyze_trends()["revenue"]
    assert [cato.get_revenue(i) for i in range(3)] == list(trends[:3])


def test_cato_total_reconciles_to_its_components(cato):
    """Ground truth: the difference is exactly the other-income component."""
    period = "duration_2023-01-29_2024-02-03"
    total = filed_value(cato, "Revenues", period)
    contract = filed_value(
        cato, "RevenueFromContractWithCustomerIncludingAssessedTax", period)
    assert total == Decimal("708059000")
    assert contract == Decimal("700318000")
    assert total - contract == Decimal("7741000")
    # The getter must return the total, which is what it used to miss by.
    assert cato.get_revenue() == float(total)


@pytest.mark.parametrize("directory, expected", [
    # Filings whose only top line is contract revenue must be unaffected by
    # the reordering: 'Revenue' matches nothing and the search falls through.
    (Path("tests/fixtures/xbrl/aapl/10k_2023"), 383285000000.0),
    (Path("tests/fixtures/xbrl/aapl/10k_2022"), 394328000000.0),
    (Path("tests/fixtures/xbrl/msft/10k_2024"), 245122000000.0),
])
def test_contract_revenue_only_filers_are_unchanged(directory, expected):
    assert _financials(directory).get_revenue() == expected


# --------------------------------------------------------------------------
# GH #1291 -- basic shares behind an abstract heading
# --------------------------------------------------------------------------

def test_aubn_basic_shares_are_not_shadowed_by_the_abstract_heading(aubn):
    assert aubn.get_shares_outstanding_basic() == 3498030.0
    assert aubn.get_shares_outstanding_basic(1) == 3510869.0
    assert aubn.get_financial_metrics()["shares_outstanding_basic"] == 3498030.0


def test_aubn_statement_really_does_lead_with_an_abstract_row(aubn):
    """Pin the mechanism, so the test cannot pass for an unrelated reason.

    If the filing ever stopped presenting the heading above the populated row,
    the test above would still pass while testing nothing.
    """
    frame = (aubn.income_statement().render(standard=True)
             .to_dataframe(presentation=False))
    matching = frame[frame["concept"].str.contains(
        "WeightedAverageNumberOfSharesOutstandingBasic", case=False, na=False)]

    concepts = list(matching["concept"])
    assert concepts == [
        "us-gaap_WeightedAverageNumberOfSharesOutstandingBasicAbstract",
        "us-gaap_WeightedAverageNumberOfSharesOutstandingBasic",
    ], "the abstract heading must still sort first for this to be a regression test"
    assert bool(matching.iloc[0]["abstract"]) is True
    assert bool(matching.iloc[1]["abstract"]) is False


def test_cato_reports_no_basic_shares_and_that_is_correct(cato):
    """Applicability control: None must still mean 'not on this statement'.

    Cato's face income statement genuinely carries no weighted-average share
    row, so the fix must not invent one by widening the search.
    """
    frame = (cato.income_statement().render(standard=True)
             .to_dataframe(presentation=False))
    assert not frame["concept"].str.contains(
        "WeightedAverageNumberOfShares", case=False, na=False).any()
    assert cato.get_shares_outstanding_basic() is None
