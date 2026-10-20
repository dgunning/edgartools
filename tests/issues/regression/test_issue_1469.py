"""Regression test for GH #1469: an instant-only note rendered blank duration columns.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1469

IBM's long-term debt components note
(http://www.ibm.com/role/BorrowingsLongTermDebtComponentsDetails) holds only
instant facts, but its role is unclassified, so period selection fell through
to the duration selector. `render_statement()` showed three annual columns
with every cell blank, and ignored an explicit instant `period_filter`.

Ground truth, read from SEC's instance for IBM's FY2024 10-K (accession
0000051143-25-000015): "Less: net unamortized discount",
us-gaap:DebtInstrumentUnamortizedDiscount, facts f-2341 / f-2342, contexts
c-73 / c-74 (no dimensions): $824,000,000 at 2024-12-31 and $838,000,000 at
2023-12-31.
"""
from pathlib import Path

import pytest

from edgar.xbrl import XBRL

ROLE = "http://www.ibm.com/role/BorrowingsLongTermDebtComponentsDetails"
TAG = "us-gaap_DebtInstrumentUnamortizedDiscount"


@pytest.fixture(scope="module")
def ibm_xbrl():
    return XBRL.from_directory(Path("tests/fixtures/xbrl/ibm/10k_2024"))


def _discount_row(rendered):
    frame = rendered.to_dataframe()
    row = frame.loc[frame["concept"].eq(TAG)]
    assert len(row) == 1
    return row.iloc[0]


@pytest.mark.fast
def test_instant_only_note_renders_its_own_instants(ibm_xbrl):
    rendered = ibm_xbrl.render_statement(ROLE, standard=False)

    assert rendered.header.period_keys == ["instant_2024-12-31", "instant_2023-12-31"]
    row = _discount_row(rendered)
    assert row["2024-12-31"] == 824_000_000
    assert row["2023-12-31"] == 838_000_000


@pytest.mark.fast
@pytest.mark.parametrize("period_key, column, value", [
    ("instant_2024-12-31", "2024-12-31", 824_000_000),
    ("instant_2023-12-31", "2023-12-31", 838_000_000),
])
def test_explicit_instant_period_filter_is_honoured(ibm_xbrl, period_key, column, value):
    rendered = ibm_xbrl.render_statement(ROLE, standard=False, period_filter=period_key)

    assert rendered.header.period_keys == [period_key]
    assert _discount_row(rendered)[column] == value


@pytest.mark.fast
def test_statement_to_dataframe_uses_the_same_instants(ibm_xbrl):
    frame = ibm_xbrl.statements[ROLE].to_dataframe()
    row = frame.loc[frame["concept"].eq(TAG)].iloc[0]

    assert row["2024-12-31"] == 824_000_000
    assert row["2023-12-31"] == 838_000_000
    assert "2022-12-31 (FY)" not in frame.columns


@pytest.mark.fast
def test_classified_statements_keep_their_periods(ibm_xbrl):
    # Controls: the balance sheet keeps its density-filtered comparison and the
    # income statement keeps its annual durations.
    assert ibm_xbrl.render_statement("BalanceSheet").header.period_keys == [
        "instant_2024-12-31", "instant_2023-12-31"]
    assert ibm_xbrl.render_statement("IncomeStatement").header.period_keys == [
        "duration_2024-01-01_2024-12-31",
        "duration_2023-01-01_2023-12-31",
        "duration_2022-01-01_2022-12-31",
    ]
