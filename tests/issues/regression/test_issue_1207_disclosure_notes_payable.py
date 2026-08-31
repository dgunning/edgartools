"""Regression test for issue #1207.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1207

`get_all_statements()` falls back to keyword matching when a role carries no
`FilingSummary` menu category, and that fallback tested the bare substring
`"note"` before it tested `"disclosure"`.  "Note" names a financial-statement
section and a debt instrument, so every role like
`"0021 - Disclosure - NOTES PAYABLE AND OTHER BORROWINGS"` was claimed by the
first branch: reported as `type="Notes"` / `category="note"`, returned by
`xbrl.notes()`, and absent from `xbrl.disclosures()`.

The fix keeps the keyword order but stops the ambiguous word from outranking a
role that states what it is - by its `Disclosure` category marker, or by the
concept it hangs from (`us-gaap_DebtDisclosureAbstract`) - unless the
definition names the notes section itself.

Roles whose definition does not contain "note" are classified exactly as
before.
"""

from pathlib import Path

import pytest

from edgar.xbrl.xbrl import XBRL, _declares_disclosure, _names_notes_section

DATA = Path(__file__).resolve().parents[3] / "data" / "xbrl" / "datafiles"


# --- the bug: "notes payable" is a disclosure subject, not a notes section ---

# The four Oracle 10-Q roles from the report (accession 0000950170-23-047713).
ORACLE_ROLES = [
    ("0000021 - Disclosure - NOTES PAYABLE AND OTHER BORROWINGS",
     "us-gaap_DebtDisclosureAbstract"),
    ("0000022 - Disclosure - NOTES PAYABLE AND OTHER BORROWINGS (Tables)",
     "us-gaap_DebtInstrumentsAbstract"),
    ("0000023 - Disclosure - NOTES PAYABLE AND OTHER BORROWINGS (Details)",
     "us-gaap_DebtInstrumentsAbstract"),
    ("0000024 - Disclosure - NOTES PAYABLE AND OTHER BORROWINGS (Narrative) (Details)",
     "us-gaap_DebtDisclosureAbstract"),
]


@pytest.mark.parametrize("definition,concept", ORACLE_ROLES)
def test_notes_payable_disclosure_roles_declare_themselves_disclosures(definition, concept):
    role_def = definition.lower()
    assert _declares_disclosure(role_def, concept)
    assert not _names_notes_section(role_def)


@pytest.mark.parametrize("definition", [
    "0011 - Disclosure - PROMISSORY NOTES PAYABLE",
    "0012 - Disclosure - CONVERTIBLE PROMISSORY NOTES PAYABLE (Tables)",
    "Disclosure - Notes Receivable, Net",
    "Disclosure - Senior Notes",
    "DisclosureConvertibleNotesPayable",
])
def test_note_bearing_disclosure_titles_are_not_notes_sections(definition):
    assert not _names_notes_section(definition.lower())


# --- what must keep working: real notes to the financial statements ----------

@pytest.mark.parametrize("definition", [
    "0007 - Disclosure - Notes to Consolidated Financial Statements",
    "0007 - Disclosure - Notes to the Unaudited Condensed Consolidated Financial Statements",
    "NotesToFinancialStatements",
    "0008 - Disclosure - Note 1 - Organization and Basis of Presentation",
    "DisclosureNote1OrganizationAndBasisOfPresentation",
    "0009 - Disclosure - Notes",
    "0010 - Disclosure - Footnotes",
])
def test_notes_sections_are_still_recognised(definition):
    assert _names_notes_section(definition.lower())


@pytest.mark.parametrize("definition,concept", [
    # No category marker and no disclosure concept: nothing states otherwise,
    # so the legacy keyword result stands.
    ("PromissoryNotesPayable", "us-gaap_OtherLiabilitiesCurrentAbstract"),
    ("0011 - Statement - NOTES PAYABLE", "us-gaap_DebtInstrumentsAbstract"),
])
def test_roles_that_do_not_declare_a_disclosure_are_left_alone(definition, concept):
    assert not _declares_disclosure(definition.lower(), concept)


# --- end to end, on filings committed to the repository ---------------------

def test_gahc_notes_payable_roles_are_disclosures():
    """Great American Holding 10-Q: the debt roles hang from
    us-gaap_DebtDisclosureAbstract and were reported as Notes."""
    directory = DATA / "gahc"
    assert directory.exists(), f"missing fixture: {directory}"
    xbrl = XBRL.from_directory(directory)

    by_definition = {s["definition"]: s for s in xbrl.get_all_statements()}
    for definition in ("PromissoryNotesPayable",
                       "PromissoryNotesPayableNarrativeDetails",
                       "ConvertiblePromissoryNotesPayable"):
        statement = by_definition[definition]
        assert statement["primary_concept"] == "us-gaap_DebtDisclosureAbstract"
        assert statement["category"] == "disclosure"
        assert statement["type"] == "Disclosures"

    note_roles = {s.role_or_type for s in xbrl.notes()}
    disclosure_roles = {s.role_or_type for s in xbrl.disclosures()}
    target = {by_definition["PromissoryNotesPayable"]["role"]}
    assert target <= disclosure_roles
    assert not target & note_roles


def test_aeon_convertible_note_roles_are_disclosures():
    """AEON Biopharma 10-Q: the role names lead with the Disclosure marker."""
    directory = DATA / "aeon"
    assert directory.exists(), f"missing fixture: {directory}"
    xbrl = XBRL.from_directory(directory)

    convertible = [s for s in xbrl.get_all_statements()
                   if "ConvertibleNote" in s["definition"]]
    assert convertible, "fixture no longer contains convertible-note roles"
    assert {s["category"] for s in convertible} == {"disclosure"}


def test_aapl_classification_is_unchanged():
    """No Apple role definition contains "note", so none of them may move."""
    directory = DATA / "aapl"
    assert directory.exists(), f"missing fixture: {directory}"
    xbrl = XBRL.from_directory(directory)

    statements = xbrl.get_all_statements()
    assert not [s for s in statements if "note" in s["definition"].lower()]
    assert {s["definition"] for s in statements if s["category"] == "note"} == set()
