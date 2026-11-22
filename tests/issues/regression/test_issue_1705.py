"""Regression test for GH #1705: to_dataframe() gave every row of a concept its first parent.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1705

A concept can be presented under two parents in one role, for example net income
on the face of a combined income and comprehensive income statement and again
at the top of the comprehensive income section. ``get_raw_data()`` keeps each
occurrence's own parent, but ``Statement._add_metadata_columns()`` looked the
parent up by concept from its first occurrence, so both rows reported the first
parent. Each row now takes its own presentation parent, and a dimensional row
takes the parent of the line it breaks down.

Ground truth: Cato Corp 10-K for fiscal 2023 (0001562762-24-000065).
cato-20240203_pre.xml presents us-gaap_NetIncomeLoss from
us-gaap_IncomeStatementAbstract and from
us-gaap_OtherComprehensiveIncomeLossNetOfTaxPeriodIncreaseDecreaseAbstract; net
loss for the year ended 2024-02-03 is (23,941) thousand. Netflix 10-Q for
2024-09-30 (0001065280-24-000287) presents NetIncomeLoss under
EarningsPerShareBasicAbstract and EarningsPerShareDilutedAbstract in its EPS
details; net income for the quarter is 2,363,509 thousand.
"""
from pathlib import Path

import pytest

from edgar import find
from edgar.xbrl import XBRL

CATO_10K = Path("tests/fixtures/xbrl/cato/10k_2023")
NFLX_10Q = Path("tests/fixtures/xbrl/nflx/10q_2024")


def _rows(df, concept):
    return df[df["concept"] == concept]


@pytest.mark.fast
def test_cato_net_income_keeps_each_presentation_parent():
    df = XBRL.from_directory(CATO_10K).statements.income_statement().to_dataframe()
    rows = _rows(df, "us-gaap_NetIncomeLoss")
    lines = rows[~rows["dimension"].astype(bool)]

    assert list(lines["2024-02-03 (FY)"]) == [-23941000.0, -23941000.0]
    assert list(lines["parent_abstract_concept"]) == [
        "us-gaap_IncomeStatementAbstract",
        "us-gaap_OtherComprehensiveIncomeLossNetOfTaxPeriodIncreaseDecreaseAbstract",
    ]

    # Each equity-component member row follows the line it breaks down.
    first, second = lines.index
    after_second = rows.loc[rows.index > second]
    between = rows.loc[(rows.index > first) & (rows.index < second)]
    assert len(between) == 4 and len(after_second) == 4
    assert set(between["parent_abstract_concept"]) == {"us-gaap_IncomeStatementAbstract"}
    assert set(after_second["parent_abstract_concept"]) == {
        "us-gaap_OtherComprehensiveIncomeLossNetOfTaxPeriodIncreaseDecreaseAbstract"
    }


@pytest.mark.fast
def test_nflx_eps_details_basic_and_diluted_parents():
    xbrl = XBRL.from_directory(NFLX_10Q)
    role = next(s["role"] for s in xbrl.get_all_statements()
                if s["role"].endswith("EarningsPerShareCalculationofEPSDetails"))
    df = xbrl.statements[role].to_dataframe()
    lines = _rows(df, "us-gaap_NetIncomeLoss")
    lines = lines[~lines["dimension"].astype(bool)]

    assert list(lines["2024-09-30 (Q3)"]) == [2363509000.0, 2363509000.0]
    assert list(lines["parent_abstract_concept"]) == [
        "us-gaap_EarningsPerShareBasicAbstract",
        "us-gaap_EarningsPerShareDilutedAbstract",
    ]


@pytest.mark.fast
def test_parent_column_matches_raw_rows_for_non_dimensional_rows():
    """Every non-dimensional row's parent is the parent its raw row carries."""
    statement = XBRL.from_directory(CATO_10K).statements.income_statement()
    df = statement.to_dataframe()
    raw_parents = [item.get("parent") for item in statement.get_raw_data()
                   if item.get("concept") in set(df["concept"]) and not item.get("is_dimension")
                   and not item.get("is_abstract")]
    df_parents = list(df.loc[~df["dimension"].astype(bool) & ~df["abstract"].astype(bool),
                             "parent_abstract_concept"])
    assert df_parents == raw_parents


@pytest.mark.network
def test_snps_issue_example():
    """The issue's reproduction: Synopsys 10-Q for 2026-07-31 (0000883241-26-000025)."""
    df = find("0000883241-26-000025").xbrl().statements.income_statement().to_dataframe()
    rows = _rows(df, "us-gaap_NetIncomeLoss")
    assert list(rows["parent_abstract_concept"]) == [
        "us-gaap_StatementLineItems",
        "us-gaap_StatementLineItems",
        "us-gaap_IncomeAmountsAttributableToReportingEntityDisclosuresAbstract",
        "us-gaap_IncomeAmountsAttributableToReportingEntityDisclosuresAbstract",
    ]
