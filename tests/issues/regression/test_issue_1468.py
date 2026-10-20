"""Regression test for GH #1468: a co-registrant's statement showed the parent's amounts.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1468

A filing for several registrants gives each subsidiary its own statement
roles. Their presentation trees list dei:LegalEntityAxis with the domain and
one member, so the undimensioned facts -- the parent's -- filled the plain
rows, and the subsidiary's filed amounts appeared only as dimensional
children. SEC's R-file viewer renders the role the same way; the filing's
HTML shows the subsidiary alone. A subsidiary's own face statement now reads
that member's facts on its plain rows.

Ground truth, read from SEC's instance documents:

- American Airlines Group Inc. Q2 2026 10-Q (0000006201-26-000052),
  us-gaap:Assets at 2026-06-30: American Airlines, Inc. 72,888,000,000
  (context c-295, aal:AmericanAirlinesIncMember); group 64,233,000,000 (c-22).
  AssetsCurrent 24,084,000,000 and StockholdersEquity 9,024,000,000 (c-295).
- FY2025 10-K (0000006201-26-000014), 2025-12-31 / 2024-12-31: American
  Airlines, Inc. 70,247,000,000 / 68,755,000,000 (c-514 / c-515); group
  61,774,000,000 / 61,783,000,000 (c-19 / c-20).
- Duke Energy Q2 2026 10-Q (0001326160-26-000040), 2026-06-30: Duke Energy
  Carolinas 63,644,000,000 (c-126); Duke Energy 201,091,000,000 (c-30).
- NextEra Energy Q2 2026 10-Q (0000753308-26-000060), 2026-06-30: NextEra
  232,807,000,000 (c-7); Florida Power & Light 111,662,000,000 (c-8). NextEra
  files one combined balance-sheet role, which is the parent's own statement.
- Simon Property Group Q2 2026 10-Q (0001104659-26-093360) likewise files one
  combined role naming the operating partnership.
"""
from pathlib import Path

import pytest

from edgar import find
from edgar.xbrl import XBRL

AAL_FIXTURES = Path("tests/fixtures/xbrl/aal")
AAL_SUBSIDIARY_ROLE = {
    "10q_2026q2": "http://www.aa.com/role/CondensedConsolidatedBalanceSheetsAmericanAirlinesInc",
    "10k_2025": "http://www.aa.com/role/ConsolidatedBalanceSheetsAmericanAirlinesInc",
}
AAL_ASSETS = {
    "10q_2026q2": {"subsidiary": {"instant_2026-06-30": 72_888_000_000, "instant_2025-12-31": 70_247_000_000},
                   "group": {"instant_2026-06-30": 64_233_000_000, "instant_2025-12-31": 61_774_000_000}},
    "10k_2025": {"subsidiary": {"instant_2025-12-31": 70_247_000_000, "instant_2024-12-31": 68_755_000_000},
                 "group": {"instant_2025-12-31": 61_774_000_000, "instant_2024-12-31": 61_783_000_000}},
}
AAL_MEMBER = "aal_AmericanAirlinesIncMember"


def _plain(rows, concept):
    matches = [row for row in rows if row["concept"] == concept and not row.get("is_dimension")]
    assert len(matches) == 1, f"expected one plain {concept} row, got {len(matches)}"
    return matches[0]["values"]


def _members(rows, concept):
    return {meta.get("member")
            for row in rows if row["concept"] == concept and row.get("is_dimension")
            for meta in row.get("dimension_metadata", [])}


@pytest.fixture(scope="module", params=sorted(AAL_SUBSIDIARY_ROLE))
def aal(request):
    return request.param, XBRL.from_directory(AAL_FIXTURES / request.param)


@pytest.mark.fast
def test_subsidiary_role_reads_its_own_facts(aal):
    filing, xbrl = aal
    rows = xbrl.get_statement(AAL_SUBSIDIARY_ROLE[filing])

    values = _plain(rows, "us-gaap_Assets")
    for period, amount in AAL_ASSETS[filing]["subsidiary"].items():
        assert values[period] == amount
    # The member is consumed by its own statement, not repeated as a child.
    assert AAL_MEMBER not in _members(rows, "us-gaap_Assets")


@pytest.mark.fast
def test_quarterly_subsidiary_balance_sheet_totals():
    xbrl = XBRL.from_directory(AAL_FIXTURES / "10q_2026q2")
    rows = xbrl.get_statement(AAL_SUBSIDIARY_ROLE["10q_2026q2"])

    assert _plain(rows, "us-gaap_AssetsCurrent")["instant_2026-06-30"] == 24_084_000_000
    assert _plain(rows, "us-gaap_StockholdersEquity")["instant_2026-06-30"] == 9_024_000_000

    frame = xbrl.statements[AAL_SUBSIDIARY_ROLE["10q_2026q2"]].to_dataframe(standard=False)
    assets = frame.loc[frame["concept"].eq("us-gaap_Assets") & ~frame["dimension"].fillna(False)]
    assert assets["2026-06-30"].tolist() == [72_888_000_000]

    rendered = xbrl.render_statement(AAL_SUBSIDIARY_ROLE["10q_2026q2"], standard=False)
    row = next(r for r in rendered.rows if r.metadata.get("concept") == "us-gaap_Assets" and not r.is_dimension)
    assert row.cells[0].value == 72_888_000_000


@pytest.mark.fast
def test_parent_role_keeps_the_group_facts(aal):
    filing, xbrl = aal
    group_role = AAL_SUBSIDIARY_ROLE[filing].replace("AmericanAirlinesInc", "AmericanAirlinesGroupInc")

    values = _plain(xbrl.get_statement(group_role), "us-gaap_Assets")
    for period, amount in AAL_ASSETS[filing]["group"].items():
        assert values[period] == amount
    named = _plain(xbrl.get_statement("BalanceSheet"), "us-gaap_Assets")
    assert named == values


@pytest.mark.network
def test_utility_subsidiary_roles_read_their_own_facts():
    xbrl = find("0001326160-26-000040").xbrl()
    carolinas = "http://www.dukeenergy.com/role/CondensedConsolidatedBalanceSheetsDukeEnergyCarolinas"

    assert _plain(xbrl.get_statement(carolinas), "us-gaap_Assets")["instant_2026-06-30"] == 63_644_000_000
    assert _plain(xbrl.get_statement("BalanceSheet"), "us-gaap_Assets")["instant_2026-06-30"] == 201_091_000_000


@pytest.mark.network
@pytest.mark.parametrize("accession, role, member, parent_assets", [
    ("0000753308-26-000060", "http://www.nexteraenergy.com/role/CONDENSEDCONSOLIDATEDBALANCESHEETS",
     "nee_FloridaPowerLightCompanyMember", 232_807_000_000),
    ("0001104659-26-093360", "http://www.simon.com/role/StatementConsolidatedBalanceSheets",
     "spg_SimonPropertyGroupLimitedPartnershipMember", 39_709_266_000),
])
def test_combined_role_stays_the_parents_statement(accession, role, member, parent_assets):
    # One role holds the parent's facts and one subsidiary member. With no
    # separate parent role beside it, the role is the parent's own statement.
    xbrl = find(accession).xbrl()
    rows = xbrl.get_statement(role)

    assert _plain(rows, "us-gaap_Assets")["instant_2026-06-30"] == parent_assets
    assert member in _members(rows, "us-gaap_Assets")
