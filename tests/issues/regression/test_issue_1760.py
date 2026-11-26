"""Regression: duplicate removal compared enumeration values with their whitespace.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1760

An extensible-enumeration value is an xs:token list of members, so the
whitespace between members is not significant (Extensible Enumerations 2.0
section 6.2.2) and duplicate detection compares the collapsed value (section
6.2.3). The facts frame compared the raw string, so one member set filed once
with a space and once with a line break stayed as two rows.

`value` itself is still returned exactly as filed; only the de-duplication
key collapses whitespace, and only for enumeration-typed concepts.
"""

import pytest

from edgar.xbrl import XBRL

SCHEMA = '''<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:enum2="http://xbrl.org/2020/extensible-enumerations-2.0" targetNamespace="http://example.com" xmlns:ex="http://example.com" elementFormDefault="qualified">
<xs:element name="Selection" id="ex_Selection" type="enum2:enumerationSetItemType" substitutionGroup="xbrli:item" xbrli:periodType="instant" enum2:domain="ex:Domain" enum2:linkrole="http://example.com/role/enumeration" enum2:headUsable="false"/>
<xs:element name="Note" id="ex_Note" type="xbrli:stringItemType" substitutionGroup="xbrli:item" xbrli:periodType="instant"/>
</xs:schema>'''


def facts_frame(selections=(), notes=(), columns=()):
    facts = "".join(f'<ex:Selection id="s{i}" contextRef="c">{v}</ex:Selection>' for i, v in enumerate(selections))
    facts += "".join(f'<ex:Note id="n{i}" contextRef="c">{v}</ex:Note>' for i, v in enumerate(notes))
    xbrl = XBRL()
    xbrl.parser.parse_schema_content(SCHEMA)
    xbrl.parser.parse_instance_content(
        '<xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:ex="http://example.com">'
        '<context id="c"><entity><identifier scheme="http://www.sec.gov/CIK">1</identifier></entity>'
        f'<period><instant>2025-12-31</instant></period></context>{facts}</xbrl>')
    if columns:
        return xbrl.facts.query().to_dataframe(*columns)
    return xbrl.facts.to_dataframe()


SPACED = "http://example.com#A http://example.com#B"
BROKEN = "http://example.com#A\nhttp://example.com#B"


@pytest.mark.fast
def test_same_members_with_different_whitespace_are_one_fact():
    df = facts_frame([SPACED, BROKEN])
    assert len(df) == 1
    # The kept row is the first occurrence, as filed.
    assert df["value"].tolist() == [SPACED]
    df = facts_frame([BROKEN, SPACED])
    assert df["value"].tolist() == [BROKEN]


@pytest.mark.fast
def test_different_members_stay_two_facts():
    df = facts_frame([SPACED, "http://example.com#A"])
    assert sorted(df["value"]) == sorted([SPACED, "http://example.com#A"])


@pytest.mark.fast
def test_whitespace_still_counts_for_a_plain_string():
    # xs:string preserves whitespace: these are two different values.
    df = facts_frame(notes=["one two", "one\ntwo"])
    assert len(df) == 2


@pytest.mark.fast
def test_projected_frame_drops_the_same_duplicate():
    # The early projection must keep dedup_value long enough to de-duplicate,
    # and not return it when it was not asked for.
    df = facts_frame([SPACED, BROKEN], columns=("concept", "value"))
    assert df.to_dict("records") == [{"concept": "ex:Selection", "value": SPACED}]


@pytest.mark.fast
def test_hidden_key_is_not_a_default_column():
    # Like fact_key and original_label, it appears only when asked for by name.
    for df in (facts_frame([SPACED, BROKEN]), facts_frame([SPACED, BROKEN], columns=("value",))):
        assert "dedup_value" not in df.columns


@pytest.mark.network
def test_cracker_barrel_state_sets_keep_their_three_periods():
    """Cracker Barrel 10-K, accession 0001104659-26-110772: the state-and-local
    tax-rate reconciliation enumeration names IL, KY, TN and TX for each of three
    fiscal years, filed with line breaks between members. The three are
    different periods, not duplicates, and each value is kept as filed."""
    from edgar import find

    concept = ("EffectiveIncomeTaxRateReconciliationStateAndLocalJurisdiction"
               "ContributionGreaterThan50PercentTaxEffectExtensibleEnumeration")
    xbrl = find("0001104659-26-110772").xbrl()
    df = xbrl.facts.query().by_concept(concept).to_dataframe()

    assert sorted(df["period_end"].astype(str)) == ["2024-08-02", "2025-08-01", "2026-07-31"]
    for value in df["value"]:
        assert "\n" in value
        assert [m.name for m in xbrl.enumeration_members(value)] == ["IL", "KY", "TN", "TX"]
