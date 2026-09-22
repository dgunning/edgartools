"""Direct coverage of `edgar/_party.py`, the shared party/address value layer.

`_party` is imported by 18 modules — Form D, Form 144, Form 3/4/5 ownership, 13F,
Schedule 13D/G, Form C, muni advisors, EFFECT, SGML headers, `_filings` — but until
now it was only ever exercised *indirectly*, through `FormD.from_xml`. Bead
edgartools-07lk.11.1 asks for direct coverage before the bs4 to lxml port
(edgartools-07lk.11.2) touches the one bs4 surface it has: `Issuer.from_xml`.

The port's failure mode is silence: helpers return `None` instead of values, and these
constructors build objects full of empty fields rather than raising. The assertions
below are on values, so that silence shows up as a failure.

See tests/test_xmltools_semantics.py for the helper-level contract.
"""
from bs4 import BeautifulSoup

from edgar._party import (
    Address,
    Contact,
    Filer,
    Issuer,
    Name,
    Person,
    get_addresses_as_columns,
)

# The <primaryIssuer> block from data/D.1685REIT.xml, trimmed to the parsed fields.
ISSUER_XML = """<?xml version="1.0"?>
<primaryIssuer>
    <cik>0001961089</cik>
    <entityName>1685 38th REIT, L.L.C.</entityName>
    <issuerAddress>
        <street1>2029 CENTURY PARK EAST</street1>
        <street2>SUITE 1370</street2>
        <city>LOS ANGELES</city>
        <stateOrCountry>CA</stateOrCountry>
        <stateOrCountryDescription>CALIFORNIA</stateOrCountryDescription>
        <zipCode>90067</zipCode>
    </issuerAddress>
    <issuerPhoneNumber>424-313-1550</issuerPhoneNumber>
    <jurisdictionOfInc>DELAWARE</jurisdictionOfInc>
    <issuerPreviousNameList>
        <value>None</value>
    </issuerPreviousNameList>
    <edgarPreviousNameList>
        <value>None</value>
    </edgarPreviousNameList>
    <entityType>Limited Liability Company</entityType>
    <yearOfInc>
        <withinFiveYears>true</withinFiveYears>
        <value>2022</value>
    </yearOfInc>
</primaryIssuer>
"""


def _issuer_element(xml: str = ISSUER_XML):
    """Parse a `<primaryIssuer>` block the way `FormD.from_xml` does.

    THE ONE LINE THAT CHANGES when `_party` moves to lxml (edgartools-07lk.11.3).
    """
    return BeautifulSoup(xml, features="xml").find("primaryIssuer")


# ------------------------------------------------------------ Issuer.from_xml


def test_issuer_from_xml_reads_every_field():
    """Ground truth: Form D filed by 1685 38th REIT, L.L.C. (CIK 0001961089)."""
    issuer = Issuer.from_xml(_issuer_element())

    assert issuer.cik == "0001961089"
    assert issuer.entity_name == "1685 38th REIT, L.L.C."
    assert issuer.entity_type == "Limited Liability Company"
    assert issuer.phone_number == "424-313-1550"
    assert issuer.jurisdiction == "DELAWARE"
    assert issuer.year_of_incorporation == "2022"
    assert issuer.incorporated_within_5_years is True


def test_issuer_from_xml_reads_the_full_address():
    address = Issuer.from_xml(_issuer_element()).primary_address

    assert address.street1 == "2029 CENTURY PARK EAST"
    assert address.street2 == "SUITE 1370"
    assert address.city == "LOS ANGELES"
    assert address.state_or_country == "CA"
    assert address.state_or_country_description == "CALIFORNIA"
    assert address.zipcode == "90067"
    assert not address.empty


def test_issuer_previous_name_lists_drop_the_literal_none_placeholder():
    """SEC writes `<value>None</value>` for "no previous names". It is not a name."""
    issuer = Issuer.from_xml(_issuer_element())
    assert issuer.issuer_previous_names == []
    assert issuer.edgar_previous_names == []


def test_issuer_previous_name_lists_keep_real_names_in_order():
    xml = ISSUER_XML.replace(
        "<issuerPreviousNameList>\n        <value>None</value>\n    </issuerPreviousNameList>",
        "<issuerPreviousNameList>"
        "<value>Old Name One</value>"
        "<value>None</value>"
        "<value>Old Name Two</value>"
        "</issuerPreviousNameList>",
    )
    issuer = Issuer.from_xml(_issuer_element(xml))
    assert issuer.issuer_previous_names == ["Old Name One", "Old Name Two"]


def test_issuer_previous_name_lists_read_the_previousName_spelling():
    """SEC also writes previous names with a `<previousName>` child instead of
    `<value>`. Ground truth: Shepherd's Finance, LLC (CIK 0001544190, formerly
    84 RE Partners, LLC), data/D.Shepards.xml. Regression for edgartools-gi0a:
    this spelling was silently dropped, returning [] instead of the real name.
    """
    xml = ISSUER_XML.replace(
        "<issuerPreviousNameList>\n        <value>None</value>\n    </issuerPreviousNameList>",
        "<issuerPreviousNameList>"
        "<previousName>84 RE Partners, LLC</previousName>"
        "</issuerPreviousNameList>",
    )
    issuer = Issuer.from_xml(_issuer_element(xml))
    assert issuer.issuer_previous_names == ["84 RE Partners, LLC"]
    assert issuer.edgar_previous_names == []


def test_issuer_previous_name_lists_drop_the_literal_none_placeholder_in_either_spelling():
    """SEC writes the literal 'None' placeholder under both spellings, e.g.
    data/D.APFund.xml: `<issuerPreviousNameList><previousName>None</previousName>`.
    """
    xml = ISSUER_XML.replace(
        "<issuerPreviousNameList>\n        <value>None</value>\n    </issuerPreviousNameList>",
        "<issuerPreviousNameList>"
        "<previousName>None</previousName>"
        "</issuerPreviousNameList>",
    )
    issuer = Issuer.from_xml(_issuer_element(xml))
    assert issuer.issuer_previous_names == []


def test_issuer_previous_name_lists_merge_both_spellings_without_duplicates():
    xml = ISSUER_XML.replace(
        "<issuerPreviousNameList>\n        <value>None</value>\n    </issuerPreviousNameList>",
        "<issuerPreviousNameList>"
        "<value>Old Name One</value>"
        "<previousName>Old Name One</previousName>"
        "<previousName>Old Name Two</previousName>"
        "</issuerPreviousNameList>",
    )
    issuer = Issuer.from_xml(_issuer_element(xml))
    assert issuer.issuer_previous_names == ["Old Name One", "Old Name Two"]


def test_issuer_tolerates_missing_previous_name_lists():
    xml = ISSUER_XML.replace("<issuerPreviousNameList>", "<absentList>").replace(
        "</issuerPreviousNameList>", "</absentList>"
    )
    issuer = Issuer.from_xml(_issuer_element(xml))
    assert issuer.issuer_previous_names == []


def test_issuer_without_an_address_gets_an_empty_address_not_none():
    """The address is always an `Address`; absence shows up as `.empty`, not `None`."""
    xml = ISSUER_XML.replace("issuerAddress", "someOtherBlock")
    issuer = Issuer.from_xml(_issuer_element(xml))

    assert issuer.primary_address is not None
    assert issuer.primary_address.empty
    assert issuer.primary_address.street1 is None
    # The scalar fields are still read.
    assert issuer.cik == "0001961089"


def test_issuer_not_incorporated_within_five_years():
    xml = ISSUER_XML.replace("<withinFiveYears>true<", "<withinFiveYears>false<")
    assert Issuer.from_xml(_issuer_element(xml)).incorporated_within_5_years is False


def test_issuer_without_a_year_of_incorporation_block_is_falsy_not_a_crash():
    """`incorporated_within_5_years` is built with `and`, so a missing block yields
    `None` rather than `False` — falsy either way, and pinned here because the lxml
    port changes what a missing element evaluates to."""
    xml = ISSUER_XML.replace("yearOfInc", "someOtherBlock")
    issuer = Issuer.from_xml(_issuer_element(xml))

    assert not issuer.incorporated_within_5_years
    assert issuer.year_of_incorporation is None


# ------------------------------------------------------------------- Address


def test_address_empty_is_true_only_when_every_location_field_is_blank():
    assert Address().empty
    assert Address(state_or_country_description="CALIFORNIA").empty  # not a location on its own
    assert not Address(street1="1 Main St").empty
    assert not Address(city="Boston").empty
    assert not Address(zipcode="02101").empty


def test_address_from_dict_maps_the_sgml_header_keys():
    address = Address.from_dict(
        {"STREET1": "1 Main St", "STREET2": "Floor 3", "CITY": "Boston", "STATE": "MA", "ZIP": "02101"}
    )
    assert address.street1 == "1 Main St"
    assert address.street2 == "Floor 3"
    assert address.city == "Boston"
    assert address.state_or_country == "MA"
    assert address.zipcode == "02101"
    assert address.state_or_country_description is None


def test_address_from_dict_tolerates_missing_keys():
    assert Address.from_dict({}).empty


def test_address_str_renders_two_or_three_lines():
    one_line = Address(street1="1 Main St", city="Boston", state_or_country="MA", zipcode="02101")
    assert str(one_line) == "1 Main St\nBoston, MA 02101"

    with_street2 = Address(
        street1="1 Main St", street2="Floor 3", city="Boston", state_or_country="MA", zipcode="02101"
    )
    assert str(with_street2) == "1 Main St\nFloor 3\nBoston, MA 02101"


def test_address_str_prefers_the_state_description_over_the_code():
    address = Address(
        street1="2029 CENTURY PARK EAST",
        city="LOS ANGELES",
        state_or_country="CA",
        state_or_country_description="CALIFORNIA",
        zipcode="90067",
    )
    assert str(address) == "2029 CENTURY PARK EAST\nLOS ANGELES, CALIFORNIA 90067"


def test_address_str_without_a_street_is_empty():
    assert str(Address(city="Boston", state_or_country="MA")) == ""


def test_address_str_without_a_zipcode_does_not_print_none():
    address = Address(street1="1 Main St", city="Boston", state_or_country="MA")
    assert str(address) == "1 Main St\nBoston, MA "
    assert "None" not in str(address)


# --------------------------------------------------- get_addresses_as_columns


def test_get_addresses_as_columns_includes_only_the_non_empty_addresses():
    mailing = Address(street1="PO Box 1", city="Boston", state_or_country="MA", zipcode="02101")
    business = Address(street1="1 Main St", city="Boston", state_or_country="MA", zipcode="02101")

    both = get_addresses_as_columns(mailing_address=mailing, business_address=business)
    assert len(both.renderables) == 2

    one = get_addresses_as_columns(mailing_address=mailing, business_address=Address())
    assert len(one.renderables) == 1

    neither = get_addresses_as_columns(mailing_address=None, business_address=None)
    assert len(neither.renderables) == 0


# -------------------------------------------------------------------- Person


def test_person_carries_relationships_and_clarification():
    person = Person(
        first_name="Daniel",
        last_name="Belldegrun",
        address=Address(city="LOS ANGELES", state_or_country="CA"),
        relationships=["Executive Officer", "Director"],
        relationship_clarification="Manager of the Managing Member",
    )
    assert repr(person) == "Daniel Belldegrun"
    assert person.relationships == ["Executive Officer", "Director"]
    assert person.relationship_clarification == "Manager of the Managing Member"


def test_person_without_relationships_gets_an_empty_list_not_none():
    """Contexts that carry no relationship still get a list, so callers can iterate."""
    assert Person(first_name="Ada", last_name="Lovelace").relationships == []


def test_person_str_uses_the_full_name():
    """Regression: `__str__` used to interpolate `first_name` twice (edgartools-uyhs)."""
    assert str(Person(first_name="Daniel", last_name="Belldegrun")) == "Daniel Belldegrun"


# ---------------------------------------------------------------------- Name


def test_name_full_name_joins_the_parts():
    assert Name(first_name="John", middle_name="Q", last_name="Public").full_name == "John Q Public"
    assert (
        Name(first_name="John", middle_name="Q", last_name="Public", suffix="Jr.").full_name
        == "John Q Public Jr."
    )


def test_name_full_name_without_a_middle_name():
    """Regression for edgartools-n921: this used to raise TypeError.

    `child_text` returns None for an absent `<middleName>` (edgar/muniadvisors/core.py),
    so this is the common case for muni advisors, not an edge case.
    """
    assert Name(first_name="John", middle_name=None, last_name="Public").full_name == "John Public"


def test_name_full_name_with_a_blank_middle_name_does_not_double_space():
    """The other half of n921: `' ' + ''` was a truthy single space."""
    assert Name(first_name="John", middle_name="", last_name="Public").full_name == "John Public"


def test_name_full_name_keeps_the_nmn_placeholder():
    """SEC writes the literal 'NMN' for no-middle-name; it is data, not absence.

    Ground truth: muni advisor Michael Tym, tests/test_muni_advisors.py:148.
    """
    assert Name(first_name="Michael", middle_name="NMN", last_name="Tym", suffix="Jr.").full_name == (
        "Michael NMN Tym Jr."
    )


# --------------------------------------------------------- Filer and Contact


def test_filer_renders_name_and_cik():
    filer = Filer(cik="0000320193", entity_name="Apple Inc.", file_number="001-36743")
    assert str(filer) == "Apple Inc. (0000320193)"
    assert repr(filer) == "Apple Inc. (0000320193)"
    assert filer.file_number == "001-36743"


def test_contact_renders_name_phone_and_email():
    contact = Contact(name="Jane Roe", phone_number="617-555-0100", email="jane@example.com")
    assert str(contact) == "Jane Roe (617-555-0100) jane@example.com"
    assert repr(contact) == str(contact)
