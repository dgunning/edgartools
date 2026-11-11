"""Regression: calculation and definition role names use the schema's roleType definition.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1731

The presentation parser named a role by the schema's `link:definition` (XBRL
2.1 section 5.1.3.3: the role's human-readable meaning) when one was loaded,
but the calculation and definition parsers always derived the name from the
role URI's last segment, and the coordinator did not give them the schema's
role types. One declared role came back as "100 - Statement - ..." from
presentation and "OpaqueName" from calculation and definition.

All three parsers now name roles through one helper
(`BaseParser._role_record`) that prefers the loaded definition and falls back
to the URI tail. The role URI stays the key and `roleId` stays the URI tail.
"""

from pathlib import Path

from edgar.xbrl import XBRL

ROLE = "http://example.com/role/OpaqueName"
ARCROLES = {
    "presentation": "http://www.xbrl.org/2003/arcrole/parent-child",
    "calculation": "http://www.xbrl.org/2003/arcrole/summation-item",
    "definition": "http://xbrl.org/int/dim/arcrole/domain-member",
}


def schema(role_definition):
    definition = f"<link:definition>{role_definition}</link:definition>" if role_definition else ""
    return (
        '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" '
        'xmlns:link="http://www.xbrl.org/2003/linkbase" '
        'xmlns:xbrli="http://www.xbrl.org/2003/instance" targetNamespace="http://example.com">'
        f'<xs:annotation><xs:appinfo><link:roleType roleURI="{ROLE}" id="role">{definition}'
        '<link:usedOn>link:presentationLink</link:usedOn><link:usedOn>link:calculationLink</link:usedOn>'
        '<link:usedOn>link:definitionLink</link:usedOn></link:roleType></xs:appinfo></xs:annotation>'
        '<xs:element id="ex_Total" name="Total" type="xbrli:monetaryItemType" substitutionGroup="xbrli:item" '
        'xbrli:periodType="duration"/>'
        '<xs:element id="ex_Part" name="Part" type="xbrli:monetaryItemType" substitutionGroup="xbrli:item" '
        'xbrli:periodType="duration"/></xs:schema>')


def role_names(role_definition):
    xbrl = XBRL()
    xbrl.parser.parse_schema_content(schema(role_definition))
    for kind, arcrole in ARCROLES.items():
        weight = ' weight="1"' if kind == "calculation" else ""
        content = (
            '<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase" '
            'xmlns:xlink="http://www.w3.org/1999/xlink">'
            f'<link:{kind}Link xlink:type="extended" xlink:role="{ROLE}">'
            '<link:loc xlink:type="locator" xlink:href="example.xsd#ex_Total" xlink:label="total"/>'
            '<link:loc xlink:type="locator" xlink:href="example.xsd#ex_Part" xlink:label="part"/>'
            f'<link:{kind}Arc xlink:type="arc" xlink:arcrole="{arcrole}" xlink:from="total" '
            f'xlink:to="part" order="1"{weight}/></link:{kind}Link></link:linkbase>')
        getattr(xbrl.parser, f"parse_{kind}_content")(content)
    return xbrl, {kind: getattr(xbrl.parser, f"{kind}_roles")[ROLE] for kind in ARCROLES}


def test_declared_definition_names_every_linkbase_role():
    xbrl, roles = role_names("100 - Statement - Human-readable statement")
    for kind, record in roles.items():
        assert record == {"roleUri": ROLE, "definition": "100 - Statement - Human-readable statement",
                          "roleId": "OpaqueName"}, kind
    assert xbrl.calculation_trees[ROLE].definition == "100 - Statement - Human-readable statement"


def test_role_without_a_definition_falls_back_to_the_uri():
    _, roles = role_names(None)
    assert {kind: record["definition"] for kind, record in roles.items()} == {
        "presentation": "OpaqueName", "calculation": "OpaqueName", "definition": "OpaqueName"}


def test_nike_fy2026_calculation_and_definition_role_names():
    """NIKE, Inc. 10-K for FY ended 2026-05-31, accession 0000320187-26-000088.

    nke-20260531.xsd declares role CONSOLIDATEDSTATEMENTSOFINCOME as
    "9952151 - Statement - CONSOLIDATED STATEMENTS OF INCOME" and
    CONSOLIDATEDBALANCESHEETS as "9952153 - Statement - CONSOLIDATED BALANCE SHEETS".
    """
    xbrl = XBRL.from_directory(Path("tests/fixtures/xbrl/nke/10k_2026"))
    income = "http://www.nike.com/role/CONSOLIDATEDSTATEMENTSOFINCOME"
    balance = "http://www.nike.com/role/CONSOLIDATEDBALANCESHEETS"
    assert xbrl.calculation_roles[income]["definition"] == "9952151 - Statement - CONSOLIDATED STATEMENTS OF INCOME"
    assert xbrl.calculation_trees[income].definition == "9952151 - Statement - CONSOLIDATED STATEMENTS OF INCOME"
    assert xbrl.definition_roles[balance]["definition"] == "9952153 - Statement - CONSOLIDATED BALANCE SHEETS"
    assert xbrl.calculation_roles[income]["roleId"] == "CONSOLIDATEDSTATEMENTSOFINCOME"
