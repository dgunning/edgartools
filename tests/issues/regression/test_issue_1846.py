"""Legacy text 13F rows with '-' voting cells keep each quantity in its own column.

Berkshire Hathaway Inc, 13F-HR for 2012-12-31, accession 0001193125-13-060317 (filed 2013-02-14),
primary document d481559d13fhr.txt (kept unedited in tests/fixtures/13f/berkshire-1846). It writes an
empty voting cell as '-'. The reverse numeric scan in `_parse_after_cusip` stopped at a dash, so the first
AMERICAN EXPRESS entry (Sole 1,952,142, Shared '-', None '-') returned SoleVoting=0 and the four
WASHINGTON POST entries (Sole '-', Shared '-', None 148,311 ...) filed their None quantity under Sole.

The fix reads the trailing 3, 2 or 1 tokens as the voting cells only when they contain a dash and their
quantities add up to the row's shares, so a manager number such as '2' is never mistaken for a quantity.
Rows without a dash take the unchanged path. Offline.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1846
"""
from pathlib import Path

import pytest

from edgar.thirteenf.parsers.infotable_txt import parse_infotable_txt
from edgar.thirteenf.parsers.infotable_txt.format_multiline import _parse_after_cusip

pytestmark = pytest.mark.fast

PRIMARY = Path(__file__).resolve().parents[2] / "fixtures" / "13f" / "berkshire-1846" / "primary.txt"


@pytest.fixture(scope="module")
def table():
    return parse_infotable_txt(PRIMARY.read_text())


def test_american_express_keeps_its_sole_quantity(table):
    assert len(table) == 123
    first = table.iloc[0]
    assert (first["Cusip"], first["Value"], first["SharesPrnAmount"]) == ("025816109", 112_209, 1_952_142)
    assert (first["SoleVoting"], first["SharedVoting"], first["NonVoting"]) == (1_952_142, 0, 0)


def test_washington_post_none_quantities_stay_in_none(table):
    wapo = table[table["Cusip"] == "939640108"]
    assert wapo["NonVoting"].tolist() == [148_311, 648_165, 894_304, 36_985]
    assert wapo["SoleVoting"].tolist() == [0, 0, 0, 0]
    assert wapo["SharedVoting"].tolist() == [0, 0, 0, 0]


def test_every_row_voting_adds_up_to_its_shares(table):
    assert table["Value"].sum() == 75_313_620  # the filing's cover total
    assert (table["SoleVoting"] + table["SharedVoting"] + table["NonVoting"] == table["SharesPrnAmount"]).all()


def test_a_manager_number_is_not_a_voting_quantity():
    """TDAM USA Inc 13F-HR (accession 0000950123-11-012369), AMAZON COM INC: manager '2', Sole 1,185, Shared '-'."""
    row = _parse_after_cusip(["213", "1,185", "Defined", "2", "1,185", "-"])
    assert (row["SoleVoting"], row["SharedVoting"], row["NonVoting"]) == (1_185, 0, 0)
    assert row["InvestmentDiscretion"] == "Defined"


def test_rows_without_a_dash_are_unchanged():
    row = _parse_after_cusip(["697,973", "17,225,400", "X", "4,", "2,", "5,", "17", "17,225,400", "0", "0"])
    assert (row["SoleVoting"], row["SharedVoting"], row["NonVoting"]) == (17_225_400, 0, 0)
