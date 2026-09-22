"""A member filed on two different axes lost one of its rows.

``XBRL._apply_member_hierarchy`` keys ``member_to_item`` on the member ID alone.
JPMorgan's 2012 10-K files ``us-gaap:VariableInterestEntityPrimaryBeneficiaryMember``
on two axes at once for ``us-gaap:LoansAndLeasesReceivableNetOfDeferredIncome``:

    dei:LegalEntityAxis                                           82,723 / 86,754 M
    us-gaap:VariableInterestEntitiesByClassificationOfEntityAxis   82,700 / 86,800 M

The two rows collided in that map, last-wins, and the ``dei:LegalEntityAxis`` row
was dropped from the statement entirely — silently, and it carried the more
precise of the two figures.

This is the single-axis residual of the collapse fixed for two-axis rows in
GH #1331: that fix took the corpus from 209 lossy calls to 7, and these were the
7. The domain hierarchy cannot say which axis's row a shared member nests under,
so neither row participates in the reorder now and both pass through.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1331
Bead: edgartools-3h3q
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.presentation import StatementView

JPM = Path("tests/fixtures/xbrl/jpm/10k_2013")
ROLE = (
    "http://www.jpmorganchase.com/role/"
    "VariableInterestEntitiesConsolidatedVieAssetsAndLiabilitiesDetails3"
)
CONCEPT = "us-gaap_LoansAndLeasesReceivableNetOfDeferredIncome"
MEMBER = "us-gaap_VariableInterestEntityPrimaryBeneficiaryMember"

LEGAL_ENTITY_AXIS = "dei:LegalEntityAxis"
CLASSIFICATION_AXIS = "us-gaap:VariableInterestEntitiesByClassificationOfEntityAxis"

FY2012 = "instant_2012-12-31"
FY2011 = "instant_2011-12-31"

# jpm-20121231.xml, contexts I2012Q4_/I2011Q4_dei_LegalEntityAxis_us-gaap_
# VariableInterestEntityPrimaryBeneficiaryMember. USD, not millions.
LEGAL_ENTITY_VALUES = {FY2012: 82_723_000_000, FY2011: 86_754_000_000}
CLASSIFICATION_VALUES = {FY2012: 82_700_000_000, FY2011: 86_800_000_000}


@pytest.fixture(scope="module")
def jpm_xbrl():
    assert JPM.exists(), f"missing fixture: {JPM}"
    return XBRL.from_directory(JPM)


def _axes(row):
    return [d.get("dimension") for d in row.get("dimension_metadata") or []]


def _row_on_axis(rows, axis):
    for row in rows:
        meta = row.get("dimension_metadata") or []
        if (row.get("concept") == CONCEPT
                and len(meta) == 1
                and meta[0].get("member") == MEMBER
                and meta[0].get("dimension") == axis):
            return row
    return None


def test_both_axes_survive_with_their_filed_values(jpm_xbrl):
    """The reported loss: the LegalEntityAxis row disappeared from DETAILED."""
    rows = jpm_xbrl.statements[ROLE].get_raw_data(view=StatementView.DETAILED)

    legal_entity = _row_on_axis(rows, LEGAL_ENTITY_AXIS)
    classification = _row_on_axis(rows, CLASSIFICATION_AXIS)

    assert legal_entity is not None, "dei:LegalEntityAxis row was dropped"
    assert classification is not None, "classification-axis row was dropped"

    for period, expected in LEGAL_ENTITY_VALUES.items():
        assert legal_entity["values"].get(period) == expected, legal_entity["values"]
    for period, expected in CLASSIFICATION_VALUES.items():
        assert classification["values"].get(period) == expected, classification["values"]


def test_the_hierarchy_never_drops_a_row_on_this_filing(jpm_xbrl):
    """`_apply_member_hierarchy` reorders in place; it must be a permutation of
    its input, never lossy. A corpus sweep is how this bug was found, so assert
    the property directly rather than trusting a row count."""
    original = XBRL._apply_member_hierarchy
    losses = []

    def probe(self, dim_items):
        before = list(dim_items)
        original(self, dim_items)
        if sorted(map(id, before)) != sorted(map(id, dim_items)):
            losses.append([i.get("full_dimension_label") for i in before
                           if not any(x is i for x in dim_items)])

    XBRL._apply_member_hierarchy = probe
    try:
        for stmt in jpm_xbrl.get_all_statements():
            for view in (None, StatementView.DETAILED):
                try:
                    jpm_xbrl.statements[stmt["role"]].get_raw_data(view=view)
                except Exception:  # noqa: S110 - render failures are not this test's subject
                    pass
    finally:
        XBRL._apply_member_hierarchy = original

    assert losses == [], f"rows dropped by the member hierarchy: {losses}"


def test_a_member_on_two_axes_leaves_both_rows_in_place():
    """The defect in isolation, independent of any filing: one member, two axes,
    plus a same-axis parent/child pair to activate the reorder."""
    items = [
        {"label": "LegalEntity - VIE primary beneficiary", "level": 1,
         "dimension_metadata": [{"dimension": "dei:LegalEntityAxis", "member": "m_shared"}]},
        {"label": "Classification - VIE primary beneficiary", "level": 1,
         "dimension_metadata": [{"dimension": "us-gaap:ClassificationAxis", "member": "m_shared"}]},
        {"label": "Parent", "level": 1,
         "dimension_metadata": [{"dimension": "srt:ProductAxis", "member": "m_parent"}]},
        {"label": "Child", "level": 1,
         "dimension_metadata": [{"dimension": "srt:ProductAxis", "member": "m_child"}]},
    ]
    dummy = SimpleNamespace(
        parser=SimpleNamespace(domains={"m_parent": SimpleNamespace(members=["m_child"])})
    )

    XBRL._apply_member_hierarchy(dummy, items)

    labels = [item["label"] for item in items]
    assert sorted(labels) == sorted([
        "LegalEntity - VIE primary beneficiary",
        "Classification - VIE primary beneficiary",
        "Parent",
        "Child",
    ]), f"a row was dropped or duplicated: {labels}"

    # The ambiguous member is not reordered or re-levelled; the unambiguous
    # parent/child pair still nests.
    by_label = {item["label"]: item["level"] for item in items}
    assert by_label["LegalEntity - VIE primary beneficiary"] == 1
    assert by_label["Classification - VIE primary beneficiary"] == 1
    assert by_label["Parent"] == 1
    assert by_label["Child"] == 2
