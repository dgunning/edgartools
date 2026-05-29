"""
Regression test for Issue #825: PP&E line item duplicated on CLW balance sheet

GitHub Issue: https://github.com/dgunning/edgartools/issues/825
Reporter: GitHub user mkdeak

Bug (FIXED): Clearwater Paper's (CLW) 10-K balance sheet rendered
"Property, plant and equipment" twice with identical values, and the second
occurrence stole a terse label that mislabeled the net PP&E line.

Root cause: CLW's presentation linkbase emits two parent-child arcs from
``us-gaap_AssetsAbstract`` to ``us-gaap_PropertyPlantAndEquipmentNet`` (order 2
with a totalLabel, order 4 with a terseLabel). Because presentation nodes are
keyed by element_id, both arcs collapse to a single node, but the parent's
children list retained the duplicate reference -- so statement generation
emitted the same concept twice.

Fix: ``_build_presentation_subtree`` now deduplicates child references under a
parent, keeping the first (lowest-order) occurrence.

Note: the accumulated-depreciation line showing as a positive value is a filer
presentation inconsistency (the face arc uses a plain terseLabel rather than a
negatedTerseLabel), not an edgartools defect, and is intentionally out of scope
for this fix.

Filing: CIK 1441236, accession 0001441236-26-000007, FY2025 10-K.
"""

import pytest
from edgar import Company


@pytest.mark.network
@pytest.mark.regression
def test_issue_825_no_duplicate_ppe_line():
    """CLW balance sheet must contain PropertyPlantAndEquipmentNet exactly once."""
    filing = Company("CLW").get_filings(form="10-K").latest(1)
    assert filing.accession_no == "0001441236-26-000007"

    line_items = filing.xbrl().get_statement("BalanceSheet")
    ppe_net = [
        item
        for item in line_items
        if item.get("concept") == "us-gaap_PropertyPlantAndEquipmentNet"
        and not item.get("is_dimension")
    ]

    assert len(ppe_net) == 1, (
        f"PropertyPlantAndEquipmentNet should appear once, found {len(ppe_net)}"
    )

    # Ground-truth value from the SEC filing (in thousands): net PP&E = $1,001,800
    values = ppe_net[0]["values"]
    assert values["instant_2025-12-31"] == 1_001_800_000.0
    assert values["instant_2024-12-31"] == 1_023_100_000.0

    # The surviving line keeps the net (totalLabel) wording, not a bare "Property,
    # plant and equipment" that would read as gross.
    assert "net" in ppe_net[0]["label"].lower()
