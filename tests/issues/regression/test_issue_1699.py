"""Regression test for GitHub Issue #1699.

``TTMCalculator.calculate_ttm`` labelled ``TTMMetric.periods`` with each
quarter's raw ``fiscal_year``. ``quarterize`` keeps the latest-filed fact for a
period, and a quarter repeated as a comparative carries the later filing's
fiscal year, so Apple's TTM revenue to 2023-07-01 read
[(2022, 'Q4'), (2024, 'Q1'), (2024, 'Q2'), (2024, 'Q3')]. Labels now come from
the period end and the fiscal year-end month, as ``calculate_ttm_trend`` does.

A 52/53-week year that closes a few days into the month after its fiscal
year-end month (Costco 2023-09-03, Home Depot 2026-02-01) is labelled with the
year it closes, not the next one.

``as_of`` still selects by period end, not by what was filed by that date, and
``fiscal_period`` still comes from the latest-filed fact, so a re-filed
comparative can read 'FY'. The point-in-time view is the keyword-only
``filed_by`` (maintainer decision 2026-11-11): only facts from filings made on
or before that date are used, chosen before any quarter is derived, and only a
gap-free four-quarter window qualifies.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1699
"""
import json
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from edgar.entity.enhanced_statement import calculate_fiscal_year_for_label
from edgar.entity.entity_facts import EntityFacts
from edgar.entity.models import FinancialFact
from edgar.entity.parser import EntityFactsParser
from edgar.exceptions import InvalidDateError, ValidationError
from edgar.httprequests import download_json
from edgar.ttm.calculator import TTMCalculator

pytestmark = pytest.mark.regression

# Apple company facts. Fiscal year ends late September. Quarterly revenue
# (RevenueFromContractWithCustomerExcludingAssessedTax), fiscal 2023:
# Q1 to 2022-12-31 117,154,000,000; Q2 to 2023-04-01 94,836,000,000;
# Q3 to 2023-07-01 81,797,000,000 (10-Q 0000320193-23-000077); fiscal 2022 Q4
# to 2022-09-24 90,146,000,000. The latest-filed copies are the fiscal 2024
# 10-Qs' comparatives, e.g. 10-Q 0000320193-24-000006 for Q1.
AAPL_FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json"


@pytest.mark.vcr
def test_apple_ttm_revenue_periods_are_labelled_by_their_own_fiscal_year():
    facts = EntityFactsParser.parse_company_facts(download_json(AAPL_FACTS))
    ttm = facts.get_ttm_revenue(as_of=date(2023, 7, 1))

    assert ttm.value == 383_933_000_000
    assert [q.period_end for q in ttm.period_facts] == [
        date(2022, 9, 24), date(2022, 12, 31), date(2023, 4, 1), date(2023, 7, 1)]
    # Before the fix: [(2022, 'Q4'), (2024, 'Q1'), (2024, 'Q2'), (2024, 'Q3')].
    assert ttm.periods == [(2022, "Q4"), (2023, "Q1"), (2023, "Q2"), (2023, "Q3")]


@pytest.mark.parametrize("period_end, fye_month, label", [
    (date(2023, 9, 3), 8, 2023),    # Costco FY2023 closes in September
    (date(2026, 2, 1), 1, 2026),    # Home Depot FY2025 (named FY2026 here) closes in February
    (date(2023, 1, 1), 12, 2022),   # existing December rule
    (date(2023, 11, 20), 8, 2024),  # Costco Q1 of the next year
])
def test_year_end_drifting_into_the_next_month_closes_its_fiscal_year(period_end, fye_month, label):
    assert calculate_fiscal_year_for_label(period_end, fye_month) == label


# Costco: fiscal 2023 is 2022-08-29..2023-09-03, net income 6,292,000,000 (10-K
# 0000909832-23-000042). Home Depot: 2025-02-03..2026-02-01, net income
# 14,156,000,000 (10-K 0001628280-26-019436).
COST_FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000909832.json"
HD_FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000354950.json"


@pytest.mark.vcr
def test_fifty_two_fifty_three_week_year_is_labelled_by_the_year_it_closes():
    cost = EntityFactsParser.parse_company_facts(download_json(COST_FACTS)).get_ttm("NetIncomeLoss", as_of="2023-09-05")
    assert cost.value == 6_292_000_000
    # Before the fix: [(2023, 'Q1'), (2023, 'Q2'), (2023, 'Q3'), (2024, 'Q4')].
    assert cost.periods == [(2023, "Q1"), (2023, "Q2"), (2023, "Q3"), (2023, "Q4")]

    hd = EntityFactsParser.parse_company_facts(download_json(HD_FACTS)).get_ttm("NetIncomeLoss", as_of="2026-02-01")
    assert hd.value == 14_156_000_000
    # Before the fix: the quarter ending 2026-02-01 read (2027, 'Q4').
    assert hd.periods == [(2026, "Q1"), (2026, "Q2"), (2026, "Q3"), (2026, "Q4")]


# --- filed_by: a filing-date cutoff (maintainer decision 2026-11-11) ---------
#
# Apple's Q3 FY2023 10-Q, accession 0000320193-23-000077, was filed 2023-08-04.
# It reported revenue of 81,797,000,000 for 2023-04-02..2023-07-01 and
# 293,787,000,000 for the nine months 2022-09-25..2023-07-01.
#
# Filings made by 2023-08-03 end at the quarter to 2023-04-01:
#   Q3 FY22 (to 2022-06-25)  82,959,000,000  10-Q 0000320193-22-000070, filed 2022-07-29
#   Q4 FY22 (to 2022-09-24)  90,146,000,000  = FY22 394,328,000,000 (10-K 0000320193-22-000108,
#                                              filed 2022-10-28) - nine months 304,182,000,000 (22-000070)
#   Q1 FY23 (to 2022-12-31) 117,154,000,000  10-Q 0000320193-23-000006, filed 2023-02-03
#   Q2 FY23 (to 2023-04-01)  94,836,000,000  10-Q 0000320193-23-000064, filed 2023-05-05
#   total                   385,095,000,000
# Filings made by 2023-08-04 add Q3 FY23 81,797,000,000 and drop Q3 FY22:
#   90,146 + 117,154 + 94,836 + 81,797 = 383,933 (million), which is also
#   FY22 394,328 + nine months FY23 293,787 - nine months FY22 304,182.
APPLE_Q3_FY23_10Q = "0000320193-23-000077"


@pytest.mark.vcr
def test_filed_by_admits_apple_q3_fy2023_only_from_its_filing_date():
    facts = EntityFactsParser.parse_company_facts(download_json(AAPL_FACTS))
    q3_10q = {(f.period_start, f.period_end): f.numeric_value for f in facts._facts
              if f.accession == APPLE_Q3_FY23_10Q
              and f.concept.endswith("RevenueFromContractWithCustomerExcludingAssessedTax")
              and f.filing_date == date(2023, 8, 4)}
    assert q3_10q[(date(2023, 4, 2), date(2023, 7, 1))] == 81_797_000_000
    assert q3_10q[(date(2022, 9, 25), date(2023, 7, 1))] == 293_787_000_000

    before = facts.get_ttm_revenue(filed_by="2023-08-03")
    assert before.value == 385_095_000_000
    assert before.as_of_date == date(2023, 4, 1)
    assert before.period_end_cutoff == date(2023, 8, 3) and before.filed_by == date(2023, 8, 3)
    assert all(f.filing_date <= date(2023, 8, 3) for f in before.period_facts)
    assert APPLE_Q3_FY23_10Q not in {f.accession for f in before.period_facts}

    on_the_day = facts.get_ttm_revenue(filed_by=date(2023, 8, 4))
    assert on_the_day.value == 383_933_000_000
    assert on_the_day.as_of_date == date(2023, 7, 1)
    assert on_the_day.period_facts[-1].accession == APPLE_Q3_FY23_10Q
    assert on_the_day.periods == [(2022, "Q4"), (2023, "Q1"), (2023, "Q2"), (2023, "Q3")]

    # The two cutoffs are independent: a July 1 reporting cutoff with filings to
    # August 3 still cannot see the quarter to July 1.
    split = facts.get_ttm_revenue(as_of="2023-07-01", filed_by="2023-08-03")
    assert (split.value, split.as_of_date, split.period_end_cutoff) == (
        385_095_000_000, date(2023, 4, 1), date(2023, 7, 1))

    # Earlier cutoff -> later cutoff -> default: nothing leaks between calls. The
    # default call still reads the later-filed comparatives, as before.
    default = facts.get_ttm_revenue(as_of=date(2023, 7, 1))
    assert default.value == 383_933_000_000 and default.filed_by is None
    assert max(f.filing_date for f in default.period_facts) > date(2023, 8, 4)
    assert facts.get_ttm_revenue(filed_by="2023-08-03").value == 385_095_000_000

    # Per-share earnings take the same cutoff: the FY2023 diluted EPS of 6.13
    # (10-K 0000320193-23-000106, filed 2023-11-03) exists from that day; the day
    # before, the latest twelve months are not a filed fiscal year.
    eps = facts.get_ttm("EarningsPerShareDiluted", filed_by="2023-11-03")
    assert (eps.value, eps.as_of_date) == (6.13, date(2023, 9, 30))
    with pytest.raises(ValidationError, match="not a fiscal year"):
        facts.get_ttm("EarningsPerShareDiluted", filed_by="2023-11-02")


# Mastercard (tracked fixture tests/fixtures/entity/ma_facts.json), us-gaap:Revenues.
# FY2023 10-K 0001141391-24-000022 was filed 2024-02-13: FY2023 25,098,000,000 less
# nine months 18,550,000,000 (10-Q 0001141391-23-000157, filed 2023-10-26) gives
# Q4 6,548,000,000; with Q1 5,748, Q2 6,269, Q3 6,533 (million) the year is 25,098.
# A day earlier the latest window ends 2023-09-30: Q4 2022 = FY2022 22,237 (10-K
# 0001141391-23-000020) - nine months 16,420 (10-Q 0001141391-22-000163) = 5,817,
# and 5,817 + 5,748 + 6,269 + 6,533 = 24,367 (million).
MA_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "entity" / "ma_facts.json"


@pytest.fixture(scope="module")
def mastercard():
    return EntityFactsParser.parse_company_facts(json.loads(MA_FIXTURE.read_text("utf-8")))


def test_filed_by_mastercard_q4_needs_the_10k(mastercard):
    before = mastercard.get_ttm("Revenues", as_of="2023-12-31", filed_by="2024-02-12")
    assert (before.value, before.as_of_date) == (24_367_000_000, date(2023, 9, 30))
    assert before.period_end_cutoff == date(2023, 12, 31) and before.filed_by == date(2024, 2, 12)

    filed = mastercard.get_ttm("Revenues", as_of="2023-12-31", filed_by="2024-02-13")
    assert (filed.value, filed.as_of_date) == (25_098_000_000, date(2023, 12, 31))
    assert filed.period_facts[-1].accession == "0001141391-24-000022"

    default = mastercard.get_ttm("Revenues", as_of="2023-12-31")
    assert default.value == 25_098_000_000
    assert default.period_facts[-1].accession == "0001141391-26-000013"  # the FY2025 10-K's comparative


def test_company_forwards_filed_by(mastercard):
    from edgar.entity.core import Company
    holder = SimpleNamespace(facts=mastercard)
    assert Company.get_ttm(holder, "Revenues", "2023-12-31", filed_by="2024-02-12").value == 24_367_000_000
    assert Company.get_ttm_revenue(holder, filed_by="2024-02-13").filed_by == date(2024, 2, 13)
    assert Company.get_ttm_net_income(holder, filed_by="2024-02-13").filed_by == date(2024, 2, 13)


@pytest.mark.parametrize("bad", ["2024-Q2", "2024Q2", "Aug 4 2023"])
def test_filed_by_rejects_strings_that_are_not_iso_dates(mastercard, bad):
    with pytest.raises(InvalidDateError, match="filed_by"):
        mastercard.get_ttm_revenue(filed_by=bad)


def test_calculator_filed_by_takes_a_date():
    with pytest.raises(TypeError, match="filed_by must be a date"):
        TTMCalculator([_quarter("us-gaap:Revenues", 1, date(2023, 3, 31))]).calculate_ttm(filed_by="2023-08-04")


# --- Synthetic cases ---------------------------------------------------------

def _fact(concept, value, start, end, fiscal_period, filed, form="10-Q"):
    return FinancialFact(
        concept=concept, taxonomy="us-gaap", label="Revenue", value=value,
        numeric_value=float(value), unit="USD", period_type="duration",
        period_start=start, period_end=end, fiscal_year=end.year,
        fiscal_period=fiscal_period, accession=f"0009999999-{filed:%y%m%d}" if filed else None,
        filing_date=filed, form_type=form)


def _quarter(concept, value, end, filed=None):
    start = {3: date(end.year, 1, 1), 6: date(end.year, 4, 1),
             9: date(end.year, 7, 1), 12: date(end.year, 10, 1)}[end.month]
    return _fact(concept, value, start, end, "Q", filed or end + timedelta(days=30))


REVENUES = "us-gaap:Revenues"
ASC606 = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"


def _tag_migration():
    """The design's tag-migration case: the new tag has four quarters spanning
    eighteen months (2022-04-01..2023-09-30, missing 2022-10-01..2023-03-31);
    the old tag has a complete year to 2023-03-31."""
    new_tag = [_quarter(REVENUES, v, e) for v, e in [
        (100, date(2022, 6, 30)), (100, date(2022, 9, 30)), (110, date(2023, 6, 30)), (110, date(2023, 9, 30))]]
    old_tag = [_quarter(ASC606, v, e) for v, e in [
        (100, date(2022, 6, 30)), (100, date(2022, 9, 30)), (105, date(2022, 12, 31)), (105, date(2023, 3, 31))]]
    return new_tag, old_tag


def test_filed_by_never_returns_a_gapped_window():
    new_tag, old_tag = _tag_migration()
    facts = EntityFacts(cik=1, name="Tag Migration Co", facts=new_tag + old_tag)

    # Default mode is unchanged: the newest window wins even though it has a gap.
    default = facts.get_ttm_revenue(as_of="2023-09-30")
    assert (default.value, default.has_gaps) == (420, True)

    ttm = facts.get_ttm_revenue(as_of="2023-09-30", filed_by="2023-11-01")
    assert (ttm.concept, ttm.value, ttm.as_of_date, ttm.has_gaps) == (ASC606, 410, date(2023, 3, 31), False)
    assert ttm.period_end_cutoff == date(2023, 9, 30) and ttm.filed_by == date(2023, 11, 1)

    # With only the gapped tag there is no qualifying window: an error naming
    # both cutoffs, not the 420 sum.
    with pytest.raises(ValidationError, match=r"2023-09-30.*2023-11-01"):
        EntityFacts(cik=1, name="Tag Migration Co", facts=new_tag).get_ttm_revenue(
            as_of="2023-09-30", filed_by="2023-11-01")
    with pytest.raises(ValidationError, match="gap"):
        TTMCalculator(new_tag).calculate_ttm(as_of=date(2023, 9, 30), filed_by=date(2023, 11, 1))


def test_every_operand_of_a_derived_quarter_must_be_filed_by_the_cutoff():
    """Q3 2023 is derived as nine months less six months. The nine-month fact was
    filed 2023-10-30, so the derived Q3 carries that date, but the six-month
    figure was first filed with no recorded filing date and otherwise only as a
    2024 comparative. On 2023-11-01 the derived Q3 is not eligible, although its
    own filing date passes: filtering after derivation would accept it."""
    facts = [
        _quarter(REVENUES, 90, date(2022, 6, 30)),
        _quarter(REVENUES, 95, date(2022, 9, 30)),
        _quarter(REVENUES, 100, date(2022, 12, 31)),
        _quarter(REVENUES, 100, date(2023, 3, 31)),
        _quarter(REVENUES, 110, date(2023, 6, 30)),
        _fact(REVENUES, 210, date(2023, 1, 1), date(2023, 6, 30), "Q2", None),
        _fact(REVENUES, 210, date(2023, 1, 1), date(2023, 6, 30), "Q2", date(2024, 7, 30)),
        _fact(REVENUES, 330, date(2023, 1, 1), date(2023, 9, 30), "Q3", date(2023, 10, 30)),
    ]
    calc = TTMCalculator(facts)

    # Default: Q4 2022 100 + Q1 100 + Q2 110 + Q3 (330 - 210) = 430
    assert calc.calculate_ttm(as_of=date(2023, 9, 30)).value == 430

    # By 2023-11-01 the six-month operand was not filed, so Q3 cannot be
    # derived: 95 + 100 + 100 + 110, ending 2023-06-30.
    early = calc.calculate_ttm(as_of=date(2023, 9, 30), filed_by=date(2023, 11, 1))
    assert (early.value, early.as_of_date, early.has_calculated_q4) == (405, date(2023, 6, 30), False)

    late = calc.calculate_ttm(filed_by=date(2024, 7, 30))
    assert (late.value, late.as_of_date) == (430, date(2023, 9, 30))
