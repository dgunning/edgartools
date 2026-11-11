"""
Regression test for GitHub issue #1725.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1725

`axes_for_role(role)[axis].default_member_id` was None whenever the axis's
dimension-default arc sat in a different extended link from the hypercube that
used the axis. A dimension-default relationship is global (XBRL Dimensions 1.0
section 2.7.1): it applies in every extended link that uses the dimension and
whose domain contains the default. The per-role answer now agrees with the
merged `xbrl.axes` answer.

Ground truth: Microsoft FY2024 10-K, accession 0000950170-24-087843, tracked
at tests/fixtures/xbrl/msft/10k_2024 (its schema embeds the linkbases). The
issue counted 48 affected axis-role pairs in this filing, read straight from
the definition linkbase.
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.parsers import XBRLParser

MSFT_DIR = Path("tests/fixtures/xbrl/msft/10k_2024")
MSFT_EXAMINATIONS = ("http://www.microsoft.com/20240630/taxonomy/role/"
                     "Role_DisclosureIncomeTaxesAdditionalInformationRegardingExaminationsDetail")
TYPED_RPO_AXIS = "us-gaap_RevenueRemainingPerformanceObligationExpectedTimingOfSatisfactionStartDateAxis"


@pytest.fixture(scope="module")
def msft():
    return XBRL.from_directory(MSFT_DIR)


@pytest.mark.fast
def test_default_declared_in_another_role_applies(msft):
    axis = msft.axes_for_role(MSFT_EXAMINATIONS)["us-gaap_IncomeTaxAuthorityAxis"]
    assert axis.domain_id == "us-gaap_IncomeTaxAuthorityDomain"
    assert axis.default_member_id == "us-gaap_IncomeTaxAuthorityDomain"
    assert msft.axes["us-gaap_IncomeTaxAuthorityAxis"].default_member_id == "us-gaap_IncomeTaxAuthorityDomain"


@pytest.mark.fast
def test_only_the_typed_axis_lacks_a_default(msft):
    """86 of Microsoft's 87 axis-role pairs have a default; 38 did on main."""
    dp = msft.parser.definition_parser
    pairs = [(role, axis_id, axis) for role, axes in dp.axes_by_role.items() for axis_id, axis in axes.items()]
    assert len(pairs) == 87
    without = [(role, axis_id) for role, axis_id, axis in pairs if axis.default_member_id is None]
    # A typed dimension has no default, by definition.
    assert [axis_id for _, axis_id in without] == [TYPED_RPO_AXIS]


def _linkbase(links: str) -> str:
    return f'''<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase"
 xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xbrldt="http://xbrl.org/2005/xbrldt">{links}</link:linkbase>'''


def _cube_link(role: str, domain: str, members=()) -> str:
    member_locs = "".join(f'<link:loc xlink:type="locator" xlink:label="{m}" xlink:href="t.xsd#{m}"/>' for m in members)
    member_arcs = "".join(
        f'<link:definitionArc xlink:type="arc" xlink:from="dom" xlink:to="{m}" '
        f'xlink:arcrole="http://xbrl.org/int/dim/arcrole/domain-member"/>' for m in members)
    return f'''<link:definitionLink xlink:type="extended" xlink:role="{role}">
  <link:loc xlink:type="locator" xlink:label="items" xlink:href="t.xsd#x_LineItems"/>
  <link:loc xlink:type="locator" xlink:label="cube" xlink:href="t.xsd#x_Table"/>
  <link:loc xlink:type="locator" xlink:label="axis" xlink:href="t.xsd#x_Axis"/>
  <link:loc xlink:type="locator" xlink:label="dom" xlink:href="t.xsd#{domain}"/>{member_locs}
  <link:definitionArc xlink:type="arc" xlink:from="items" xlink:to="cube" xlink:arcrole="http://xbrl.org/int/dim/arcrole/all" xbrldt:contextElement="segment"/>
  <link:definitionArc xlink:type="arc" xlink:from="cube" xlink:to="axis" xlink:arcrole="http://xbrl.org/int/dim/arcrole/hypercube-dimension"/>
  <link:definitionArc xlink:type="arc" xlink:from="axis" xlink:to="dom" xlink:arcrole="http://xbrl.org/int/dim/arcrole/dimension-domain"/>{member_arcs}
 </link:definitionLink>'''


def _default_link(role: str, default: str) -> str:
    return f'''<link:definitionLink xlink:type="extended" xlink:role="{role}">
  <link:loc xlink:type="locator" xlink:label="axis" xlink:href="t.xsd#x_Axis"/>
  <link:loc xlink:type="locator" xlink:label="def" xlink:href="t.xsd#{default}"/>
  <link:definitionArc xlink:type="arc" xlink:from="axis" xlink:to="def" xlink:arcrole="http://xbrl.org/int/dim/arcrole/dimension-default"/>
 </link:definitionLink>'''


USE = "http://example.com/role/Use"
DECLARE = "http://example.com/role/Declare"
OTHER = "http://example.com/role/Other"


@pytest.mark.fast
def test_default_in_a_role_without_the_axis_hypercube():
    """The default arc's role has no hypercube for the axis at all."""
    parser = XBRLParser()
    parser.parse_definition_content(_linkbase(_cube_link(USE, "x_Domain", ["x_A"]) + _default_link(DECLARE, "x_Domain")))
    assert parser.definition_parser.axes_for_role(USE)["x_Axis"].default_member_id == "x_Domain"
    assert parser.axes["x_Axis"].default_member_id == "x_Domain"


@pytest.mark.fast
def test_default_nested_below_the_domain_root_applies():
    parser = XBRLParser()
    parser.parse_definition_content(_linkbase(_cube_link(USE, "x_Domain", ["x_A"]) + _default_link(DECLARE, "x_A")))
    assert parser.definition_parser.axes_for_role(USE)["x_Axis"].default_member_id == "x_A"


@pytest.mark.fast
def test_default_outside_the_roles_domain_does_not_apply():
    """The role's domain does not contain the default, so it is not this role's."""
    parser = XBRLParser()
    parser.parse_definition_content(_linkbase(_cube_link(USE, "x_Domain", ["x_A"]) + _default_link(DECLARE, "x_Elsewhere")))
    assert parser.definition_parser.axes_for_role(USE)["x_Axis"].default_member_id is None


@pytest.mark.fast
def test_two_different_defaults_are_not_guessed_between():
    parser = XBRLParser()
    parser.parse_definition_content(_linkbase(
        _cube_link(USE, "x_Domain", ["x_A"]) + _default_link(DECLARE, "x_Domain") + _default_link(OTHER, "x_A")))
    assert parser.definition_parser.axes_for_role(USE)["x_Axis"].default_member_id is None


@pytest.mark.fast
def test_a_local_default_still_wins():
    parser = XBRLParser()
    local = _cube_link(USE, "x_Domain", ["x_A"]).replace(
        "</link:definitionLink>",
        '<link:loc xlink:type="locator" xlink:label="local" xlink:href="t.xsd#x_A"/>'
        '<link:definitionArc xlink:type="arc" xlink:from="axis" xlink:to="local" '
        'xlink:arcrole="http://xbrl.org/int/dim/arcrole/dimension-default"/></link:definitionLink>')
    parser.parse_definition_content(_linkbase(local + _default_link(DECLARE, "x_Domain")))
    assert parser.definition_parser.axes_for_role(USE)["x_Axis"].default_member_id == "x_A"
