"""
Regression tests for edgartools-hsgs: four statement-level helpers that
computed from the wrong rows.

GH #1280 -- `calculate_ratios()` fetched every period and then let each operand
independently take the first value in ITS OWN dictionary, whose order is
insertion order, not recency. Netflix's Q3 2024 net margin came out as 0.2767:
Q3 2024 net income over Q3 2023 revenue, a figure belonging to neither quarter.
`CurrentPeriodStatement.calculate_ratios()` made it worse by delegating to the
unfiltered statement, so even an explicit current-period object returned the
mixed answer while its own `get_raw_data()` held the right operands.

GH #1281 -- `_compute_synthetic_total()` grouped dimensional facts by axis and
summed everything in the largest group. Sharing an axis does not make members
disjoint: a statement of shareholders' equity carries the components AND the
filer's own subtotals on one axis, so Disney's 2022-10-01 beginning balance was
reported as $292,766,000,000 against a filed $98,879,000,000 -- the four
components, their ParentMember subtotal, the noncontrolling interest and the
issuer's total member all added together.

GH #1292 -- `analyze_trends()` returned `{}` whenever no NAMED period view
existed. The IncomeStatement views require three normal durations, so a 10-K
presenting exactly two annual periods had none and a request for two periods
came back empty although both were present.

GH #1290 -- `to_dict()` is documented as JSON-safe but passed non-finite floats
through. `_calculate_comparison()` produces `inf` whenever the prior period is
a filed zero, which is ordinary, so the result carried a bare `Infinity` token
that no compliant reader accepts and `allow_nan=False` refuses outright.

MEASURED across the fixture corpus: 20 cell values change, all of them on
statements carrying aggregate members, and NONE is lost or gained. Beyond
Disney's headline row the same double count was inflating its dividends
(4,098 -> 1,366), its share-based stock issuance (3,600 -> 1,200) and a pension
asset allocation that read 2.0 where an allocation cannot exceed 1.0. Fourteen
ratio results change; each moves onto the period the statement actually
reports -- Microsoft FY2015 to 64.7% gross margin on its filed 93,580 revenue,
Apple FY2010 to 39.4%.

NOTE ON AN EXISTING TEST. `test_ysr8_statement_helpers.py` asserted Apple's
FY2010 gross margin as 0.3520. That is FY2008 (13,197/37,491) -- a consistent
pairing, but of the oldest comparative on a statement reporting FY2010, which
is precisely the defect. It now asserts the filed 0.3938.
"""

import json
import math
from pathlib import Path

import pytest

from edgar.xbrl import XBRL

NFLX_10Q = Path("tests/fixtures/xbrl/nflx/10q_2024")
KO_10K = Path("tests/fixtures/xbrl/ko/10k_2024")
KO_2012 = Path("tests/fixtures/xbrl/ko/10k_2012")
DIS = Path("tests/fixtures/xbrl/dis/10k_2025")
AUBN = Path("tests/fixtures/xbrl/aubn/10k_2023")


@pytest.fixture(scope="module")
def nflx():
    return XBRL.from_directory(NFLX_10Q)


@pytest.fixture(scope="module")
def dis():
    return XBRL.from_directory(DIS)


@pytest.fixture(scope="module")
def aubn():
    return XBRL.from_directory(AUBN)


# --------------------------------------------------------------------------
# GH #1280 -- ratios must take every operand from one period
# --------------------------------------------------------------------------

def test_netflix_net_margin_uses_one_quarter(nflx):
    """2,363,509 / 9,824,703, both Q3 2024. Was Q3 2024 over Q3 2023."""
    ratios = nflx.statements["IncomeStatement"].calculate_ratios()
    assert ratios["net_margin"] == pytest.approx(0.24056798459963624)
    assert ratios["net_margin"] != pytest.approx(0.27670344949019327)


def test_netflix_operands_are_the_filed_quarter(nflx):
    """Ground truth: the ratio equals the filed facts for that one quarter."""
    period = "duration_2024-07-01_2024-09-30"
    data = nflx.statements["IncomeStatement"].get_raw_data(period)

    def value(concept):
        item = next(i for i in data if concept in i.get("all_names", []) and i.get("values"))
        return item["values"][period]

    assert value("us-gaap_Revenues") == 9824703000.0
    assert value("us-gaap_NetIncomeLoss") == 2363509000.0
    assert nflx.statements["IncomeStatement"].calculate_ratios()["net_margin"] == \
        pytest.approx(2363509000.0 / 9824703000.0)


def test_current_period_statement_honours_its_own_filter(nflx):
    """The wrapper's ratios must match the period it was narrowed to."""
    current = nflx.current_period.income_statement()
    assert current.period_filter == "duration_2024-07-01_2024-09-30"
    assert current.calculate_ratios()["net_margin"] == pytest.approx(0.24056798459963624)


def test_ratios_accept_an_explicit_period(nflx):
    """A caller can ask for a period, and gets that period's ratio."""
    statement = nflx.statements["IncomeStatement"]
    prior = statement.calculate_ratios(period="duration_2023-07-01_2023-09-30")
    assert prior["net_margin"] == pytest.approx(1677422000.0 / 8541668000.0)


@pytest.mark.parametrize("fixture, ratio, expected", [
    (KO_10K, "net_margin", 0.23416531887922368),      # was FY2022 income / FY2023 revenue
    (KO_2012, "current_ratio", 1.049993822839023),    # was 2011 assets / 2010 liabilities
])
def test_other_filings_with_mixed_operands(fixture, ratio, expected):
    xbrl = XBRL.from_directory(fixture)
    kind = "IncomeStatement" if ratio == "net_margin" else "BalanceSheet"
    assert xbrl.statements[kind].calculate_ratios()[ratio] == pytest.approx(expected)


def test_a_missing_operand_leaves_the_ratio_out(nflx):
    """Silence check: no ratio is better than one borrowed from elsewhere."""
    statement = nflx.statements["BalanceSheet"]
    ratios = statement.calculate_ratios(period="duration_1999-01-01_1999-12-31")
    assert ratios == {}


# --------------------------------------------------------------------------
# GH #1281 -- synthetic totals must not double-count
# --------------------------------------------------------------------------

def equity_row(xbrl, label, concept):
    frame = xbrl.statements.statement_of_equity().to_dataframe()
    rows = frame.loc[frame["concept"].eq(concept) & frame["label"].eq(label)
                     & ~frame["dimension"].fillna(False)]
    assert len(rows) == 1
    return rows.iloc[0]


def test_disney_beginning_equity_is_the_filed_total(dis):
    """98,879 and 103,957 as filed, not the 292,766 / 307,191 sums."""
    concept = ("us-gaap_StockholdersEquityIncludingPortionAttributable"
               "ToNoncontrollingInterest")
    beginning = equity_row(dis, "BEGINNING BALANCE", concept)
    assert beginning["2023-09-30 (FY)"] == 98879000000.0
    assert beginning["2024-09-28 (FY)"] == 103957000000.0


def test_disney_components_reconcile_to_that_total(dis):
    """Ground truth from the filed facts, so the number is not merely pinned.

    The four equity components sum to the ParentMember subtotal; adding the
    noncontrolling interest gives the issuer's own total member. Adding all
    seven -- which is what the helper did -- gives the reported 292,766.
    """
    concept = ("us-gaap:StockholdersEquityIncludingPortionAttributable"
               "ToNoncontrollingInterest")
    frame = (dis.facts.query().by_concept(concept, exact=True)
             .by_period_key("instant_2022-10-01").with_dimensions().to_dataframe())
    members = dict(zip(frame["dim_us-gaap_StatementEquityComponentsAxis"],
                       frame["numeric_value"]))

    components = {
        "us-gaap:CommonStockMember": 56398000000.0,
        "us-gaap:RetainedEarningsMember": 43636000000.0,
        "us-gaap:AccumulatedOtherComprehensiveIncomeMember": -4119000000.0,
        "us-gaap:TreasuryStockCommonMember": -907000000.0,
    }
    assert {m: members[m] for m in components} == components
    assert sum(components.values()) == members["us-gaap:ParentMember"] == 95008000000.0

    total_member = "dis:TotalexcludingredeemablenoncontrollinginterestMember"
    assert (members["us-gaap:ParentMember"]
            + members["us-gaap:NoncontrollingInterestMember"]) == members[total_member]
    assert members[total_member] == 98879000000.0

    # Adding every member of the axis is the double count that was reported.
    assert sum(members.values()) == 292766000000.0


def test_disney_period_with_a_filed_total_is_unchanged(dis):
    """Control: FY2025 has a non-dimensional fact and bypasses this path."""
    concept = ("us-gaap_StockholdersEquityIncludingPortionAttributable"
               "ToNoncontrollingInterest")
    assert equity_row(dis, "BEGINNING BALANCE", concept)["2025-09-27 (FY)"] == \
        105522000000.0


@pytest.mark.parametrize("concept, column, expected", [
    # The same double count was inflating other lines of the same statement.
    ("us-gaap_DividendsCommonStock", "2024-09-28 (FY)", 1366000000.0),
    ("us-gaap_StockIssuedDuringPeriodValueShareBasedCompensation",
     "2025-09-27 (FY)", 1200000000.0),
])
def test_other_disney_equity_lines_are_no_longer_tripled(dis, concept, column, expected):
    frame = dis.statements.statement_of_equity().to_dataframe()
    rows = frame.loc[frame["concept"].eq(concept) & ~frame["dimension"].fillna(False)]
    assert expected in [v for v in rows[column].tolist()
                        if isinstance(v, (int, float)) and not math.isnan(v)]


def test_a_disjoint_breakdown_still_sums():
    """Must not regress gh #646, which is why this helper exists.

    Coca-Cola tags shareowners' equity solely against ParentMember: one member,
    no components, nothing to double-count, and the filed value must survive.
    """
    xbrl = XBRL.from_directory(KO_10K)
    frame = xbrl.statements.statement_of_equity().to_dataframe()
    rows = frame.loc[frame["concept"].eq("us-gaap_StockholdersEquity")
                     & ~frame["dimension"].fillna(False)]
    values = [v for v in rows["2021-12-31 (FY)"].tolist()
              if isinstance(v, (int, float)) and not math.isnan(v)]
    assert 22999000000.0 in values


# --------------------------------------------------------------------------
# GH #1292 -- trends without a named period view
# --------------------------------------------------------------------------

def test_two_period_10k_reports_its_trend(aubn):
    """Both annual periods are present; a named view is not a precondition."""
    assert aubn.get_period_views("IncomeStatement") == []
    trends = aubn.statements["IncomeStatement"].analyze_trends(periods=2)
    assert trends["revenue"] == [603000.0, 598000.0]


def test_those_values_are_the_filed_ones(aubn):
    statement = aubn.statements["IncomeStatement"]
    concept = "us-gaap_RevenueFromContractWithCustomerIncludingAssessedTax"
    for period, expected in (("duration_2023-01-01_2023-12-31", 603000.0),
                             ("duration_2022-01-01_2022-12-31", 598000.0)):
        item = next(i for i in statement.get_raw_data(period) if i["concept"] == concept)
        assert item["values"][period] == expected


def test_the_named_view_path_is_unchanged():
    """Control: a filing WITH period views must behave exactly as before."""
    xbrl = XBRL.from_directory(KO_10K)
    assert xbrl.get_period_views("IncomeStatement")
    trends = xbrl.statements["IncomeStatement"].analyze_trends(periods=2)
    assert trends["revenue"] == [45754000000.0, 43004000000.0]


# --------------------------------------------------------------------------
# GH #1290 -- to_dict must be JSON
# --------------------------------------------------------------------------

@pytest.mark.parametrize("fixture, kind", [
    (NFLX_10Q, "CashFlowStatement"),
    (KO_10K, "CashFlowStatement"),
    (Path("tests/fixtures/xbrl/msft/10k_2015"), "IncomeStatement"),
])
def test_to_dict_is_strict_json(fixture, kind):
    payload = XBRL.from_directory(fixture).statements[kind].render().to_dict()
    # allow_nan=False is what "JSON-safe" means; the default writes bare
    # Infinity/NaN tokens that no compliant reader accepts.
    json.dumps(payload, allow_nan=False)
    assert "Infinity" not in json.dumps(payload)


def test_filed_values_are_not_disturbed_by_that(nflx):
    """Only generated comparison metadata changes; cells stay as filed."""
    payload = nflx.statements["CashFlowStatement"].render().to_dict()
    values = [c["value"] for r in payload["rows"] for c in r["cells"]
              if isinstance(c["value"], (int, float))]
    assert values, "no numeric cells; the test would prove nothing"
    assert all(math.isfinite(v) for v in values)
