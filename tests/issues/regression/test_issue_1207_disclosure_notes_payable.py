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

from edgar.xbrl.xbrl import XBRL

DATA = Path(__file__).resolve().parents[3] / "data" / "xbrl" / "datafiles"

# `_declares_disclosure` and `_names_notes_section` are imported inside the
# tests that use them, not here. They only exist on a tree carrying the fix, and
# a module-level import would turn this file into a collection error when it is
# run against an unfixed tree - which is exactly when someone wants to watch it
# fail. Kept lazy so that run reports test failures instead.


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
    from edgar.xbrl.xbrl import _declares_disclosure, _names_notes_section

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
    from edgar.xbrl.xbrl import _names_notes_section

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
    from edgar.xbrl.xbrl import _names_notes_section

    assert _names_notes_section(definition.lower())


@pytest.mark.parametrize("definition,concept", [
    # No category marker and no disclosure concept: nothing states otherwise,
    # so the legacy keyword result stands.
    ("PromissoryNotesPayable", "us-gaap_OtherLiabilitiesCurrentAbstract"),
    ("0011 - Statement - NOTES PAYABLE", "us-gaap_DebtInstrumentsAbstract"),
])
def test_roles_that_do_not_declare_a_disclosure_are_left_alone(definition, concept):
    from edgar.xbrl.xbrl import _declares_disclosure

    assert not _declares_disclosure(definition.lower(), concept)


# --- end to end, on filings committed to the repository ---------------------

def test_gahc_notes_payable_roles_are_disclosures():
    """Global Arena Holding 10-Q: the debt roles hang from
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


# --- issue #1218: a role family classifies as a unit -------------------------
#
# gahc falls back to role names.  Only the family stem hangs from
# us-gaap_DebtDisclosureAbstract; its Tables and ScheduleOf...Details children
# hang from a debt-balance abstract and two of them spell the stem in the
# singular, so neither signal in `_declares_disclosure` reaches them.

GAHC_CONVERTIBLE_FAMILY = [
    "ConvertiblePromissoryNotesPayable",
    "ConvertiblePromissoryNotesPayableTables",
    "ConvertiblePromissoryNotePayableScheduleOfConvertiblePromissoryNotesPayableDetails",
    "ConvertiblePromissoryNotePayableScheduleOfConvertiblePromissoryNotesPayableDetailsParenthetical",
    "ConvertiblePromissoryNotesPayableScheduleOfRollfowardOfConvertiblePromissoryNotesPayableDetails",
]


def _stems(**declares_by_definition):
    """Family key of each stem role -> declares-a-disclosure, as the pre-pass
    builds it.  Tables and Details roles are not stems and are left out."""
    from edgar.xbrl.xbrl import _ROLE_FAMILY_SUFFIX_RE, _role_family_key
    return {_role_family_key(d): declares for d, declares in declares_by_definition.items()
            if not _ROLE_FAMILY_SUFFIX_RE.search(d.lower())}


def _follows(definition, stems):
    from edgar.xbrl.xbrl import _follows_disclosure_family, _role_family_key
    return _follows_disclosure_family(definition.lower(), _role_family_key(definition), stems)


@pytest.mark.parametrize("definition", GAHC_CONVERTIBLE_FAMILY[1:])
def test_family_children_follow_a_stem_that_declares_a_disclosure(definition):
    stems = _stems(ConvertiblePromissoryNotesPayable=True,
                   **{d: False for d in GAHC_CONVERTIBLE_FAMILY[1:]})
    assert _follows(definition, stems)


def test_children_are_not_stems():
    """`...DetailsParenthetical` extends `...Details`, which does not declare
    a disclosure; it must reach the family stem, not stop at its sibling."""
    parenthetical, details = GAHC_CONVERTIBLE_FAMILY[3], GAHC_CONVERTIBLE_FAMILY[2]
    assert parenthetical.startswith(details)
    stems = _stems(ConvertiblePromissoryNotesPayable=True, **{details: False})
    assert len(stems) == 1  # the Details role was left out
    assert _follows(parenthetical, stems)


@pytest.mark.parametrize("definition", [
    "PromissoryNotesPayable",                 # a stem, not a child
    "OtherNotesReceivableTables",             # a child of some other family
    "ConvertiblePromissoryNotesPayableNarrative",  # no family suffix
])
def test_roles_outside_the_family_do_not_follow_it(definition):
    stems = _stems(ConvertiblePromissoryNotesPayable=True)
    assert not _follows(definition, stems)


def test_child_follows_its_nearest_stem_not_a_shorter_disclosure_stem():
    """`NotesPayable` declares a disclosure and `NotesPayableRelatedParty` does
    not.  The related-party Details belong to the longer stem and stay with
    it, while the plain Details still follow `NotesPayable`."""
    stems = _stems(NotesPayable=True, NotesPayableRelatedParty=False)
    assert _follows("NotesPayableDetails", stems)
    assert not _follows("NotesPayableRelatedPartyDetails", stems)
    # The sibling stem is not a child of `NotesPayable`, whatever prefixes it.
    assert not _follows("NotesPayableRelatedParty", stems)


def test_gahc_convertible_note_family_classifies_as_a_unit():
    """Global Arena Holding 10-Q: the whole family is returned by
    disclosures() and none of it by notes()."""
    directory = DATA / "gahc"
    assert directory.exists(), f"missing fixture: {directory}"
    xbrl = XBRL.from_directory(directory)

    by_definition = {s["definition"]: s for s in xbrl.get_all_statements()}
    family = [by_definition[d] for d in GAHC_CONVERTIBLE_FAMILY]
    assert [s["category"] for s in family] == ["disclosure"] * 5
    assert [s["type"] for s in family] == ["Disclosures"] * 5

    note_roles = {s.role_or_type for s in xbrl.notes()}
    disclosure_roles = {s.role_or_type for s in xbrl.disclosures()}
    family_roles = {s["role"] for s in family}
    assert family_roles <= disclosure_roles
    assert not family_roles & note_roles

    # The only note-bearing roles left as notes are accounting-policy roles,
    # which never entered the ambiguous branch.
    assert {s["type"] for s in xbrl.get_all_statements()
            if s["category"] == "note"} == {"AccountingPolicies"}


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
