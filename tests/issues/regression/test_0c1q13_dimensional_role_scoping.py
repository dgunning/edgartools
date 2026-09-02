"""
Regression tests for edgartools-0c1q.13 (cluster A): the dimensional model was
not role-scoped.

`DefinitionParser` kept tables per role but kept axes and domains in dicts keyed
on `element_id` alone, with no role on either model. Six reports follow from that
one asymmetry, or from a line in the same loop that was never wired up:

  .8  a domain reused across roles kept only the LAST role's members
  .10 `Domain.parent` was never written
  .5  `xbrldt:targetRole` was not followed across extended links
  .2  `dimension-default` arcs were ignored, leaving `Axis.default_member_id` unset
  .9  `Table.closed` was a hardcoded literal `False`, not a read of `xbrldt:closed`
  .12 the `order` attribute was extracted and then never used to sort axes

Ground truth comes from checked-in fixtures, so these run offline:

  tests/fixtures/xbrl/aapl/10k_2023/aapl-20230930_def.xml
      Apple FY2023 10-K, accession 0000320193-23-000106
  tests/fixtures/xbrl/nflx/10k_2010/nflx-20100222_def.xml
      Netflix FY2009 10-K — 19 `xbrldt:targetRole` attributes, which is why it
      guards the cross-role hop
"""

from pathlib import Path

import pytest

from edgar.xbrl.parsers import XBRLParser

AAPL_DEF = Path("tests/fixtures/xbrl/aapl/10k_2023/aapl-20230930_def.xml")
NFLX_DEF = Path("tests/fixtures/xbrl/nflx/10k_2010/nflx-20100222_def.xml")

AAPL_OPERATIONS = "http://www.apple.com/role/CONSOLIDATEDSTATEMENTSOFOPERATIONS"
AAPL_EQUITY = "http://www.apple.com/role/CONSOLIDATEDSTATEMENTSOFSHAREHOLDERSEQUITY"
AAPL_REVENUE = (
    "http://www.apple.com/role/"
    "RevenueNetSalesDisaggregatedbySignificantProductsandServicesDetails"
)
NFLX_INCOME = "http://www.netflix.com/taxonomy/role/StatementOfIncome"
NFLX_COMMON = "http://www.netflix.com/taxonomy/role/CommonDomainMembers"

PRODUCTS_DOMAIN = "srt_ProductsAndServicesDomain"
PRODUCT_AXIS = "srt_ProductOrServiceAxis"
EQUITY_ROLLFORWARD = "us-gaap_IncreaseDecreaseInStockholdersEquityRollForward"


@pytest.fixture(scope="module")
def aapl():
    """Apple's definition linkbase, parsed on its own."""
    parser = XBRLParser()
    parser.parse_definition_content(AAPL_DEF.read_text())
    return parser


@pytest.fixture(scope="module")
def nflx():
    """Netflix's definition linkbase, parsed on its own."""
    parser = XBRLParser()
    parser.parse_definition_content(NFLX_DEF.read_text())
    return parser


def _definition_link(role_uri: str, arcs: str, locators: str) -> str:
    return f"""
      <definitionLink xlink:type="extended" xlink:role="{role_uri}">
        {locators}
        {arcs}
      </definitionLink>"""


def _linkbase(*links: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<linkbase xmlns="http://www.xbrl.org/2003/linkbase"
          xmlns:xlink="http://www.w3.org/1999/xlink"
          xmlns:xbrldt="http://xbrl.org/2005/xbrldt">
  {"".join(links)}
</linkbase>"""


def _loc(label: str) -> str:
    return (f'<loc xlink:type="locator" xlink:href="ex.xsd#{label}" '
            f'xlink:label="{label}"/>')


def _arc(arcrole: str, frm: str, to: str, **attrs: str) -> str:
    extra = "".join(f' {k}="{v}"' for k, v in attrs.items())
    return (f'<definitionArc xlink:type="arc" '
            f'xlink:arcrole="http://xbrl.org/int/dim/arcrole/{arcrole}" '
            f'xlink:from="{frm}" xlink:to="{to}"{extra}/>')


# ---------------------------------------------------------------------------
# .8 — a domain reused across roles kept only the last role's members
# ---------------------------------------------------------------------------

def test_reused_domain_keeps_each_roles_members(aapl):
    """
    Apple declares `srt_ProductsAndServicesDomain` under two roles with
    genuinely different member sets: the income statement splits revenue two
    ways, the revenue note splits it five ways. Before the fix a single global
    `Domain` object held whichever set was parsed last, so one of these two
    assertions was always wrong.
    """
    operations = aapl.domains_for_role(AAPL_OPERATIONS)[PRODUCTS_DOMAIN]
    revenue = aapl.domains_for_role(AAPL_REVENUE)[PRODUCTS_DOMAIN]

    assert operations.members == ["us-gaap_ProductMember", "us-gaap_ServiceMember"]
    assert revenue.members == [
        "aapl_IPhoneMember",
        "aapl_MacMember",
        "aapl_IPadMember",
        "aapl_WearablesHomeandAccessoriesMember",
        "us-gaap_ServiceMember",
    ]
    assert operations.role_uri == AAPL_OPERATIONS
    assert revenue.role_uri == AAPL_REVENUE


def test_flat_domain_view_is_a_union_not_a_truncation(aapl):
    """
    `xbrl.domains` keeps its flat shape for existing callers, but it must now
    merge the roles rather than let the last one win. Six distinct members
    across the two roles, `us-gaap_ServiceMember` appearing in both.
    """
    merged = aapl.domains[PRODUCTS_DOMAIN].members

    assert set(merged) == {
        "us-gaap_ProductMember",
        "us-gaap_ServiceMember",
        "aapl_IPhoneMember",
        "aapl_MacMember",
        "aapl_IPadMember",
        "aapl_WearablesHomeandAccessoriesMember",
    }
    assert len(merged) == len(set(merged)), "merged view should not duplicate members"


def test_synthetic_domain_reuse_is_isolated_per_role():
    """The same defect on a two-role linkbase small enough to read in full."""
    shared = _loc("Axis") + _loc("Dom") + _loc("M1") + _loc("M2") + _loc("Table") + _loc("Items")
    role_a = _definition_link(
        "http://example.com/role/A",
        _arc("all", "Items", "Table")
        + _arc("hypercube-dimension", "Table", "Axis")
        + _arc("dimension-domain", "Axis", "Dom")
        + _arc("domain-member", "Dom", "M1"),
        shared,
    )
    role_b = _definition_link(
        "http://example.com/role/B",
        _arc("all", "Items", "Table")
        + _arc("hypercube-dimension", "Table", "Axis")
        + _arc("dimension-domain", "Axis", "Dom")
        + _arc("domain-member", "Dom", "M2"),
        shared,
    )

    parser = XBRLParser()
    parser.parse_definition_content(_linkbase(role_a, role_b))

    assert parser.domains_for_role("http://example.com/role/A")["Dom"].members == ["M1"]
    assert parser.domains_for_role("http://example.com/role/B")["Dom"].members == ["M2"]


# ---------------------------------------------------------------------------
# .10 — Domain.parent was never written
# ---------------------------------------------------------------------------

def test_nested_member_records_its_parent_domain(aapl):
    """
    In the equity statement `us-gaap_IncreaseDecreaseInStockholdersEquityRollForward`
    is both a member of `us-gaap_StatementLineItems` and a parent of eight members
    of its own. It was exposed with `parent=None`, which loses the nesting.
    """
    domains = aapl.domains_for_role(AAPL_EQUITY)
    rollforward = domains[EQUITY_ROLLFORWARD]

    assert rollforward.parent == "us-gaap_StatementLineItems"
    assert len(rollforward.members) == 8
    assert rollforward.members[0] == "us-gaap_StockholdersEquity"


def test_top_level_domain_has_no_parent(aapl):
    """A domain that is nobody's member keeps `parent=None` — the control."""
    domains = aapl.domains_for_role(AAPL_OPERATIONS)

    assert domains["us-gaap_StatementLineItems"].parent is None


# ---------------------------------------------------------------------------
# .5 — xbrldt:targetRole was not followed across extended links
# ---------------------------------------------------------------------------

def test_target_role_hop_resolves_the_axis_domain(nflx):
    """
    Netflix declares the axis inside each statement role but its domain and
    members once, in a shared role, reached by `xbrldt:targetRole`. Under the
    old global keying this resolved by accident; role-scoping it without
    following the hop would break it, which is why this test is here.
    """
    axis = nflx.axes_for_role(NFLX_INCOME)["dei_LegalEntityAxis"]

    assert axis.domain_id == "dei_EntityDomain"
    assert axis.default_member_id == "dei_EntityDomain"

    domain = nflx.domains_for_role(NFLX_INCOME)["dei_EntityDomain"]
    assert domain.members == ["us-gaap_ParentCompanyMember"]


@pytest.mark.parametrize("reverse", [False, True], ids=["declared-first", "declared-last"])
def test_target_role_on_all_arc_finds_axes_in_the_target_role(reverse):
    """
    The shape gh #1194 reports, taken from the XBRL International Dimensions
    suite (V-100 / muliRoleInheritance_pa_m1_1): the `all` arc names a target
    role, and the hypercube's dimensions are declared only there. The source
    role looked as though it had no table at all.

    Parametrized over declaration order because a filer may put either extended
    link first, and the two may even arrive in separate files.
    """
    source = _definition_link(
        "http://example.com/role/Source",
        _arc("all", "Items", "Table", **{"xbrldt:targetRole": "http://example.com/role/Target"}),
        _loc("Items") + _loc("Table"),
    )
    target = _definition_link(
        "http://example.com/role/Target",
        _arc("hypercube-dimension", "Table", "Axis")
        + _arc("dimension-domain", "Axis", "Dom"),
        _loc("Table") + _loc("Axis") + _loc("Dom"),
    )
    links = [target, source] if reverse else [source, target]

    parser = XBRLParser()
    parser.parse_definition_content(_linkbase(*links))

    tables = parser.tables.get("http://example.com/role/Source", [])
    assert [t.element_id for t in tables] == ["Table"]
    assert tables[0].axes == ["Axis"]
    assert parser.axes_for_role("http://example.com/role/Source")["Axis"].domain_id == "Dom"


def test_target_role_hop_works_across_separate_files():
    """The two extended links arriving in separate `parse_definition_content`
    calls must resolve the same way — a filer may split them across files."""
    source = _linkbase(_definition_link(
        "http://example.com/role/Source",
        _arc("all", "Items", "Table", **{"xbrldt:targetRole": "http://example.com/role/Target"}),
        _loc("Items") + _loc("Table"),
    ))
    target = _linkbase(_definition_link(
        "http://example.com/role/Target",
        _arc("hypercube-dimension", "Table", "Axis"),
        _loc("Table") + _loc("Axis"),
    ))

    parser = XBRLParser()
    parser.parse_definition_content(source)
    parser.parse_definition_content(target)

    tables = parser.tables.get("http://example.com/role/Source", [])
    assert [t.axes for t in tables] == [["Axis"]]


# ---------------------------------------------------------------------------
# .2 — dimension-default arcs were ignored
# ---------------------------------------------------------------------------

def test_dimension_default_sets_the_axis_default_member(aapl):
    """
    Without the default member a fact reported at the axis default cannot be
    told apart from an undimensioned fact, which is exactly what the default
    member is for.
    """
    axis = aapl.axes_for_role(AAPL_OPERATIONS)[PRODUCT_AXIS]

    assert axis.default_member_id == PRODUCTS_DOMAIN
    assert axis.domain_id == PRODUCTS_DOMAIN


def test_equity_axis_default_member(aapl):
    """A second axis, so the first is not passing on a coincidence."""
    axis = aapl.axes_for_role(AAPL_EQUITY)["us-gaap_StatementEquityComponentsAxis"]

    assert axis.default_member_id == "us-gaap_EquityComponentDomain"


# ---------------------------------------------------------------------------
# .9 — Table.closed was a hardcoded literal
# ---------------------------------------------------------------------------

def test_closed_hypercube_is_reported_as_closed(aapl):
    """
    Apple files every `all` arc with `xbrldt:closed="true"`. A closed hypercube
    restricts which member combinations are valid, so reporting it as open
    permits combinations the filer excluded.
    """
    tables = aapl.tables[AAPL_OPERATIONS]

    assert [t.element_id for t in tables] == ["us-gaap_StatementTable"]
    assert tables[0].closed is True
    assert tables[0].context_element == "segment"


def test_absent_closed_attribute_still_defaults_to_open():
    """`xbrldt:closed` is optional and defaults to false — the control that
    separates "we read false" from "we never looked"."""
    link = _definition_link(
        "http://example.com/role/Open",
        _arc("all", "Items", "Table") + _arc("hypercube-dimension", "Table", "Axis"),
        _loc("Items") + _loc("Table") + _loc("Axis"),
    )

    parser = XBRLParser()
    parser.parse_definition_content(_linkbase(link))

    assert parser.tables["http://example.com/role/Open"][0].closed is False


def test_context_element_is_read_from_the_arc():
    """`xbrldt:contextElement` was hardcoded to "segment" beside `closed`."""
    link = _definition_link(
        "http://example.com/role/Scenario",
        _arc("all", "Items", "Table", **{"xbrldt:contextElement": "scenario"})
        + _arc("hypercube-dimension", "Table", "Axis"),
        _loc("Items") + _loc("Table") + _loc("Axis"),
    )

    parser = XBRLParser()
    parser.parse_definition_content(_linkbase(link))

    assert parser.tables["http://example.com/role/Scenario"][0].context_element == "scenario"


# ---------------------------------------------------------------------------
# .12 — the order attribute was extracted and then never used
# ---------------------------------------------------------------------------

def test_axes_follow_the_filed_order_not_document_order():
    """
    Three axes filed in the reverse of their `order` attribute. Filers use
    `order` to control presentation, so encounter order is arbitrary.
    """
    link = _definition_link(
        "http://example.com/role/Ordered",
        _arc("all", "Items", "Table")
        + _arc("hypercube-dimension", "Table", "AxisC", order="3")
        + _arc("hypercube-dimension", "Table", "AxisA", order="1")
        + _arc("hypercube-dimension", "Table", "AxisB", order="2"),
        _loc("Items") + _loc("Table") + _loc("AxisA") + _loc("AxisB") + _loc("AxisC"),
    )

    parser = XBRLParser()
    parser.parse_definition_content(_linkbase(link))

    assert parser.tables["http://example.com/role/Ordered"][0].axes == ["AxisA", "AxisB", "AxisC"]


def test_domain_members_follow_the_filed_order(aapl):
    """
    The same `order` attribute governs members. Apple files the equity
    rollforward in a deliberate sequence that is not alphabetical, so document
    order and filed order agreeing here is itself the check.
    """
    members = aapl.domains_for_role(AAPL_EQUITY)[EQUITY_ROLLFORWARD].members

    assert members[:3] == [
        "us-gaap_StockholdersEquity",
        "us-gaap_StockIssuedDuringPeriodValueNewIssues",
        "us-gaap_AdjustmentsRelatedToTaxWithholdingForShareBasedCompensation",
    ]


# ---------------------------------------------------------------------------
# Controls — the rework must not lose anything the old code found
# ---------------------------------------------------------------------------

def test_flat_views_still_cover_every_concept(aapl):
    """
    The flat `axes` / `domains` dicts predate this change and callers still read
    them. Apple's linkbase yields 24 axes, 52 domains and tables under 22 roles;
    role-scoping must not shrink any of those.
    """
    assert len(aapl.axes) == 24
    assert len(aapl.domains) == 52
    assert len(aapl.tables) == 22


def test_role_scoped_lookup_of_an_unknown_role_is_empty(aapl):
    """A role with no definition linkbase gets an empty mapping, not a KeyError."""
    assert aapl.axes_for_role("http://example.com/role/NotFiled") == {}
    assert aapl.domains_for_role("http://example.com/role/NotFiled") == {}
