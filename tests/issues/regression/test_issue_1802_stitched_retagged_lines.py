"""A line the company retagged between filings stitched as two half-empty rows.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1802

Sprouts tagged cash-flow net income as ``ProfitLoss`` through FY2023 and as
``NetIncomeLoss`` from FY2024, and moved its operating-lease lines from ``sfm:``
extensions to ``us-gaap`` concepts in FY2022. Neither pair is a name variant or
shares a standard concept, so the stitcher kept each line as two rows, one
filled for the new years and one for the old.

A pair now merges when the rows carry the same label, have no stitched period in
common, and some filing reports both concepts for a common period with agreeing,
nonzero amounts. A filer that presents both lines in one statement fills both in
the same periods, so its rows stay separate.

Ground truth, read from the filings' XBRL: SFM 10-K 0000950170-22-001976
(FY2021) tags ``sfm:OperatingLeaseRightOfUseAssetAmortization`` 108,517,000 for
the year ending 2022-01-02; SFM 10-K 0000950170-23-005723 (FY2022) tags
``us-gaap:OperatingLeaseRightOfUseAssetAmortizationExpense`` 117,315,000 for the
year ending 2023-01-01 and 108,517,000 for its 2022-01-02 comparative.
"""
import pytest

from edgar import find
from edgar.xbrl.stitching import XBRLS
from edgar.xbrl.stitching.core import StatementStitcher

FY2024 = "duration_2024-01-01_2024-12-29"
FY2023 = "duration_2023-01-02_2023-12-31"


def _stmt(pid, rows):
    return {"statement_type": "CashFlowStatement",
            "periods": {pid: {"label": pid}},
            "data": [{"concept": c, "label": label, "level": 1, "is_abstract": False,
                      "is_total": False, "values": dict(values), "decimals": {p: 0 for p in values}}
                     for c, label, values in rows]}


def _rows(statements):
    out = StatementStitcher().stitch_statements(statements)
    return {r["concept"]: r["values"] for r in out["statement_data"]}


@pytest.mark.fast
def test_retagged_line_merges_on_an_agreeing_comparative():
    rows = _rows([
        _stmt(FY2024, [("us-gaap_NetIncomeLoss", "Net income", {FY2024: 380, FY2023: 259})]),
        _stmt(FY2023, [("us-gaap_ProfitLoss", "Net income", {FY2023: 259})]),
    ])
    assert rows == {"us-gaap_NetIncomeLoss": {FY2024: 380, FY2023: 259}}


@pytest.mark.fast
def test_both_lines_in_one_statement_stay_separate():
    # A filer with a non-controlling interest presents both, sometimes equal.
    rows = _rows([
        _stmt(FY2024, [("us-gaap_ProfitLoss", "Net income", {FY2024: 100, FY2023: 90}),
                       ("us-gaap_NetIncomeLoss", "Net income", {FY2024: 100, FY2023: 90})]),
        _stmt(FY2023, [("us-gaap_ProfitLoss", "Net income", {FY2023: 90}),
                       ("us-gaap_NetIncomeLoss", "Net income", {FY2023: 90})]),
    ])
    assert set(rows) == {"us-gaap_ProfitLoss", "us-gaap_NetIncomeLoss"}


@pytest.mark.fast
def test_same_label_without_evidence_stays_separate():
    rows = _rows([
        _stmt(FY2024, [("us-gaap_PaymentsForProceedsFromOtherInvestingActivities", "Other", {FY2024: 5})]),
        _stmt(FY2023, [("us-gaap_ProceedsFromPaymentsForOtherFinancingActivities", "Other", {FY2023: 7})]),
    ])
    assert len(rows) == 2


@pytest.mark.fast
def test_a_shared_zero_is_not_evidence():
    rows = _rows([
        _stmt(FY2024, [("us-gaap_PaymentsForProceedsFromOtherInvestingActivities", "Other", {FY2024: 5, FY2023: 0})]),
        _stmt(FY2023, [("us-gaap_ProceedsFromPaymentsForOtherFinancingActivities", "Other", {FY2023: 0})]),
    ])
    assert len(rows) == 2


@pytest.mark.fast
def test_a_restated_comparative_keeps_two_rows():
    rows = _rows([
        _stmt(FY2024, [("us-gaap_NetIncomeLoss", "Net income", {FY2024: 380, FY2023: 250})]),
        _stmt(FY2023, [("us-gaap_ProfitLoss", "Net income", {FY2023: 259})]),
    ])
    assert len(rows) == 2


@pytest.mark.vcr
def test_sfm_operating_lease_amortization_is_one_row():
    xbrls = XBRLS.from_filings([find("0000950170-23-005723"), find("0000950170-22-001976")])
    df = xbrls.statements.cash_flow_statement().to_dataframe()

    rows = df[df["label"] == "Operating lease asset amortization"]
    assert len(rows) == 1
    assert rows["2023-01-01"].iloc[0] == 117315000
    assert rows["2022-01-02"].iloc[0] == 108517000
