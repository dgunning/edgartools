"""
Extensible enumerations: the declared domain of an enumeration concept and the
members its fact value names (GH #1255).

Ground truth from tracked fixtures, read offline:
- Apple's FY2023 10-K (accession 0000320193-23-000106),
  tests/fixtures/xbrl/aapl/aapl-20230930_htm.xml: the one value of
  us-gaap:HedgedAssetStatementOfFinancialPositionExtensibleEnumeration is
  'http://fasb.org/us-gaap/2023#MarketableSecuritiesCurrent
  http://fasb.org/us-gaap/2023#MarketableSecuritiesNoncurrent'. The filing
  imports the concept, so its declaration comes from the bundled FASB table:
  us-gaap-2026.xsd declares it enum2:enumerationSetItemType with
  enum2:domain='us-gaap:AssetsAbstract', enum2:headUsable='false' and
  enum2:linkrole='http://fasb.org/srt/role/srt-eedm/ExtensibleEnumerationLists'
  (the newest year's declaration is kept).
- Microsoft's FY2024 10-K (accession 0000950170-24-087843),
  tests/fixtures/xbrl/msft/10k_2024: msft-20240730.xsd declares
  msft_DerivativeAssetStatementOfFinancialPositionExtensibleEnumerationNotDisclosedFlag
  with enum2:domain="us-gaap:AssetsAbstract", enum2:headUsable="false",
  enum2:linkrole="http://fasb.org/us-gaap/role/eedm/ExtensibleEnumerationLists";
  msft-20240730_htm.xml reports it twice, both times
  'http://fasb.org/us-gaap/2023#DerivativeAssets'.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1255
"""

from pathlib import Path

import pytest

from edgar.exceptions import ValidationError
from edgar.xbrl import XBRL, EnumerationDomain, EnumerationMember, parse_enumeration_value
from edgar.xbrl.element_metadata import build_element_metadata
from edgar.xbrl.enumerations import enumeration_domain, parse_head_usable
from edgar.xbrl.models import ElementCatalog
from edgar.xbrl.parsers.concepts import get_standard_declaration
from edgar.xbrl.parsers.schema import SchemaParser

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "xbrl"
AAPL_10K = FIXTURES / "aapl"
MSFT_10K = FIXTURES / "msft" / "10k_2024"

AAPL_CONCEPT = "us-gaap_HedgedAssetStatementOfFinancialPositionExtensibleEnumeration"
AAPL_VALUE = ("http://fasb.org/us-gaap/2023#MarketableSecuritiesCurrent "
              "http://fasb.org/us-gaap/2023#MarketableSecuritiesNoncurrent")
MSFT_CONCEPT = "msft_DerivativeAssetStatementOfFinancialPositionExtensibleEnumerationNotDisclosedFlag"
US_GAAP_2023 = "http://fasb.org/us-gaap/2023"


@pytest.fixture(scope="module")
def aapl():
    return XBRL.from_directory(AAPL_10K)


@pytest.fixture(scope="module")
def msft():
    return XBRL.from_directory(MSFT_10K)


def _values(xbrl, concept):
    return sorted({fact.value.strip() for fact in xbrl._facts.values()
                   if fact.element_id.replace(':', '_') == concept})


# --- the bundled FASB table -------------------------------------------------

def test_bundled_table_carries_the_enumeration_attributes():
    declaration = get_standard_declaration(AAPL_CONCEPT)
    assert declaration['type'] == 'enum2:enumerationSetItemType'
    assert declaration['enum_domain'] == 'us-gaap:AssetsAbstract'
    assert declaration['enum_linkrole'] == 'http://fasb.org/srt/role/srt-eedm/ExtensibleEnumerationLists'
    assert declaration['enum_head_usable'] == 'false'


def test_bundled_table_has_no_enumeration_attributes_for_other_concepts():
    declaration = get_standard_declaration('us-gaap:Assets')
    assert declaration['balance'] == 'debit'
    assert (declaration['enum_domain'], declaration['enum_linkrole'], declaration['enum_head_usable']) == (None, None, None)


# --- element_metadata().enumeration ----------------------------------------

def test_imported_concept_enumeration_comes_from_the_bundled_table(aapl):
    assert aapl.element_metadata(AAPL_CONCEPT).enumeration == EnumerationDomain(
        domain='us-gaap:AssetsAbstract',
        linkrole='http://fasb.org/srt/role/srt-eedm/ExtensibleEnumerationLists',
        head_usable=False,
        is_set=True)


def test_filing_declared_concept_enumeration_comes_from_the_filing_schema(msft):
    element = msft.element_catalog[MSFT_CONCEPT]
    assert (element.enum_domain, element.enum_head_usable) == ('us-gaap:AssetsAbstract', 'false')
    assert msft.element_metadata(MSFT_CONCEPT).enumeration == EnumerationDomain(
        domain='us-gaap:AssetsAbstract',
        linkrole='http://fasb.org/us-gaap/role/eedm/ExtensibleEnumerationLists',
        head_usable=False,
        is_set=True)


def test_a_concept_that_is_not_an_enumeration_has_none(aapl, msft):
    assert aapl.element_metadata('us-gaap:Assets').enumeration is None
    assert aapl.element_metadata('us-gaap:Assets').balance == 'debit'
    deferred = msft.element_metadata('msft:ContractWithCustomerLiabilityRevenueDeferred')
    assert (deferred.balance, deferred.enumeration) == ('credit', None)


def test_filing_declaration_wins_over_the_table():
    # A filing schema that redeclares the concept with its own linkrole
    element = ElementCatalog(AAPL_CONCEPT, 'enum2:enumerationSetItemType', 'instant',
                             enum_domain='us-gaap:LiabilitiesAbstract', enum_linkrole='http://example.com/role/x')
    enumeration = build_element_metadata(AAPL_CONCEPT, element, None).enumeration
    assert (enumeration.domain, enumeration.linkrole) == ('us-gaap:LiabilitiesAbstract', 'http://example.com/role/x')
    # absent headUsable on a known enumeration is the enum2 default
    assert enumeration.head_usable is False


def test_schema_reads_enum_attributes_by_namespace_not_prefix():
    xsd = """<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
        xmlns:xbrli="http://www.xbrl.org/2003/instance"
        xmlns:ee="http://xbrl.org/2020/extensible-enumerations-2.0"
        xmlns:old="http://xbrl.org/2014/extensible-enumerations"
        xmlns:abc="http://abc.example/2024" targetNamespace="http://abc.example/2024">
      <xs:element id="abc_Set" name="Set" type="ee:enumerationSetItemType" substitutionGroup="xbrli:item"
          xbrli:periodType="duration" ee:domain="abc:ThingsDomain" ee:linkrole="http://abc.example/role/Things"
          ee:headUsable="1"/>
      <xs:element id="abc_One" name="One" type="old:enumerationItemType" substitutionGroup="xbrli:item"
          xbrli:periodType="duration" old:domain="abc:OtherDomain" old:linkrole="http://abc.example/role/Other"
          old:headUsable="maybe"/>
      <xs:element id="abc_Plain" name="Plain" type="xbrli:stringItemType" substitutionGroup="xbrli:item"
          xbrli:periodType="duration"/>
    </xs:schema>"""
    catalog = {}
    parser = SchemaParser(catalog)
    parser.parse_schema_content(xsd)
    assert (catalog['abc_Set'].enum_domain, catalog['abc_Set'].enum_head_usable) == ('abc:ThingsDomain', '1')
    assert catalog['abc_One'].enum_linkrole == 'http://abc.example/role/Other'
    assert catalog['abc_Plain'].enum_domain is None
    assert parser.namespace_prefixes['http://abc.example/2024'] == 'abc'

    meta = build_element_metadata('abc_Set', catalog['abc_Set'], None)
    assert meta.enumeration == EnumerationDomain('abc:ThingsDomain', 'http://abc.example/role/Things', True, True)
    one = build_element_metadata('abc_One', catalog['abc_One'], None).enumeration
    assert (one.is_set, one.head_usable) == (False, None)
    assert build_element_metadata('abc_Plain', catalog['abc_Plain'], None).enumeration is None


@pytest.mark.parametrize("text, expected", [
    (None, False), ('true', True), ('1', True), (' false ', False), ('0', False), ('yes', None), ('', None),
])
def test_head_usable_is_an_xs_boolean(text, expected):
    assert parse_head_usable(text) is expected


def test_enumeration_domain_is_none_for_a_plain_type():
    assert enumeration_domain('xbrli:monetaryItemType', None, None, None) is None


def test_element_catalog_positional_constructor_still_works():
    element = ElementCatalog('x_A', 'xbrli:stringItemType', 'duration', None, False, {}, None, None)
    assert (element.enum_domain, element.enum_linkrole, element.enum_head_usable) == (None, None, None)


# --- members of a fact value -------------------------------------------------

def test_apple_two_member_value(aapl):
    assert _values(aapl, AAPL_CONCEPT) == [AAPL_VALUE]
    assert aapl.enumeration_members(AAPL_VALUE) == (
        EnumerationMember(US_GAAP_2023, 'MarketableSecuritiesCurrent', 'us-gaap_MarketableSecuritiesCurrent'),
        EnumerationMember(US_GAAP_2023, 'MarketableSecuritiesNoncurrent', 'us-gaap_MarketableSecuritiesNoncurrent'),
    )


def test_microsoft_filing_declared_concept_value(msft):
    values = _values(msft, MSFT_CONCEPT)
    assert values == ['http://fasb.org/us-gaap/2023#DerivativeAssets']
    assert msft.enumeration_members(values[0]) == (
        EnumerationMember(US_GAAP_2023, 'DerivativeAssets', 'us-gaap_DerivativeAssets'),)


def test_member_concept_uses_the_filing_prefix_and_never_guesses(msft):
    members = msft.enumeration_members(
        "http://www.microsoft.com/20240630#CloudMember\n\thttp://unbound.example/2024#Thing  urn:x:y#Z")
    assert [m.concept for m in members] == ['msft_CloudMember', None, None]
    assert (members[2].namespace, members[2].name) == ('urn:x:y', 'Z')


def test_split_on_the_last_hash():
    member, = parse_enumeration_value('http://a.example/x#frag#Name', {'http://a.example/x#frag': 'a'})
    assert (member.namespace, member.name, member.concept) == ('http://a.example/x#frag', 'Name', 'a_Name')


@pytest.mark.parametrize("value", [None, '', '   \n'])
def test_empty_or_nil_value_has_no_members(aapl, value):
    assert aapl.enumeration_members(value) == ()


@pytest.mark.parametrize("value", ['MarketableSecuritiesCurrent', 'http://fasb.org/us-gaap/2023#', '#Name'])
def test_malformed_member_raises_a_useful_error(value):
    with pytest.raises(ValidationError, match="namespace#LocalName"):
        parse_enumeration_value(value)


def test_non_string_value_raises_type_error():
    with pytest.raises(TypeError, match="must be a string"):
        parse_enumeration_value(42)
