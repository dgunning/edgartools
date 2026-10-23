"""Regression test for GH #1657: to_dataframe() gave every row of a concept its first sign.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1657

XBRL puts preferredLabel on the presentation arc, so a concept presented twice
in one role can carry a negated label on the face and a terse label in a second
table. ``Statement._add_metadata_columns()`` looked the display sign up by
concept from its first occurrence, so ``to_dataframe()`` negated the second
appearance too, while ``render().to_dataframe()`` signed each row on its own.
Each row now takes its own occurrence's sign.

Ground truth: Chesapeake Utilities 10-Q for 2026-03-31 (0001628280-26-031397),
cash flow statement: PaymentsToAcquirePropertyPlantAndEquipment is presented as
(141.9) million on the face (negatedLabel) and 141.9 million again under
StatementTable with terseLabel; likewise 11.3 million of IncreaseDecreaseIn
AccountsReceivable and 16.2 million of PaymentsOfDividendsCommonStock.
"""
import copy
from pathlib import Path

import pytest

from edgar import find
from edgar.xbrl import XBRL

TSLA_10Q = Path("tests/fixtures/xbrl/tsla")
CONCEPT = "us-gaap_RepaymentsOfConvertibleDebt"
PERIOD = "duration_2024-01-01_2024-06-30"


@pytest.mark.fast
def test_each_occurrence_keeps_its_own_sign(monkeypatch):
    statement = XBRL.from_directory(TSLA_10Q).statements.cash_flow_statement()
    raw = statement.get_raw_data()
    face = next(item for item in raw if item["concept"] == CONCEPT and not item.get("is_dimension"))
    assert face["preferred_signs"][PERIOD] == -1

    # Present the concept a second time with a terse (as-is) label, as CPK does.
    second = copy.deepcopy(face)
    second["label"] = "Repayments of debt (terse)"
    second["preferred_signs"] = {key: 1 for key in second["preferred_signs"]}
    patched = raw + [second]
    monkeypatch.setattr(statement, "get_raw_data", lambda *args, **kwargs: patched)

    df = statement.to_dataframe(standard=False)
    rows = df[df["concept"] == CONCEPT].set_index("label")
    assert rows.loc["Repayments of debt", "preferred_sign"] == -1
    assert rows.loc["Repayments of debt (terse)", "preferred_sign"] == 1
    assert rows.loc["Repayments of debt", "2024-06-30 (YTD)"] == -1_222_000_000
    assert rows.loc["Repayments of debt (terse)", "2024-06-30 (YTD)"] == 1_222_000_000
    assert "_row_preferred_sign" not in df.columns


@pytest.mark.network
def test_chesapeake_second_appearances_match_render():
    statement = find("0001628280-26-031397").xbrl().statements.cash_flow_statement()
    concepts = {"us-gaap_PaymentsToAcquirePropertyPlantAndEquipment": 141_900_000,
                "us-gaap_IncreaseDecreaseInAccountsReceivable": 11_300_000,
                "us-gaap_PaymentsOfDividendsCommonStock": 16_200_000}
    frames = (statement.to_dataframe(), statement.render().to_dataframe())
    for frame in frames:
        period = next(c for c in frame.columns if str(c).startswith("2026-03-31"))
        for concept, amount in concepts.items():
            values = frame.loc[frame["concept"] == concept, period].tolist()
            assert values == [-amount, amount], (concept, values)
