"""Regression test for GH #1682: rows merged distinct members that share a label.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1682

Statement building grouped a concept's dimensional facts by their display key,
which is built from labels ("dei:LegalEntityAxis: GE Capital"). Two members of
one axis with the same label fell into one row: the row kept the first member's
identity and the later member's amounts overwrote the first's. Facts are now
grouped by their axis and member names.

Ground truth:
- Netflix 10-Q for 2024-03-31 (0001065280-24-000128, fixture
  tests/fixtures/xbrl/nflx/2024), debt schedule: three notes labeled "3.625%
  Senior Notes" with face amounts USD 500,000,000
  (ThreePointSixTwoFivePercentSeniorNotesIssuedApril2020Member), EUR
  1,300,000,000 (ThreePointSixTwoFivePercentSeniorNotesMember) and EUR
  1,100,000,000 (...IssuedOctober2019Member). One row appeared, under the April
  2020 USD note, carrying EUR 1,100,000,000.
  Netflix also files each euro note's USD amount in the same context (f-432 USD
  1,401,000,000 beside f-495 EUR 1,300,000,000; f-450 USD 1,187,000,000 beside
  f-499 EUR 1,100,000,000). Since GH #1704 a statement row keeps the
  reporting-currency fact, so the rows read in USD.
- GE 10-K for FY2020 (0000040545-21-000011), ShortTermBorrowings:
  ge:SubsidiariesGeccMember 2,028,000,000 / 13,598,000,000 and ge:GECapitalMember
  4,461,000,000 / 15,702,000,000 at 2020-12-31 / 2019-12-31, both labeled
  "GE Capital".
"""
from pathlib import Path

import pytest

from edgar import find
from edgar.xbrl import XBRL
from edgar.xbrl.presentation import StatementView

NFLX_10Q = Path("tests/fixtures/xbrl/nflx/2024")
NFLX_DEBT_ROLE = "http://www.netflix.com/role/DebtScheduleofLongtermDebtDetails"


@pytest.mark.fast
def test_netflix_notes_sharing_a_label_keep_their_own_amounts():
    xbrl = XBRL.from_directory(NFLX_10Q)
    rows = [row for row in xbrl.get_statement(NFLX_DEBT_ROLE, view=StatementView.DETAILED)
            if row.get("is_dimension") and row["concept"] == "us-gaap_DebtInstrumentFaceAmount"
            and "3.625%" in row["full_dimension_label"]]
    by_note = {row["dimension_metadata"][0]["member"]: (row["values"]["instant_2024-03-31"],
                                                        row["units"]["instant_2024-03-31"])
               for row in rows}
    assert by_note == {
        "nflx_ThreePointSixTwoFivePercentSeniorNotesIssuedApril2020Member": (500_000_000, "usd"),
        "nflx_ThreePointSixTwoFivePercentSeniorNotesMember": (1_401_000_000, "usd"),
        "nflx_ThreePointSixTwoFivePercentSeniorNotesIssuedOctober2019Member": (1_187_000_000, "usd"),
    }


@pytest.mark.network
def test_ge_capital_members_are_separate_rows():
    statement = find("0000040545-21-000011").xbrl().statements.balance_sheet()
    df = statement.to_dataframe(view="detailed", presentation=False, standard=False)
    rows = df[df["concept"].eq("us-gaap_ShortTermBorrowings") & df["dimension_axis"].eq("dei:LegalEntityAxis")
              & ~df["dimension_label"].str.contains("ShortTermDebtTypeAxis", na=False)].set_index("dimension_member")
    assert rows.loc["ge_SubsidiariesGeccMember", "2020-12-31"] == 2_028_000_000  # was 4,461,000,000
    assert rows.loc["ge_SubsidiariesGeccMember", "2019-12-31"] == 13_598_000_000
    assert rows.loc["ge_GECapitalMember", "2020-12-31"] == 4_461_000_000
    assert rows.loc["ge_GECapitalMember", "2019-12-31"] == 15_702_000_000
