"""GitHub Issue: https://github.com/dgunning/edgartools/issues/2019"""

from pathlib import Path

import pytest
from pandas.testing import assert_frame_equal

from edgar.xbrl import XBRL

pytestmark = pytest.mark.fast

METADATA_COLUMNS = [
    "balance", "weight", "preferred_sign", "parent_concept", "parent_abstract_concept",
]


@pytest.fixture(scope="module")
def apple():
    # Apple's FY2023 10-K, SEC accession 0000320193-23-000106.
    return XBRL.from_directory(Path("tests/fixtures/xbrl/aapl/10k_2023"))


@pytest.mark.parametrize("presentation, capex", [(True, -10_959_000_000), (False, 10_959_000_000)])
def test_omit_metadata_preserves_cash_flow_values(apple, presentation, capex):
    statement = apple.statements.cash_flow_statement()
    full = statement.to_dataframe(presentation=presentation, include_unit=True)
    lean = statement.to_dataframe(presentation=presentation, include_unit=True, include_metadata=False)

    assert_frame_equal(lean, full.drop(columns=METADATA_COLUMNS))
    capex_rows = lean["concept"] == "us-gaap_PaymentsToAcquirePropertyPlantAndEquipment"
    assert lean.loc[capex_rows, "2023-09-30 (FY)"].item() == capex


def test_omit_metadata_preserves_equity_matrix(apple):
    statement = apple.statements.statement_of_equity()
    full = statement.to_dataframe(matrix=True)
    lean = statement.to_dataframe(matrix=True, include_metadata=False)

    assert_frame_equal(lean, full)
    net_income = lean["concept"] == "us-gaap_NetIncomeLoss"
    assert lean.loc[net_income, "Retained earnings/(Accumulated deficit)"].item() == 96_995_000_000
