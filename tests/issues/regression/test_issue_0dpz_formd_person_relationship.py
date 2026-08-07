"""Regression test for edgartools-0dpz / GH #874.

Form D `Person` (related persons) dropped the related-person relationship
(`<relatedPersonRelationshipList>`) and the optional `<relationshipClarification>`.
The relationship is the analytically meaningful part — without it you only get a
list of names and cannot tell officers/directors from promoters.

https://github.com/dgunning/edgartools/issues/874
"""
from pathlib import Path

import pytest

from edgar import Filing
from edgar.offerings import FormD

DATA = Path(__file__).resolve().parents[2].parent / "data"


def _load(name: str) -> FormD:
    return FormD.from_xml((DATA / name).read_text())


def test_person_exposes_relationships():
    """A single-relationship related person surfaces its relationship list."""
    offering = _load("D.1685REIT.xml")
    daniel = offering.related_persons[0]
    assert daniel.first_name == "Daniel"
    assert daniel.last_name == "Belldegrun"
    assert daniel.relationships == ["Executive Officer"]
    assert daniel.relationship_clarification is None


def test_person_exposes_multiple_relationships():
    """A person who is both Executive Officer and Director keeps both, in order."""
    offering = _load("D.1685REIT.xml")
    # Joshua Bradley is the third related person — Executive Officer + Director.
    josh = offering.related_persons[2]
    assert josh.first_name == "Joshua"
    assert josh.relationships == ["Executive Officer", "Director"]


def test_person_exposes_relationship_clarification():
    """The optional free-text clarification is surfaced when present."""
    offering = _load("D.Shepards.xml")
    daniel = offering.related_persons[0]
    assert daniel.first_name == "Daniel"
    assert daniel.last_name == "Wallach"
    assert daniel.relationships == ["Executive Officer", "Director"]
    assert daniel.relationship_clarification == (
        "Chief Executive Officer and Member of the Board of Managers"
    )


def test_promoter_director_clarification():
    """Directors with clarifications parse cleanly (no relationship dropped)."""
    offering = _load("D.APFund.xml")
    people = offering.related_persons
    assert all(p.relationships for p in people)  # none dropped
    assert people[0].relationships == ["Director"]
    assert people[0].relationship_clarification == "Manager of the general partner of the Issuer"


@pytest.mark.network
def test_msft_satya_nadella_ground_truth():
    """Ground truth (GH #874): MSFT Form D 0001137638-20-000002.

    Satya Nadella is both an Executive Officer and a Director.
    """
    filing = Filing(
        form="D", filing_date="2020-01-02", company="MICROSOFT CORP",
        cik=789019, accession_no="0001137638-20-000002",
    )
    satya = filing.obj().related_persons[0]
    assert satya.first_name == "Satya"
    assert satya.last_name == "Nadella"
    assert satya.relationships == ["Executive Officer", "Director"]
