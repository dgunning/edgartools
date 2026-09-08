"""Regression test for issue #1224.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1224

Tesla's STANDARD statement of operations carried four automotive member
headings -- "Automotive Revenues", "Automotive sales", "Automotive regulatory
credits", "Automotive leasing" -- with empty value maps and no fact rows behind
them.

The report reads these as residue left by the STANDARD view's dimensional
filtering. They are not: they come from the presentation linkbase's inline
hypercube declaration ("Statement [Table]" -> "Product and Service [Axis]" ->
"[Domain]" -> one node per member), no fact ever hangs off those nodes, and
they appeared in the DETAILED view too. `render_statement` already dropped them
on the way to Rich output, so only the raw `get_statement()` / `to_dataframe()`
/ Markdown paths exposed them.

`XBRL._prune_empty_structural_items` now drops an abstract row when neither it
nor anything under it carries a value.
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.presentation import StatementView

TSLA = Path(__file__).resolve().parents[3] / "data" / "xbrl" / "datafiles" / "tsla"
ROLE = "http://www.tesla.com/role/ConsolidatedStatementsofOperations"

MEMBER_HEADINGS = {
    "tsla_AutomotiveRevenuesMember",
    "tsla_AutomotiveSalesMember",
    "tsla_AutomotiveRegulatoryCreditsMember",
    "tsla_AutomotiveLeasingMember",
    "tsla_EnergyGenerationAndStorageMember",
    "tsla_ServicesAndOtherMember",
}


@pytest.fixture(scope="module")
def tsla_xbrl():
    assert TSLA.exists(), f"missing fixture: {TSLA}"
    return XBRL.from_directory(TSLA)


@pytest.mark.parametrize("view", [StatementView.STANDARD, StatementView.DETAILED])
def test_no_row_is_a_permanently_empty_heading(tsla_xbrl, view):
    rows = tsla_xbrl.get_statement(ROLE, view=view)

    orphans = [row for row in rows if row.get("concept") in MEMBER_HEADINGS]
    assert orphans == [], f"empty member headings survived: {[r['label'] for r in orphans]}"

    axis_and_domain = [row["label"] for row in rows
                       if "[Axis]" in row["label"] or "[Domain]" in row["label"]]
    assert axis_and_domain == []


def test_the_filed_values_those_headings_stood_for_are_untouched(tsla_xbrl):
    """Pruning must remove headings only -- never a row carrying a value."""
    rows = tsla_xbrl.get_statement(ROLE, view=StatementView.DETAILED)
    q2_2024 = "duration_2024-04-01_2024-06-30"

    by_label = {}
    for row in rows:
        by_label.setdefault(row["label"], []).append(row)

    # The three automotive revenue components from the report.
    for label, expected in [("Automotive sales", 18_530_000_000),
                            ("Automotive regulatory credits", 890_000_000),
                            ("Automotive leasing", 458_000_000)]:
        values = [row["values"].get(q2_2024) for row in by_label.get(label, [])
                  if row.get("concept", "").endswith("RevenueFromContractWithCustomerExcludingAssessedTax")]
        assert expected in values, f"{label} lost its filed value: {values}"


def test_a_section_heading_with_data_under_it_survives(tsla_xbrl):
    """The prune walks the subtree; it must not drop ordinary abstract headers."""
    labels = [row["label"] for row in tsla_xbrl.get_statement(ROLE, view=StatementView.STANDARD)]

    for heading in ("Revenues", "Cost of revenues", "Operating expenses"):
        assert heading in labels
