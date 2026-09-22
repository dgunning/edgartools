"""Period identity comes from durations, not from SEC filing-focus labels.

edgartools-51xd; GH #1179, #1180, #1185, #1197.

The SEC's ``fiscal_period``/``fiscal_year`` on a Company Facts row say which
FILING the row came from, not which period it covers. In the Snowflake ledger 778
nine-month YTD facts are tagged ``Q3``, 600 six-month YTD facts are tagged ``Q2``,
154 real ~92-day quarters are tagged ``FY``, and one full year is tagged ``Q1``.
Every consumer that reads those labels as a period type inherits the error, which
is what these four issues are.

Expectations below come from the filed SEC values named in each issue, computed by
hand, not from the library.
"""
import json
from datetime import date
from pathlib import Path

import pytest

from edgar.entity.parser import EntityFactsParser
from edgar.ttm.calculator import TTMCalculator

SNOW_FACTS = Path("tests/fixtures/entity/snow_facts.json")
LPA_FACTS = Path("tests/fixtures/entity/lpa_facts.json")


@pytest.fixture(scope="module")
def snow():
    return EntityFactsParser.parse_company_facts(json.loads(SNOW_FACTS.read_text()))


@pytest.fixture(scope="module")
def lpa():
    return EntityFactsParser.parse_company_facts(json.loads(LPA_FACTS.read_text()))


# --------------------------------------------------------------------------- #
# The premise, asserted rather than assumed
# --------------------------------------------------------------------------- #

def test_the_fiscal_period_label_does_not_describe_the_period(snow):
    """If this ever stops being true the rest of the file is testing nothing."""
    ytd9_tagged_q3 = ytd6_tagged_q2 = quarter_tagged_fy = 0
    for fact in snow.get_all_facts():
        if not (fact.period_start and fact.period_end):
            continue
        days = (fact.period_end - fact.period_start).days
        if 230 <= days <= 329 and fact.fiscal_period == "Q3":
            ytd9_tagged_q3 += 1
        elif 140 <= days <= 229 and fact.fiscal_period == "Q2":
            ytd6_tagged_q2 += 1
        elif 70 <= days <= 120 and fact.fiscal_period == "FY":
            quarter_tagged_fy += 1

    assert ytd9_tagged_q3 > 500, "9-month YTD facts tagged Q3"
    assert ytd6_tagged_q2 > 500, "6-month YTD facts tagged Q2"
    assert quarter_tagged_fy > 100, "~92-day quarters tagged FY"


# --------------------------------------------------------------------------- #
# GH #1180 -- a 273-day YTD figure presented as Q3
# --------------------------------------------------------------------------- #

def test_quarterly_cash_flow_reports_the_discrete_quarter_not_the_ytd(snow):
    """SNOW 10-Q 0001640147-21-000271, nine months ended 2021-10-31.

    Filed: nine-month YTD 3,042,396,000 and six-month YTD 1,988,633,000, so the
    discrete quarter is 1,053,763,000. The Q3 column used to carry the 273-day
    YTD figure -- a 2.89x overstatement.
    """
    stmt = snow.cash_flow_statement(periods=30, period="quarterly", as_dataframe=True)
    # The statement renders us-gaap:PaymentsToAcquireInvestments under its standard
    # label; the SEC caption on Snowflake's own filing is "Purchases of investments".
    row = stmt[stmt["label"].astype(str).str.contains("Payments to Acquire Investments",
                                                     case=False, na=False)]
    assert not row.empty, "fixture changed: concept not on the statement"

    assert row["Q3 2022"].iloc[0] == pytest.approx(1_053_763_000)
    assert row["Q3 2022"].iloc[0] != pytest.approx(3_042_396_000), "still the YTD figure"


def test_comparative_refilings_are_not_discarded_as_invalid(snow):
    """The upstream cause. A comparative carries the FILING's fiscal year, so it
    fails a plain fiscal_year/period_end consistency check; rejecting it threw away
    the six-month YTD operand that the Q3 derivation subtracts, leaving the YTD
    figure as the only candidate for the column."""
    prepared = snow._ttm_ready_facts
    concept = "us-gaap:PaymentsToAcquireInvestments"
    ending = [f for f in prepared.get_all_facts()
              if f.concept == concept and f.period_end == date(2021, 10, 31)]
    durations = sorted((f.period_end - f.period_start).days for f in ending if f.period_start)
    assert 91 in durations, "the derived discrete quarter is missing"


# --------------------------------------------------------------------------- #
# GH #1197 -- a 457-day "quarter"
# --------------------------------------------------------------------------- #

def test_quarterize_never_returns_a_period_that_is_not_a_quarter(snow):
    """Deriving across two fiscal cycles is arithmetically valid and semantically
    nonsense: SNOW goodwill produced -45,711,000 over 2023-05-01..2024-07-31,
    an interval 457 days long, by subtracting the prior year's Q1 from the current
    six-month figure."""
    concept = "us-gaap:GoodwillPeriodIncreaseDecrease"
    facts = [f for f in snow.get_all_facts() if f.concept == concept]
    assert facts, "fixture changed: concept absent"

    quarters = TTMCalculator(facts).quarterize()
    for fact in quarters:
        days = (fact.period_end - fact.period_start).days
        assert 70 <= days <= 120, (
            f"{fact.calculation_context} produced a {days}-day period "
            f"{fact.period_start}..{fact.period_end}")

    assert not [f for f in quarters if f.numeric_value == -45_711_000]


def test_the_quarter_invariant_holds_for_every_concept_in_the_ledger(snow):
    """The bug was found on one concept; the guard is not concept-specific, so
    neither is the check."""
    by_concept = {}
    for fact in snow.get_all_facts():
        by_concept.setdefault(fact.concept, []).append(fact)

    malformed = []
    for concept, facts in by_concept.items():
        try:
            for q in TTMCalculator(facts).quarterize():
                if q.period_start and q.period_end:
                    days = (q.period_end - q.period_start).days
                    if not 70 <= days <= 120:
                        malformed.append((concept, days))
        except (ValueError, KeyError, AttributeError, IndexError, TypeError):
            continue
    assert malformed == []


# --------------------------------------------------------------------------- #
# GH #1185 -- one period asked for, three returned
# --------------------------------------------------------------------------- #

def test_latest_periods_counts_economic_periods_not_filing_labels(lpa):
    """LPA 20-F 0001997711-25-000030 reports 2022, 2023 and 2024 comparatively and
    the SEC tags all three fy=2024, fp=FY. Keyed on that label they were one
    period, so asking for one returned three."""
    facts = (lpa.query()
             .by_concept("ifrs-full:Revenue", exact=True)
             .latest_periods(1, annual=True)
             .execute())

    periods = {(f.period_start, f.period_end) for f in facts}
    assert len(periods) == 1, f"expected one economic period, got {sorted(periods)}"
    assert periods == {(date(2024, 1, 1), date(2024, 12, 31))}, "and it should be the most recent"


@pytest.mark.parametrize("n", [1, 2, 3])
def test_latest_periods_returns_n_distinct_economic_periods(lpa, n):
    facts = (lpa.query()
             .by_concept("ifrs-full:Revenue", exact=True)
             .latest_periods(n, annual=True)
             .execute())
    assert len({(f.period_start, f.period_end) for f in facts}) == n


# --------------------------------------------------------------------------- #
# GH #1179 -- an unchanged 12-month value relabelled Q4
# --------------------------------------------------------------------------- #

def _stitcher_with_meta_shaped_deferred_tax():
    """Meta's FY2024 cash flow, reduced to the two rows that matter.

    The 10-K tags "Deferred income taxes" `DeferredIncomeTaxesAndTaxCredits` while
    the Q3 10-Q tags the identically-labelled line `DeferredIncomeTaxExpenseBenefit`
    (accessions 0001326801-25-000017 and 0001326801-24-000081). The concept that
    only exists on the 12-month period therefore has no 9-month operand to subtract.

    Values are Meta's, in millions as filed: FY $(4,738), nine-month $(3,406), so
    the derivable Q4 is $(1,332).
    """
    from edgar.xbrl.stitching.core import StatementStitcher

    fy = "duration_2024-01-01_2024-12-31"
    ytd9 = "duration_2024-01-01_2024-09-30"

    stitcher = StatementStitcher()
    stitcher.periods = [fy, ytd9]
    stitcher.period_dates = {fy: "FY 2024", ytd9: "YTD Sep 30, 2024"}
    # Present on both periods -> Q4 is derivable.
    stitcher.data["Net cash provided by operating activities"] = {
        fy: {"value": 91_328, "decimals": 0},
        ytd9: {"value": 63_609, "decimals": 0},
    }
    # Present only on the 12-month period -> Q4 is NOT derivable.
    stitcher.data["Deferred income taxes"] = {
        fy: {"value": -4_738, "decimals": 0},
    }
    return stitcher, fy


def test_a_quarter_that_cannot_be_derived_is_dropped_not_left_cumulative():
    stitcher, fy = _stitcher_with_meta_shaped_deferred_tax()
    stitcher._unaccumulate_cashflow_ytd()

    deferred = stitcher.data["Deferred income taxes"]
    assert fy not in deferred, (
        "the unchanged 12-month value is still present under a discrete-quarter label; "
        f"got {deferred.get(fy)}")
    assert -4_738 not in [entry.get("value") for entry in deferred.values()]


def test_the_derivable_neighbour_on_the_same_period_still_converts():
    """The control. Dropping the underivable cell must not cost the cells that do
    have both operands, or the fix would empty the column instead of correcting it."""
    stitcher, fy = _stitcher_with_meta_shaped_deferred_tax()
    stitcher._unaccumulate_cashflow_ytd()

    operating = stitcher.data["Net cash provided by operating activities"]
    assert operating[fy]["value"] == pytest.approx(91_328 - 63_609)
