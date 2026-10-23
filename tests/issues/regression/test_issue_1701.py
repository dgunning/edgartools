"""Regression: dimensional rows nest by the statement role's own domain-member arcs.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1701

`XBRL._apply_member_hierarchy` read `parser.domains`, the union of domain-member
relationships across every role, although the statement role is known. Tesla's
10-Q (0001628280-26-049270) nests tsla:ServicesAndOtherMember under
tsla:SalesAndServicesMember in a note, but its Consolidated Statements of
Operations role declares no SalesAndServicesMember at all: there
srt:ProductsAndServicesDomain has the children AutomotiveRevenuesMember,
EnergyGenerationAndStorageMember and ServicesAndOtherMember. The DETAILED income
statement still put "Services and other" ($4,581M) one level below "Total revenues
from sales and services" ($27,731M).

With a statement role, the hierarchy now comes from `domains_for_role(role)`
(XBRL Dimensions 1.0 section 2.4); a call without a role keeps the union.
"""

from types import SimpleNamespace

import pytest

from edgar.httprequests import download_file
from edgar.xbrl import XBRL
from edgar.xbrl.presentation import StatementView


def _row(label, member):
    return {"label": label, "level": 5,
            "dimension_metadata": [{"dimension": "srt:ProductOrServiceAxis", "member": member}]}


def _dummy():
    note_union = {"m_SalesAndServices": SimpleNamespace(members=["m_Automotive", "m_Services"])}
    statement_role = {"m_Automotive": SimpleNamespace(members=["m_AutomotiveSales"])}
    return SimpleNamespace(parser=SimpleNamespace(
        domains=note_union,
        domains_for_role=lambda role: statement_role if role == "role/Operations" else {},
    ))


def _items():
    return [
        _row("Automotive", "m_Automotive"),
        _row("Automotive sales", "m_AutomotiveSales"),
        _row("Sales and services", "m_SalesAndServices"),
        _row("Services", "m_Services"),
    ]


def test_statement_role_hierarchy_ignores_other_roles_members():
    items = _items()
    XBRL._apply_member_hierarchy(_dummy(), items, "role/Operations")
    assert [(item["label"], item["level"]) for item in items] == [
        ("Automotive", 5),
        ("Automotive sales", 6),
        ("Sales and services", 5),
        ("Services", 5),
    ]


def test_role_without_domain_member_arcs_falls_back_to_the_union():
    items = _items()
    XBRL._apply_member_hierarchy(_dummy(), items, "role/NoDefinitionNetwork")
    levels = {item["label"]: item["level"] for item in items}
    assert levels["Services"] == 6
    assert levels["Automotive"] == 6


def test_without_a_role_the_union_is_still_used():
    items = _items()
    XBRL._apply_member_hierarchy(_dummy(), items)
    levels = {item["label"]: item["level"] for item in items}
    assert levels["Services"] == 6


TSLA_FOLDER = "https://www.sec.gov/Archives/edgar/data/1318605/000162828026049270/"
TSLA_FILES = ("tsla-20260630.xsd", "tsla-20260630_htm.xml", "tsla-20260630_pre.xml",
              "tsla-20260630_lab.xml", "tsla-20260630_def.xml")
OPERATIONS = "http://www.tesla.com/role/ConsolidatedStatementsofOperations"


@pytest.mark.vcr
def test_tesla_services_and_other_is_a_sibling_of_automotive_revenues(tmp_path):
    """Ground truth: Tesla 10-Q, 0001628280-26-049270, Consolidated Statements of Operations."""
    for name in TSLA_FILES:
        (tmp_path / name).write_text(download_file(TSLA_FOLDER + name), encoding="utf-8")
    xbrl = XBRL.from_directory(tmp_path)

    in_role = xbrl.domains_for_role(OPERATIONS)
    assert "tsla_SalesAndServicesMember" not in in_role
    assert in_role["srt_ProductsAndServicesDomain"].members == [
        "tsla_AutomotiveRevenuesMember", "tsla_EnergyGenerationAndStorageMember", "tsla_ServicesAndOtherMember"]

    rows = []
    for item in xbrl.get_statement(OPERATIONS, view=StatementView.DETAILED):
        if item["label"].startswith("Cost of revenues"):
            break
        rows.append(item)
    by_label = {item["label"]: item for item in rows}

    services = by_label["Services and other"]
    automotive = by_label["Automotive Revenues"]
    assert services["values"]["duration_2026-04-01_2026-06-30"] == 4_581_000_000
    assert automotive["values"]["duration_2026-04-01_2026-06-30"] == 20_516_000_000
    assert services["level"] == automotive["level"]
    assert by_label["Automotive sales"]["level"] == automotive["level"] + 1
