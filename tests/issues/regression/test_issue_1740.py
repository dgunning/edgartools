"""ConceptGraph.validate() silently dropped a total when one calculation child had no value.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1740

``_validate_recursive`` stopped summing at the first child with no number in
the validated report and appended no result for the parent, so a total whose
other contributors were all reported was never checked and an empty failure
list read as clean. XBRL 2.1 section 5.2.5.2 excludes nil and absent facts from
the contributing items and binds a calculation when at least one contributor
is present, so the check now sums the contributors that are shown and lists the
ones that are not in ``missing_children``. A total with no contributor at all
is still not checked.

Ground truth: Apple 10-Q for the quarter ended 2025-03-29, accession
0000320193-25-000057 (fixture tests/fixtures/attachments/aapl/20250329).
The balance sheet (R4) reports total liabilities and shareholders' equity of
$331,233M = liabilities $264,437M + shareholders' equity $66,796M; the third
calculation child, us-gaap:CommitmentsAndContingencies (fact f-214), is nil.
The comprehensive income statement (R3) reports other comprehensive income of
$426M = 90 + 1,282 - 946; Apple's custom derivative concept has only a prior
year value there. Before the fix neither total was in the results.
"""
import re
from pathlib import Path

import pytest

from edgar.sgml.concept_extractor import ConceptReport, ConceptRow, extract_concepts_from_report
from edgar.sgml.metalinks import CalculationEntry, MetaLinks, MetaLinksReport, TagDefinition
from edgar.xbrl.concept_graph import ConceptGraph

pytestmark = pytest.mark.fast

FIXTURE = Path("tests/fixtures/attachments/aapl/20250329")


@pytest.fixture(scope="module")
def results():
    metalinks = MetaLinks.parse((FIXTURE / "MetaLinks.json").read_text())
    r_files = sorted(FIXTURE.glob("R*.htm"), key=lambda p: int(re.sub(r"\D", "", p.stem)))
    reports = {p.stem: extract_concepts_from_report(p.read_text()) for p in r_files}
    return {r["parent"].id: r for r in ConceptGraph.build(metalinks, reports).validate()}


def test_balance_sheet_identity_is_checked_without_the_nil_child(results):
    total = results["us-gaap_LiabilitiesAndStockholdersEquity"]
    assert total["expected"] == 331233.0
    assert total["computed"] == 331233.0          # 264,437 + 66,796
    assert total["valid"] is True
    assert total["missing_children"] == ["us-gaap_CommitmentsAndContingencies"]


def test_oci_total_is_checked_without_the_prior_year_only_child(results):
    total = results["us-gaap_OtherComprehensiveIncomeLossNetOfTaxPortionAttributableToParent"]
    assert total["expected"] == 426.0
    assert total["computed"] == 426.0             # 90 + 1,282 - 946
    assert total["valid"] is True
    assert total["missing_children"] == [
        "aapl_OtherComprehensiveIncomeLossDerivativeInstrumentGainLossafterReclassificationandTax"]


def test_complete_checks_list_no_missing_children(results):
    assert results["us-gaap_Assets"]["missing_children"] == []


def _graph(children):
    """A total of 100 with weight-1 children; None is a child with no reported value."""
    role = "https://example.com/role/BS"
    names = ["ex_Total"] + [f"ex_Part{i}" for i in range(len(children))]
    tags, rows = {}, []
    for i, (name, value) in enumerate(zip(names, [100] + children, strict=True)):
        entry = CalculationEntry(role, None if i == 0 else names[0], None if i == 0 else 1, i, i == 0)
        tags[name] = TagDefinition(name, "monetaryItemType", "https://example.com", name[3:], "debit",
                                   name, name, None, "", [role], {role: entry}, [])
        if value is not None:
            rows.append(ConceptRow(name, name, {"2025-03-29": str(value)}, False, i == 0, False, i,
                                   "re", "2025-03-29"))
    report = MetaLinksReport("R1", role, "Balance Sheet", "Balance Sheet", "Statements", "", "Statements",
                             1, None, None)
    meta = MetaLinks("2.2", "ex.htm", tags, {"R1": report}, {}, {})
    return ConceptGraph.build(meta, {"R1": ConceptReport("Balance Sheet", ["2025-03-29"], rows)})


def test_missing_contributor_does_not_hide_an_imbalance():
    [result] = _graph([60, 30, None]).validate()
    assert result["expected"] == 100.0
    assert result["computed"] == 90.0
    assert result["difference"] == 10.0
    assert result["valid"] is False
    assert result["missing_children"] == ["ex_Part2"]


def test_total_with_no_reported_contributor_is_not_checked():
    assert _graph([None, None]).validate() == []
