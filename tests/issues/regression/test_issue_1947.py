"""Regression test for GH #1947: a detail role filed under the wrong menu category.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1947

SEC's renderer files a role under Details mostly from its title. In Costco's
FY2021 10-K (0000909832-21-000014) the lease detail roles carry no "(Details)"
suffix, and FilingSummary.xml puts them under Notes, Cover and Uncategorized.
edgartools took that menu as authoritative, so the year looked different from
every later one:

- ``xbrl.notes()`` returned "Leases, Supplemental Cash Flow Information" and
  "Leases, Future Minimum Payments" as notes of their own;
- "Leases, Components of Lease Expense" was typed ``CoverPage``;
- ``tenk.notes["Leases"].details`` was empty (FY2022 onward it has four).

A role whose concepts include line items but no text block is not a note, and
one without a single dei concept is not a cover page. Those roles are now
treated as Details, so the 2021 note has the same shape as later years.

The fixture under tests/fixtures/xbrl/cost/10k_2021 holds the filing's own XBRL
files and FilingSummary.xml, verbatim (see its README).
"""

from types import SimpleNamespace

import pytest

from edgar.sgml.filing_summary import FilingSummary
from edgar.xbrl.notes import Notes
from edgar.xbrl.xbrl import XBRL, _effective_menu_category
from tests.paths import FIXTURES_DIR

FIXTURE = FIXTURES_DIR / "xbrl" / "cost" / "10k_2021"

LEASE_DETAIL_ROLES = [
    "LeasesSupplementalBalanceSheetInformation",   # SEC menu: Uncategorized
    "LeasesComponentsofLeaseExpense",              # SEC menu: Cover
    "LeasesSupplementalCashFlowInformation",       # SEC menu: Notes
    "LeasesFutureMinimumPayments",                 # SEC menu: Notes
]


@pytest.fixture(scope="module")
def cost_2021():
    xbrl = XBRL.from_directory(FIXTURE)
    filing_summary = FilingSummary.parse((FIXTURE / "FilingSummary.xml").read_text())
    xbrl._apply_filing_summary(filing_summary)
    return xbrl, Notes.from_xbrl(xbrl, filing_summary=filing_summary)


def _role_name(statement):
    return statement.role_or_type.split("/")[-1]


def test_sec_menu_is_kept_as_filed():
    """The FilingSummary object still says what SEC wrote; only edgartools' reading changes."""
    filing_summary = FilingSummary.parse((FIXTURE / "FilingSummary.xml").read_text())
    menu = {report.short_name: report.menu_category for report in filing_summary.reports}
    assert menu["Leases, Components of Lease Expense"] == "Cover"
    assert menu["Leases, Future Minimum Payments"] == "Notes"
    assert menu["Leases, Supplemental Balance Sheet Information"] == "Uncategorized"


def test_leases_note_owns_its_detail_tables(cost_2021):
    _, notes = cost_2021
    assert [_role_name(detail) for detail in notes["Leases"].details] == LEASE_DETAIL_ROLES


def test_detail_roles_are_not_notes(cost_2021):
    xbrl, notes = cost_2021
    assert [note.title for note in notes if "lease" in note.title.lower()] == ["Leases"]
    assert [_role_name(note) for note in xbrl.notes() if "Lease" in note.role_or_type] == ["Leases", "LeasesTables"]
    assert len(notes) == 12


def test_detail_roles_are_disclosures_not_cover_pages(cost_2021):
    xbrl, _ = cost_2021
    types = {s["role"].split("/")[-1]: (s["type"], s["category"]) for s in xbrl.get_all_statements()}
    for role in LEASE_DETAIL_ROLES:
        assert types[role] == ("Disclosures", "disclosure"), role
    # The real cover page, which holds the dei facts, is untouched.
    assert types["Cover"][0] == "CoverPage"
    assert xbrl.statements.cover_page().role_or_type == "http://www.costco.com/role/Cover"


def test_components_of_lease_expense_values(cost_2021):
    """Ground truth: Note 6 of the FY2021 10-K, operating lease costs $296M and $252M."""
    _, notes = cost_2021
    detail = next(d for d in notes["Leases"].details if _role_name(d) == "LeasesComponentsofLeaseExpense")
    df = detail.to_dataframe().set_index("concept")
    assert df.loc["us-gaap_OperatingLeaseCost", "2021-08-29 (FY)"] == 296_000_000
    assert df.loc["us-gaap_OperatingLeaseCost", "2020-08-30 (FY)"] == 252_000_000
    assert df.loc["us-gaap_LeaseCost", "2021-08-29 (FY)"] == 534_000_000


def test_text_block_notes_keep_their_category(cost_2021):
    """A note whose role is a text block stays a note however few concepts it has."""
    xbrl, _ = cost_2021
    types = {s["role"].split("/")[-1]: s["type"] for s in xbrl.get_all_statements()}
    assert types["Leases"] == "Notes"
    assert types["Debt"] == "Notes"
    assert types["SegmentReporting"] == "Notes"


# --- the shapes a first version of the rule got wrong ---------------------------
#
# Measured over 111 10-Ks from 37 filers (2020-2022), a rule that read only
# "line items and no ...TextBlock concept" moved 74 roles, and 70 of them were
# not details. These are the three shapes, as SEC filed them.

TYPES = {
    "us-gaap_Revenues": "xbrli:monetaryItemType",
    "us-gaap_NatureOfOperations": "dtr-types:textBlockItemType",
    "dei_AuditorName": "xbrli:normalizedStringItemType",
    "dei_AuditorLocation": "xbrli:normalizedStringItemType",
    "dei_AuditorFirmId": "nonnum:nonemptySequenceNumberItemType",
    "us-gaap_OperatingLeaseCost": "xbrli:monetaryItemType",
}


def _tree(definition, *element_ids):
    nodes = {eid: SimpleNamespace(is_abstract=eid.endswith("Abstract")) for eid in element_ids}
    return SimpleNamespace(definition=definition, all_nodes=nodes)


@pytest.mark.parametrize("menu,tree", [
    # JPM FY2020: the income statement filed under Uncategorized.
    ("Uncategorized", _tree("100010003 - Statement - Consolidated Statements of Income",
                            "us-gaap_IncomeStatementAbstract", "us-gaap_Revenues")),
    # HD FY2020: a balance sheet parenthetical filed under Cover.
    ("Cover", _tree("1002004 - Statement - Consolidated Balance Sheets (Parenthetical)",
                    "us-gaap_StatementOfFinancialPositionAbstract", "us-gaap_Revenues")),
    # 25 filers: Audit Information filed under Notes.
    ("Notes", _tree("0002002 - Document - Audit Information",
                    "dei_CoverAbstract", "dei_AuditorName", "dei_AuditorLocation", "dei_AuditorFirmId")),
    # CL and MRK: a note whose text block is not named ...TextBlock.
    ("Notes", _tree("2101101 - Disclosure - Nature of Operations",
                    "us-gaap_OrganizationConsolidationAndPresentationOfFinancialStatementsAbstract",
                    "us-gaap_NatureOfOperations")),
], ids=["statement-uncategorized", "parenthetical-cover", "audit-information", "nature-of-operations"])
def test_non_detail_roles_keep_sec_category(menu, tree):
    assert _effective_menu_category(menu, tree, TYPES.get) == menu


def test_disclosure_role_with_value_items_and_no_text_block_is_a_detail():
    tree = _tree("2425412 - Disclosure - Leases, Components of Lease Expense",
                 "us-gaap_LeaseCostAbstract", "us-gaap_OperatingLeaseCost")
    assert _effective_menu_category("Cover", tree, TYPES.get) == "Details"


def test_trusted_categories_are_never_reconsidered():
    tree = _tree("2425412 - Disclosure - Leases, Components of Lease Expense", "us-gaap_OperatingLeaseCost")
    for menu in ("Statements", "Tables", "Policies", "Details"):
        assert _effective_menu_category(menu, tree, TYPES.get) == menu
