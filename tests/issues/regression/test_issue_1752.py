"""
Regression test for GitHub issue #1752.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1752

A domain reached through `xbrldt:targetRole` lost its nested member hierarchy:
`_copy_domain_into_role` copied only the remote root's direct members, and a
domain-member arc carrying `targetRole` was not followed at all, so a branch's
own children (declared in the target role) were never visible from the role
asking. XBRL Dimensions 1.0 section 2.4, example 7, continues a domain-member
relationship through `targetRole` into the target role's domain-member arcs.

The issue's reproduction is a synthetic definition linkbase; no tracked
fixture uses a domain-member `targetRole` (measured over the 34 fixtures with
definition linkbases: the change alters none of their dimensional models).
"""

import pytest

from edgar.xbrl.parsers import XBRLParser

ROLE = "http://example.com/role/Statement"
REMOTE = "http://example.com/role/Members"
DEEPER = "http://example.com/role/Deeper"


def _loc(label, element):
    return f'<link:loc xlink:type="locator" xlink:label="{label}" xlink:href="test.xsd#{element}"/>'


def _arc(frm, to, arcrole, extra=""):
    return (f'<link:definitionArc xlink:type="arc" xlink:from="{frm}" xlink:to="{to}" '
            f'xlink:arcrole="http://xbrl.org/int/dim/arcrole/{arcrole}" {extra}/>')


def _linkbase(links):
    return ('<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase" '
            'xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xbrldt="http://xbrl.org/2005/xbrldt">'
            + links + '</link:linkbase>')


def _link(role, body):
    return f'<link:definitionLink xlink:type="extended" xlink:role="{role}">{body}</link:definitionLink>'


# The issue's fragment, trimmed to what the hierarchy needs.
STATEMENT = _link(ROLE, "".join([
    _loc("items", "x_LineItems"), _loc("all", "x_IncludedTable"), _loc("axis", "x_Axis"),
    _loc("remoteaxis", "x_RemoteAxis"), _loc("remoteroot", "x_RemoteDomain"), _loc("domain", "x_Domain"),
    _loc("unusable", "x_UnusableMember"), _loc("branch", "x_Branch"),
    _arc("items", "all", "all", 'xbrldt:contextElement="segment"'),
    _arc("all", "axis", "hypercube-dimension"),
    _arc("all", "remoteaxis", "hypercube-dimension"),
    _arc("axis", "domain", "dimension-domain"),
    _arc("remoteaxis", "remoteroot", "dimension-domain", f'xbrldt:targetRole="{REMOTE}"'),
    _arc("domain", "unusable", "domain-member", 'xbrldt:usable="false" order="1"'),
    _arc("domain", "branch", "domain-member", f'xbrldt:targetRole="{REMOTE}" order="2"'),
]))
MEMBERS = _link(REMOTE, "".join([
    _loc("remoteroot", "x_RemoteDomain"), _loc("branch", "x_Branch"), _loc("leaf", "x_LeafMember"),
    _arc("remoteroot", "branch", "domain-member"),
    _arc("branch", "leaf", "domain-member"),
]))


@pytest.mark.fast
@pytest.mark.parametrize("order", ["statement-first", "members-first"])
def test_targetrole_domain_member_continuation_keeps_nested_members(order):
    links = STATEMENT + MEMBERS if order == "statement-first" else MEMBERS + STATEMENT
    parser = XBRLParser()
    parser.parse_definition_content(_linkbase(links))
    domains = parser.definition_parser.domains_for_role(ROLE)

    assert domains["x_Domain"].members == ["x_UnusableMember", "x_Branch"]
    assert domains["x_RemoteDomain"].members == ["x_Branch"]
    # The branch's children live in REMOTE; they are now visible from ROLE.
    assert domains["x_Branch"].members == ["x_LeafMember"]
    assert domains["x_Branch"].parent in ("x_Domain", "x_RemoteDomain")


@pytest.mark.fast
def test_dimension_domain_hop_copies_the_whole_subtree():
    """No domain-member continuation: the hop alone must bring grandchildren."""
    statement = _link(ROLE, "".join([
        _loc("items", "x_LineItems"), _loc("all", "x_Table"), _loc("remoteaxis", "x_RemoteAxis"),
        _loc("remoteroot", "x_RemoteDomain"),
        _arc("items", "all", "all"),
        _arc("all", "remoteaxis", "hypercube-dimension"),
        _arc("remoteaxis", "remoteroot", "dimension-domain", f'xbrldt:targetRole="{REMOTE}"'),
    ]))
    parser = XBRLParser()
    parser.parse_definition_content(_linkbase(statement + MEMBERS))
    domains = parser.definition_parser.domains_for_role(ROLE)

    assert domains["x_RemoteDomain"].members == ["x_Branch"]
    assert domains["x_Branch"].members == ["x_LeafMember"]
    assert domains["x_Branch"].parent == "x_RemoteDomain"
    # The source role keeps its own copy untouched.
    assert parser.definition_parser.domains_for_role(REMOTE)["x_Branch"].members == ["x_LeafMember"]


@pytest.mark.fast
def test_chained_continuations_and_cycles_terminate():
    """A continuation into a role that continues again, with a cycle back."""
    members = _link(REMOTE, "".join([
        _loc("remoteroot", "x_RemoteDomain"), _loc("branch", "x_Branch"),
        _arc("remoteroot", "branch", "domain-member", f'xbrldt:targetRole="{DEEPER}"'),
    ]))
    deeper = _link(DEEPER, "".join([
        _loc("branch", "x_Branch"), _loc("leaf", "x_LeafMember"), _loc("back", "x_RemoteDomain"),
        _arc("branch", "leaf", "domain-member"),
        _arc("leaf", "back", "domain-member", f'xbrldt:targetRole="{REMOTE}"'),
    ]))
    statement = _link(ROLE, "".join([
        _loc("items", "x_LineItems"), _loc("all", "x_Table"), _loc("remoteaxis", "x_RemoteAxis"),
        _loc("remoteroot", "x_RemoteDomain"),
        _arc("items", "all", "all"),
        _arc("all", "remoteaxis", "hypercube-dimension"),
        _arc("remoteaxis", "remoteroot", "dimension-domain", f'xbrldt:targetRole="{REMOTE}"'),
    ]))
    parser = XBRLParser()
    parser.parse_definition_content(_linkbase(statement + members + deeper))
    domains = parser.definition_parser.domains_for_role(ROLE)

    assert domains["x_RemoteDomain"].members == ["x_Branch"]
    assert domains["x_Branch"].members == ["x_LeafMember"]
