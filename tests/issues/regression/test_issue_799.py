"""
Regression test for GH #799: viewer.concept_rows[*].level always 0.

Modern SEC R*.htm files don't encode hierarchy in the rendered HTML — no
``plN`` class tokens, no ``padding-left`` styles, and no row nesting (verified
empirically across AAPL, ABT, JPM, WMT, XOM, VZ, MSFT, GS, PFE, BRK.B 2025
10-Ks). The canonical source is the XBRL **presentation linkbase**.

The fix lazy-loads the parsed XBRL on first ``concept_rows`` access and
populates ``ConceptRow.level`` from
``xbrl.presentation_trees[role].all_nodes[concept_id].depth``, normalized so
the smallest depth observed in the report becomes 0.

The lazy-on-access design avoids re-entering the (stateful) FilingSummary
``Reports`` iterator during construction, which previously truncated
``viewer.financial_statements``.
"""
from __future__ import annotations

import pytest

from edgar import Filing


# Pinned ABT 2025 10-K (the canary case from the issue report).
ABT_CIK = 1800
ABT_2025_ACC = "0001628280-26-010185"


@pytest.fixture(scope="module")
def abt_2025_viewer():
    filing = Filing(form="10-K", filing_date="2026-02-21",
                    company="Abbott Laboratories", cik=ABT_CIK,
                    accession_no=ABT_2025_ACC)
    return filing.viewer


@pytest.mark.network
def test_balance_sheet_concept_rows_have_nonzero_levels(abt_2025_viewer):
    """
    Ground truth: ABT balance sheet has 45 concept rows whose hierarchy has
    historically been silently flattened to level=0. After the fix the
    levels must show real depth distribution (multiple distinct values).
    """
    bs = next((vr for vr in abt_2025_viewer.financial_statements
               if "Balance Sheet" in vr.short_name and "Parenthetical" not in vr.short_name),
              None)
    assert bs is not None, "ABT balance sheet not found"

    rows = bs.concept_rows
    levels = {row.level for row in rows}

    # Must have at least 3 distinct levels (top-level, child, sub-child).
    assert len(levels) >= 3, f"Expected >=3 distinct levels, got {sorted(levels)}"

    # Smallest level normalized to 0
    assert min(levels) == 0, f"Smallest level should be 0, got {min(levels)}"

    # No row in the issue's canonical report should be at level 0 ONLY
    # (the original bug had every row at level 0).
    nonzero = sum(1 for row in rows if row.level > 0)
    assert nonzero >= 10, f"Expected >=10 indented rows, got {nonzero}"


@pytest.mark.network
def test_inventory_subitems_indented_below_total_inventories(abt_2025_viewer):
    """
    Ground truth from the issue: inventory line items (Finished products,
    Work in process, Materials) are children of "Inventories:" so must have
    a strictly higher level than the parent abstract.
    """
    bs = next(vr for vr in abt_2025_viewer.financial_statements
              if "Balance Sheet" in vr.short_name and "Parenthetical" not in vr.short_name)
    rows = bs.concept_rows
    by_concept = {row.concept_id: row for row in rows}

    parent = by_concept.get("us-gaap_InventoryNetAbstract")
    finished_goods = by_concept.get("us-gaap_InventoryFinishedGoodsNetOfReserves")
    work_in_process = by_concept.get("us-gaap_InventoryWorkInProcessNetOfReserves")
    raw_materials = by_concept.get("us-gaap_InventoryRawMaterialsNetOfReserves")

    assert parent is not None
    for child in (finished_goods, work_in_process, raw_materials):
        assert child is not None
        assert child.level > parent.level, (
            f"Child {child.concept_id} (level={child.level}) should be deeper than "
            f"parent us-gaap_InventoryNetAbstract (level={parent.level})"
        )


@pytest.mark.network
def test_financial_statements_list_complete_after_levels_lazy_load(abt_2025_viewer):
    """
    Regression: an earlier draft of the fix triggered XBRL parsing during
    FilingSummary report iteration, which corrupted the (stateful) Reports
    iterator and truncated ``financial_statements`` to a single entry.
    The lazy-on-access design must keep the full list intact.
    """
    stmts = list(abt_2025_viewer.financial_statements)
    assert len(stmts) >= 4, (
        f"Expected at least 4 primary statements, got {len(stmts)}: "
        f"{[s.short_name for s in stmts]}"
    )
    short_names = [s.short_name for s in stmts]
    # Touch concept_rows on the *last* report (forces XBRL parse), then
    # verify the list is still intact.
    _ = stmts[-1].concept_rows
    stmts_after = list(abt_2025_viewer.financial_statements)
    assert [s.short_name for s in stmts_after] == short_names


@pytest.mark.network
def test_levels_consistent_across_multiple_companies():
    """
    Sanity: the fix must produce non-trivial level distributions for diverse
    filers, not just ABT. We don't pin specific values (filings update over
    time) — just assert the *shape*: min level is 0, levels span at least
    two values for any primary balance sheet.
    """
    cases = [
        # (cik, accession, filing_date, company)
        (320193, "0000320193-25-000079", "2025-10-31", "Apple Inc."),
        (789019, "0000950170-25-100235", "2025-07-30", "Microsoft Corporation"),
    ]
    for cik, acc, fdate, name in cases:
        filing = Filing(form="10-K", filing_date=fdate, company=name,
                        cik=cik, accession_no=acc)
        viewer = filing.viewer
        bs = next((vr for vr in viewer.financial_statements
                   if "BALANCE" in vr.short_name.upper()
                   and "Parenthetical" not in vr.short_name),
                  None)
        assert bs is not None, f"{name}: balance sheet not found"
        levels = {row.level for row in bs.concept_rows}
        assert min(levels) == 0, f"{name}: min level = {min(levels)}, expected 0"
        assert len(levels) >= 2, f"{name}: only one level distinct = {levels}"
