"""
DETAILED view dropped NVIDIA reportable-segment revenue that the default view kept.

On NVDA's FY2026 10-K the notes role
``SegmentInformationScheduleofRevenuebyMarketDetails`` files revenue on two
axes at once (``srt:ConsolidationItemsAxis`` + ``us-gaap:StatementBusinessSegmentsAxis``).
``get_raw_data()`` returned those six annual observations. ``view=DETAILED``
returned none, and substituted single-axis ProductOrService "Compute" /
"Networking" rows instead.

DETAILED also includes Data Center's definition-linkbase children. That activated
``_apply_member_hierarchy``, which keyed every dimensional row by its first
member. Both segment combinations share ``OperatingSegmentsMember`` on the first
axis, so last-wins dropped them.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1331
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.presentation import StatementView

NVDA = Path("tests/fixtures/xbrl/nvda/10k_2026")
ROLE = (
    "http://www.nvidia.com/role/"
    "SegmentInformationScheduleofRevenuebyMarketDetails"
)
SEG_AXIS = "us-gaap:StatementBusinessSegmentsAxis"
PROD_AXIS = "srt:ProductOrServiceAxis"

FY2026 = "duration_2025-01-27_2026-01-25"
FY2025 = "duration_2024-01-29_2025-01-26"
FY2024 = "duration_2023-01-30_2024-01-28"

# Note 16 of nvda-20260125.htm, USD not millions.
COMPUTE_AND_NETWORKING = {
    FY2026: 193_479_000_000,
    FY2025: 116_193_000_000,
    FY2024: 47_405_000_000,
}
GRAPHICS = {
    FY2026: 22_459_000_000,
    FY2025: 14_304_000_000,
    FY2024: 13_517_000_000,
}
COMPUTE_PRODUCT = {FY2026: 162_361_000_000}
NETWORKING_PRODUCT = {FY2026: 31_376_000_000}


def _axes(row):
    return [d.get("dimension") for d in row.get("dimension_metadata") or []]


def _members(row):
    return [d.get("member") for d in row.get("dimension_metadata") or []]


def _segment_revenue_rows(rows):
    return [row for row in rows if row.get("concept") == "us-gaap_Revenues" and SEG_AXIS in _axes(row)]


def _product_row(rows, member):
    for row in rows:
        if row.get("concept") == "us-gaap_Revenues" and PROD_AXIS in _axes(row) and member in _members(row):
            return row
    return None


def _segment_row(rows, member):
    for row in _segment_revenue_rows(rows):
        if member in _members(row):
            return row
    return None


@pytest.fixture(scope="module")
def nvda_xbrl():
    assert NVDA.exists(), f"missing fixture: {NVDA}"
    return XBRL.from_directory(NVDA)


def _raw(nvda_xbrl, view=None):
    return nvda_xbrl.statements[ROLE].get_raw_data(view=view)


def test_default_and_detailed_keep_the_filed_segment_revenue(nvda_xbrl):
    default_rows = _raw(nvda_xbrl)
    detailed_rows = _raw(nvda_xbrl, view=StatementView.DETAILED)

    for rows, view_name in ((default_rows, "default"), (detailed_rows, "detailed")):
        compute = _segment_row(rows, "nvda_ComputeAndNetworkingSegmentMember")
        graphics = _segment_row(rows, "nvda_GraphicsSegmentMember")
        assert compute is not None, f"{view_name} dropped Compute & Networking"
        assert graphics is not None, f"{view_name} dropped Graphics"
        for period, expected in COMPUTE_AND_NETWORKING.items():
            assert compute["values"].get(period) == expected, f"{view_name} Compute & Networking {period}: {compute['values']}"
        for period, expected in GRAPHICS.items():
            assert graphics["values"].get(period) == expected, f"{view_name} Graphics {period}: {graphics['values']}"


def test_detailed_still_includes_data_center_product_children(nvda_xbrl):
    """DETAILED's GH-574 job is to surface Compute/Networking under Data Center."""
    rows = _raw(nvda_xbrl, view=StatementView.DETAILED)
    compute = _product_row(rows, "nvda_ComputeMember")
    networking = _product_row(rows, "nvda_NetworkingMember")
    assert compute is not None, "DETAILED lost ProductOrService Compute"
    assert networking is not None, "DETAILED lost ProductOrService Networking"
    assert compute["values"][FY2026] == COMPUTE_PRODUCT[FY2026]
    assert networking["values"][FY2026] == NETWORKING_PRODUCT[FY2026]


def test_hierarchy_does_not_collapse_two_axis_rows_onto_the_first_member():
    """The last-wins map on meta[0] is the defect, independent of NVIDIA's tree."""
    items = [
        {
            "label": "Operating Segments - Compute & Networking",
            "level": 1,
            "dimension_metadata": [
                {"dimension": "srt:ConsolidationItemsAxis", "member": "us-gaap_OperatingSegmentsMember"},
                {"dimension": "us-gaap:StatementBusinessSegmentsAxis", "member": "nvda_ComputeAndNetworkingSegmentMember"},
            ],
        },
        {
            "label": "Operating Segments - Graphics",
            "level": 1,
            "dimension_metadata": [
                {"dimension": "srt:ConsolidationItemsAxis", "member": "us-gaap_OperatingSegmentsMember"},
                {"dimension": "us-gaap:StatementBusinessSegmentsAxis", "member": "nvda_GraphicsSegmentMember"},
            ],
        },
        {
            "label": "Data Center",
            "level": 1,
            "dimension_metadata": [
                {"dimension": "srt:ProductOrServiceAxis", "member": "nvda_DataCenterMember"},
            ],
        },
        {
            "label": "Compute",
            "level": 1,
            "dimension_metadata": [
                {"dimension": "srt:ProductOrServiceAxis", "member": "nvda_ComputeMember"},
            ],
        },
        {
            "label": "Networking",
            "level": 1,
            "dimension_metadata": [
                {"dimension": "srt:ProductOrServiceAxis", "member": "nvda_NetworkingMember"},
            ],
        },
    ]
    dummy = SimpleNamespace(
        parser=SimpleNamespace(domains={"nvda_DataCenterMember": SimpleNamespace(members=["nvda_ComputeMember", "nvda_NetworkingMember"])})
    )
    XBRL._apply_member_hierarchy(dummy, items)

    labels = [item["label"] for item in items]
    assert labels[:2] == [
        "Operating Segments - Compute & Networking",
        "Operating Segments - Graphics",
    ]
    assert labels[2:] == ["Data Center", "Compute", "Networking"]
    by_label = {item["label"]: item["level"] for item in items}
    assert by_label["Data Center"] == 1
    assert by_label["Compute"] == 2
    assert by_label["Networking"] == 2
    assert by_label["Operating Segments - Compute & Networking"] == 1
