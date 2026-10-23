"""Stitched cash flow put continuing-operations cash in the total row.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1690

NetCashProvidedByUsedInOperatingActivities and its *ContinuingOperations
variant pass the name-variant check and share a standard concept, so the
stitcher merged them whenever no overlapping stitched period disagreed. When the
filing that supplies the continuing amount also reports nonzero discontinued-
operations cash for that activity and period, the continuing amount is not the
total, and the merge put it in the total row. The merge is now blocked in that
case; filings with no discontinued cash keep merging.

Ground truth: AT&T 10-Q 0000732717-26-000297 (six months ended 2026-06-30)
tags continuing operating cash 18,396,000,000 and investing -13,233,000,000,
with discontinued operating 31,000,000 and investing -4,363,000,000. AT&T 10-Q
0000732717-25-000080 tags the 2025 totals 18,812,000,000 and -11,044,000,000.
"""
import pytest

from edgar.xbrl.stitching.core import StatementStitcher

OP = "us-gaap_NetCashProvidedByUsedInOperatingActivities"
OP_CONT = "us-gaap_NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"
OP_DISC = "us-gaap_CashProvidedByUsedInOperatingActivitiesDiscontinuedOperations"


def _stmt(start, end, rows, comparative=None):
    pid = f"duration_{start}_{end}"
    data = []
    for concept, label, value in rows:
        values = {pid: value}
        if comparative and concept in comparative:
            values.update(comparative[concept])
        data.append({"concept": concept, "label": label, "level": 1, "is_abstract": False,
                     "is_total": False, "values": values, "decimals": {pid: -6}})
    return {"statement_type": "CashFlowStatement", "periods": {pid: {"label": end}}, "data": data}


def _rows(statements):
    out = StatementStitcher().stitch_statements(statements)
    return {r["concept"]: r["values"] for r in out["statement_data"]}


@pytest.mark.fast
def test_continuing_amount_stays_out_of_total_when_discontinued_is_reported():
    p25 = "duration_2025-01-01_2025-06-30"
    rows = _rows([
        _stmt("2026-01-01", "2026-06-30",
              [(OP_CONT, "Net cash from operating activities, continuing", 18396),
               (OP_DISC, "Cash provided by operating activities", 31)],
              comparative={OP_CONT: {p25: 18812}, OP_DISC: {p25: 0}}),
        _stmt("2025-01-01", "2025-06-30", [(OP, "Net cash from operating activities", 18812)]),
    ])
    assert rows[OP] == {p25: 18812}
    assert rows[OP_CONT] == {"duration_2026-01-01_2026-06-30": 18396}
    assert rows[OP_DISC] == {"duration_2026-01-01_2026-06-30": 31}


@pytest.mark.fast
def test_continuing_variant_still_merges_without_discontinued_cash():
    rows = _rows([
        _stmt("2015-07-01", "2016-06-30", [(OP_CONT, "Net cash from operations", 300)]),
        _stmt("2014-07-01", "2015-06-30", [(OP, "Net cash from operations", 200)]),
    ])
    assert len(rows) == 1
    (values,) = rows.values()
    assert values == {"duration_2015-07-01_2016-06-30": 300, "duration_2014-07-01_2015-06-30": 200}


@pytest.mark.network
def test_att_continuing_cash_not_in_total_rows():
    from edgar import find
    from edgar.xbrl import XBRLS

    xbrls = [find(a).xbrl() for a in ("0000732717-26-000297", "0000732717-25-000080")]
    frame = XBRLS.from_xbrl_objects(xbrls).statements.cash_flow_statement().to_dataframe()
    by_concept = frame.set_index("concept")

    def cell(concept, col):
        value = by_concept.loc[concept, col]
        return None if value != value else value

    assert cell(OP, "2025-06-30") == 18_812_000_000
    assert cell(OP, "2026-06-30") is None
    assert cell(OP_CONT, "2026-06-30") == 18_396_000_000
    inv, inv_cont = ("us-gaap_NetCashProvidedByUsedInInvestingActivities",
                     "us-gaap_NetCashProvidedByUsedInInvestingActivitiesContinuingOperations")
    assert cell(inv, "2025-06-30") == -11_044_000_000
    assert cell(inv, "2026-06-30") is None
    assert cell(inv_cont, "2026-06-30") == -13_233_000_000
    assert cell(OP_DISC, "2026-06-30") == 31_000_000


@pytest.mark.fast
def test_aggregate_discontinued_cash_also_blocks_the_merge():
    agg = "us-gaap_CashProvidedByUsedInDiscontinuedOperations"
    rows = _rows([
        _stmt("2026-01-01", "2026-06-30",
              [(OP_CONT, "Net cash from operating activities, continuing", 18396),
               (agg, "Net cash from discontinued operations", 31)]),
        _stmt("2025-01-01", "2025-06-30", [(OP, "Net cash from operating activities", 18812)]),
    ])
    assert rows[OP] == {"duration_2025-01-01_2025-06-30": 18812}
    assert rows[OP_CONT] == {"duration_2026-01-01_2026-06-30": 18396}
