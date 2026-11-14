"""Regression test for GH #1970: MTD's FY2021-2023 balance sheet came back empty in 6.1.0.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1970

Mettler-Toledo's 10-Ks for FY2021-2023 file a role "Statement of Financial
Position, Classified" whose root is ``StatementOfFinancialPositionAbstract`` and
whose only content is the Schedule II valuation text block. Issue #659 added
essential-concept validation to reject exactly this role. GH #1843 (6.1.0) then
accepted a declared statement of the requested type when no candidate in the same
cascade step validated, so the stub was returned at the primary-concept step,
before the role-pattern step reached "Consolidated Balance Sheets": one row, no
values. The declared-primary fallback is now held while later steps run, and a
later validated candidate that is itself a declared statement replaces it.

Ground truth, from each filing's R5.htm "Consolidated Balance Sheets" ($ in thousands):
- 10-K FY2022, 0001037646-23-000005: total assets 3,492,395 (2022) and 3,326,798 (2021)
- 10-K FY2021, 0001037646-22-000008: total assets 3,326,798 (2021) and 2,814,549 (2020)
- 10-K FY2023, 0001037646-24-000007: total assets 3,355,555 (2023) and 3,492,395 (2022)
"""
from types import SimpleNamespace

import pytest

from edgar import find
from edgar.xbrl.statement_resolver import StatementResolver

FACE = "http://www.mt.com/role/ConsolidatedBalanceSheets"
STUB = "http://www.mt.com/role/StatementofFinancialPositionClassified"


def _stub_xbrl():
    face = {"role": FACE, "type": None, "menu_category": "Statements",
            "definition": "0000005 - Statement - Consolidated Balance Sheets",
            "role_name": "ConsolidatedBalanceSheets", "primary_concept": "us-gaap_StatementTable"}
    stub = {"role": STUB, "type": "BalanceSheet", "menu_category": "Statements",
            "definition": "0000009 - Statement - Statement of Financial Position, Classified",
            "role_name": "StatementofFinancialPositionClassified",
            "primary_concept": "us-gaap_StatementOfFinancialPositionAbstract"}
    nodes = {
        FACE: ["us-gaap_StatementTable", "us-gaap_StatementLineItems", "us-gaap_AssetsCurrent",
               "us-gaap_Assets", "us-gaap_Liabilities", "us-gaap_StockholdersEquity",
               "us-gaap_LiabilitiesAndStockholdersEquity"],
        STUB: ["us-gaap_StatementOfFinancialPositionAbstract",
               "srt_ScheduleOfValuationAndQualifyingAccountsDisclosureTextBlock"],
    }
    trees = {role: SimpleNamespace(all_nodes=dict.fromkeys(n)) for role, n in nodes.items()}
    return SimpleNamespace(get_all_statements=lambda: [face, stub], presentation_trees=trees)


@pytest.mark.fast
def test_declared_stub_does_not_beat_a_later_validated_statement():
    _, role, canonical, _ = StatementResolver(_stub_xbrl()).find_statement("BalanceSheet")
    assert role == FACE  # was STUB
    assert canonical == "BalanceSheet"


def _total_assets(accession):
    df = find(accession).xbrl().statements.balance_sheet().to_dataframe()
    row = df[(df["concept"] == "us-gaap_Assets") & (df["dimension"] != True)]  # noqa: E712
    assert len(row) == 1, f"{len(df)} rows, concepts {list(df['concept'])[:5]}"
    return row.iloc[0], len(df)


@pytest.mark.network
@pytest.mark.parametrize("accession, current, prior, values", [
    ("0001037646-23-000005", "2022-12-31", "2021-12-31", (3_492_395_000, 3_326_798_000)),
    ("0001037646-22-000008", "2021-12-31", "2020-12-31", (3_326_798_000, 2_814_549_000)),
    ("0001037646-24-000007", "2023-12-31", "2022-12-31", (3_355_555_000, 3_492_395_000)),
])
def test_mtd_balance_sheet_has_its_totals(accession, current, prior, values):
    assets, rows = _total_assets(accession)
    assert (assets[current], assets[prior]) == values
    assert rows > 30  # was 1: the Schedule II text block
