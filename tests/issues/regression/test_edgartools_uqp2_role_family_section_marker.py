"""A role family split when a filing spelled only some of its roles with a
leading section marker.

`_role_family_key` turns a role definition into CamelCase segments and
`_is_family_stem_of` requires a segment-aligned prefix anchored at position 0.
UNP names most of one family `DisclosureDebtDetails1` but two members of it
`DebtDetails6` and `DebtDetails2`, and names the Leases stem `Leases` while its
Tables are `DisclosureLeasesTables`. Those spellings share no leading segment, so
the members were not recognised as members: they were promoted to stems and
surfaced as spurious top-level notes ("Debt Details6", "Disclosure Leases
Tables") while the real `Disclosure Debt` note lost two of its Details.

This is the layer under GH #1218: before that work UNP produced no notes at all
through `Notes._build_from_xbrl_only`, so this was never a regression, just the
next thing in the way.

The marker is ignored only as a fallback, never stripped from the key. A filing
that names both a `Debt` family and a separate `DisclosureDebt` family must keep
them apart, which erasing the marker outright would not do.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1218
Bead: edgartools-uqp2
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.notes import Notes, _get_concept_to_notes_index
from edgar.xbrl.xbrl import _role_family_key, _role_family_stem

DATA = Path(__file__).resolve().parents[3] / "data" / "xbrl" / "datafiles"

# Pinned so a later change to the family rules cannot quietly move them.
# Counts are (notes, concepts reachable through StatementLineItem.note).
UNCHANGED_FIXTURES = {
    "gahc": (7, 92),
    "aapl": (16, 261),
    "tsla": (12, 133),
    "aeon": (12, 252),
}


def _key(name):
    return _role_family_key(name)


@pytest.fixture(scope="module")
def unp_xbrl():
    directory = DATA / "unp"
    assert directory.exists(), f"missing fixture: {directory}"
    return XBRL.from_directory(directory)


def test_unp_debt_family_absorbs_the_unprefixed_members(unp_xbrl):
    """`DebtDetails2` and `DebtDetails6` belong to `DisclosureDebt`."""
    notes = Notes.from_xbrl(unp_xbrl)

    debt = notes["Disclosure Debt"]
    assert debt is not None, "the Debt note is gone entirely"
    assert len(debt.details) == 7, (
        f"Debt should carry all 7 Details, has {len(debt.details)}"
    )


def test_unp_has_no_note_that_is_really_a_family_member(unp_xbrl):
    """A bare Tables or Details role must not surface as a top-level note when
    the filing names a stem for it."""
    titles = [note.short_name for note in Notes.from_xbrl(unp_xbrl)]

    assert "Debt Details6" not in titles
    assert "Disclosure Leases Tables" not in titles
    assert len(titles) == 18, titles


def test_unp_concept_index_grew_rather_than_shrank(unp_xbrl):
    """The absorbed Details carry data concepts, so they must now be reachable
    through the note rather than through a spurious one of their own."""
    assert len(_get_concept_to_notes_index(unp_xbrl)) == 336


@pytest.mark.parametrize("name,expected", sorted(UNCHANGED_FIXTURES.items()))
def test_other_filings_are_unchanged(name, expected):
    """The rule must not move a filing that spells its roles consistently."""
    directory = DATA / name
    assert directory.exists(), f"missing fixture: {directory}"
    xbrl = XBRL.from_directory(directory)

    expected_notes, expected_concepts = expected
    assert len(Notes.from_xbrl(xbrl)) == expected_notes
    assert len(_get_concept_to_notes_index(xbrl)) == expected_concepts


def test_two_families_differing_only_by_the_marker_stay_separate():
    """The risk the fallback creates, and why the marker is not simply stripped:
    a filing naming both `Debt` and `DisclosureDebt` must keep two families."""
    stems = [_key("Debt"), _key("DisclosureDebt")]

    assert _role_family_stem(_key("DebtDetails"), stems) == ("debt",)
    assert _role_family_stem(_key("DisclosureDebtDetails"), stems) == ("disclosure", "debt")


def test_a_stem_named_only_for_its_section_claims_nothing():
    """`Disclosure` is empty once the marker is ignored, and an empty key leads
    every other key, so it would claim every role in the filing."""
    from edgar.xbrl.xbrl import _leads_family

    assert not _leads_family(_key("Disclosure"), _key("DebtDetails"))
    assert not _leads_family(_key("Statements"), _key("DebtDetails"))


def test_the_marker_fallback_does_not_loosen_the_segment_boundary():
    """The precision the segment rule bought must survive the fallback: a short
    stem still does not claim a longer unrelated name."""
    from edgar.xbrl.xbrl import _leads_family

    assert not _leads_family(_key("Debt"), _key("DebtorNotesDetails"))
    assert not _leads_family(_key("ConvertibleNote"), _key("ConvertibleNoteholderRightsDetails"))
    # ...and a genuine member still follows.
    assert _leads_family(_key("NotesPayableRelatedParty"), _key("NotesPayableRelatedPartyDetails"))
