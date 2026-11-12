"""A derived cash-flow quarter mixed a recast cumulative figure with an unrecast earlier quarter.

Bead: edgartools-k7mi8.3, found while measuring GitHub Issue #1697
(https://github.com/dgunning/edgartools/issues/1697).

``StatementStitcher._unaccumulate_cashflow_ytd`` derives a discrete quarter as the
longer cumulative period minus the next-shorter one, and took each operand from
whichever filing supplied that stitched column. Microsoft's 10-Q for the quarter
ended 2025-12-31 (0001193125-26-027207) files net recognized gains on investments
and derivatives of $6,024M for the six months and $9,931M for the quarter, while
the Q1 10-Q (0001193125-25-256321) filed $1,007M for Q1, later recast to
$(3,907)M (the comparative in 10-Q 0001193125-26-436133). The default
``discrete_quarters=True`` path showed Q2 = 6,024 - 1,007 = $5,017M.

Decision (maintainer, 2026-11-11), latest vintage:
1. A three-month value an input filing presents wins over derivation, in the
   default path as with ``include_quarterly=True`` (the GH #1697 merge rule).
2. A derived quarter's operands are each the value from the latest-filed input
   that presents that exact period.
Back-deriving a recast Q1 as H1 - Q2 from one filing is not done: with only the
Q2 and Q1 10-Qs as input, Q1 stays $1,007M.
"""
import pytest

from edgar.xbrl import XBRL, XBRLS
from edgar.xbrl.stitching.core import StatementStitcher

GAINS = "msft_GainLossOnInvestmentsAndDerivativeInstruments"
OPERATING = "us-gaap_NetCashProvidedByUsedInOperatingActivities"

# Trimmed copies of the three 10-Qs' XBRL, cash flow role only; see
# tests/fixtures/xbrl/msft/10q_cashflow_README.md
MSFT = "tests/fixtures/xbrl/msft"
MSFT_Q1_FY2027 = f"{MSFT}/10q_2026q1"  # 0001193125-26-436133, filed 2026-10-28
MSFT_Q2_FY2026 = f"{MSFT}/10q_2025q2"  # 0001193125-26-027207, filed 2026-01-28
MSFT_Q1_FY2026 = f"{MSFT}/10q_2025q1"  # 0001193125-25-256321, filed 2025-10-29

Q1_FY2026 = "duration_2025-07-01_2025-09-30"
Q2_FY2026 = "duration_2025-10-01_2025-12-31"


def _values(xbrl_list, **kwargs):
    statement = XBRLS.from_xbrl_objects(xbrl_list).statements.cash_flow_statement(
        standard=False, discrete_quarters=True, **kwargs)
    return {row["concept"]: row["values"] for row in statement.statement_data["statement_data"]}


@pytest.mark.fast
def test_microsoft_q2_fy2026_uses_the_filed_quarter_and_the_latest_q1():
    q1_fy27, q2, q1 = (XBRL.from_directory(d)
                       for d in (MSFT_Q1_FY2027, MSFT_Q2_FY2026, MSFT_Q1_FY2026))

    # Default path: the filed three-month $9,931M, not 6,024 - 1,007 = 5,017
    values = _values([q2, q1])
    assert values[GAINS][Q2_FY2026] == 9_931_000_000
    # Q1 is the Q1 10-Q's own figure; the recast is not back-derived
    assert values[GAINS][Q1_FY2026] == 1_007_000_000
    # Operating cash flow derives as before: $80,815M - $45,057M
    assert values[OPERATING][Q2_FY2026] == 35_758_000_000

    # With the next year's Q1 10-Q, the latest-filed Q1 is its recast comparative,
    # and the quarters sum to the six months: -3,907 + 9,931 = 6,024
    values = _values([q1_fy27, q2, q1])
    assert values[GAINS][Q1_FY2026] == -3_907_000_000
    assert values[GAINS][Q2_FY2026] == 9_931_000_000
    # The same recast moved "depreciation, amortization and other" between the
    # quarters: 13,061 + 4,284 originally, 8,147 + 9,198 recast, both 17,345
    assert values["msft_DepreciationAmortizationAndOther"][Q1_FY2026] == 8_147_000_000
    assert values["msft_DepreciationAmortizationAndOther"][Q2_FY2026] == 9_198_000_000


def _statement(source_index, periods, lines):
    """A minimal stitcher input: ``lines`` maps concept -> {period: value}."""
    return {
        'statement_type': 'CashFlowStatement',
        'source_index': source_index,
        'periods': {p: {'label': p} for p in periods},
        'data': [{'concept': c, 'label': c, 'values': v, 'decimals': {p: -6 for p in v}}
                 for c, v in lines.items()],
    }


@pytest.mark.fast
def test_derived_quarter_takes_each_operand_from_the_latest_filing():
    """No three-month value is filed for the derived quarter, and two inputs disagree
    on the shorter period. Synthetic, shaped like NVDA's FY2026 purchases of debt
    securities: the Q2 FY2026 10-Q filed $14,358M for six months and the Q2 FY2027
    10-Q recast that comparative to $14,108M; the nine months are from the Q3 10-Q."""
    current_six = "duration_2026-01-26_2026-07-26"
    six = "duration_2025-01-27_2025-07-27"
    nine = "duration_2025-01-27_2025-10-26"
    q3 = "duration_2025-07-28_2025-10-26"
    statements = [  # newest filing first
        _statement(0, [current_six, six], {"Debt": {current_six: 9_000, six: 14_108},
                                           "Other": {current_six: 1, six: 2}}),
        _statement(1, [nine], {"Debt": {nine: 20_076}, "Other": {nine: 3}}),
        _statement(2, [six], {"Debt": {six: 14_358}, "Other": {six: 2}}),
    ]
    stitcher = StatementStitcher()
    stitcher.stitch_statements(statements, standard=False, discrete_quarters=True)
    assert stitcher.data["Debt"][q3]["value"] == 20_076 - 14_108  # main: 20,076 - 14,358
    assert stitcher.data["Debt"][six]["value"] == 14_108          # the operand cell too


@pytest.mark.fast
def test_a_note_fact_is_not_a_filed_period():
    """Only periods a statement presents as columns count as filed. JNJ's Q3 10-Q
    0000200406-26-000197 tags $17,500M of acquisitions for a six-month context its
    cash flow statement never shows (it presents nine months of $352M; the Q2 10-Q
    presents six months of $263M). Taking that as the latest six months gave
    Q3 2026 = $(17,148)M."""
    six = "duration_2025-12-29_2026-06-28"
    nine = "duration_2025-12-29_2026-09-27"
    q3 = "duration_2026-06-29_2026-09-27"
    statements = [
        _statement(0, [nine, six], {"Acquisitions": {nine: 352, six: 17_500},
                                    **{f"Line{i}": {nine: i} for i in range(6)}}),
        _statement(1, [six], {"Acquisitions": {six: 263},
                              **{f"Line{i}": {six: i} for i in range(6)}}),
    ]
    stitcher = StatementStitcher()
    stitcher.stitch_statements(statements, standard=False, discrete_quarters=True)
    assert stitcher.data["Acquisitions"][q3]["value"] == 352 - 263


@pytest.mark.fast
@pytest.mark.parametrize("company, dirs, period, expected", [
    # Apple 10-K 0000320193-23-000106 and 10-Q 0000320193-23-000077: Q4 FY2023
    ("aapl", ["10k_2023", "10q_2023"], "duration_2023-07-02_2023-09-30",
     {OPERATING: 21_598_000_000, "us-gaap_NetIncomeLoss": 22_956_000_000,
      "us-gaap_PaymentsToAcquirePropertyPlantAndEquipment": 2_163_000_000}),
    # Netflix 10-K FY2023 and 10-Q Q3 2024: no shared fiscal year, nothing derived
    ("nflx", ["10k_2024", "10q_2024"], "duration_2024-01-01_2024-09-30",
     {OPERATING: 5_824_470_000, "us-gaap_NetIncomeLoss": 6_843_024_000,
      "us-gaap_PaymentsToAcquirePropertyPlantAndEquipment": 280_864_000}),
])
def test_companies_that_do_not_recast_are_unchanged(company, dirs, period, expected):
    xbrl_list = [XBRL.from_directory(f"tests/fixtures/xbrl/{company}/{d}") for d in dirs]
    values = _values(xbrl_list, max_periods=8)
    for concept, amount in expected.items():
        assert values[concept][period] == amount
