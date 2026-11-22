"""
Regression test for GitHub issue #1761.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1761

A typed dimension's value is the content of the `xbrldi:typedMember` child
(XBRL Dimensions 1.0 section 3.1.4.4). Two defects:

  * element-only content (`<x:d><x:a>1</x:a></x:d>`) has no text of its own, so
    the parser fell back to the child's tag and every such context got the same
    value, `{http://example.com}d`;
  * `_find_facts_for_element` rewrote ':' to '_' in every dimension value, as
    if each were a member concept, so the typed value `10:30` became `10_30`.

The reproduction is the issue's synthetic instance. Microsoft's FY2024 10-K
(accession 0000950170-24-087843, tests/fixtures/xbrl/msft/10k_2024) guards the
common SEC case: a date-typed remaining-performance-obligation axis whose value
must stay exactly as filed. Over the 15 tracked fixture directories with typed
members, no context value or dimension key changes.
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL


def _context(cid, typed):
    return (f"<xbrli:context id='{cid}'><xbrli:entity><xbrli:identifier scheme='http://www.sec.gov/CIK'>1"
            f"</xbrli:identifier><xbrli:segment><xbrldi:typedMember dimension='x:D'>{typed}</xbrldi:typedMember>"
            "</xbrli:segment></xbrli:entity><xbrli:period><xbrli:instant>2026-09-30</xbrli:instant></xbrli:period>"
            "</xbrli:context>")


INSTANCE = (
    "<xbrli:xbrl xmlns:xbrli='http://www.xbrl.org/2003/instance' xmlns:xbrldi='http://xbrl.org/2006/xbrldi' "
    "xmlns:x='http://example.com' xmlns:iso4217='http://www.xbrl.org/2003/iso4217'>"
    + _context("c1", "<x:d><x:a>1</x:a></x:d>")
    + _context("c2", "<x:d>\n  <x:a>2</x:a>\n</x:d>")
    + _context("c3", "<x:t>10:30</x:t>")
    + "<xbrli:unit id='usd'><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>"
    + "".join(f"<x:m contextRef='{c}' unitRef='usd' decimals='0'>{v}</x:m>"
              for c, v in (("c1", 100), ("c2", 200), ("c3", 300)))
    + "</xbrli:xbrl>"
)


@pytest.fixture(scope="module")
def synthetic():
    x = XBRL()
    x.parser.parse_instance_content(INSTANCE)
    return x


@pytest.mark.fast
def test_element_only_typed_values_stay_distinct(synthetic):
    assert synthetic.contexts["c1"].dimensions == {"x:D": "<x:d><x:a>1</x:a></x:d>"}
    assert synthetic.contexts["c2"].dimensions == {"x:D": "<x:d><x:a>2</x:a></x:d>"}


@pytest.mark.fast
def test_typed_value_is_not_rewritten_as_a_concept_id(synthetic):
    found = synthetic._find_facts_for_element("x_m")
    keys = {cid: wrapped["dimension_key"] for cid, wrapped in found.items()}
    assert keys == {
        "c1": "x:D: <x:d><x:a>1</x:a></x:d>",
        "c2": "x:D: <x:d><x:a>2</x:a></x:d>",
        "c3": "x:D: 10:30",
    }
    assert synthetic.parser.typed_dimensions == {"x:D"}


@pytest.mark.fast
def test_msft_date_typed_value_is_kept_as_filed():
    xbrl = XBRL.from_directory(Path("tests/fixtures/xbrl/msft/10k_2024"))
    axis = "us-gaap:RevenueRemainingPerformanceObligationExpectedTimingOfSatisfactionStartDateAxis"
    context = xbrl.contexts["C_097df665-adbd-440a-b214-b2ac02a48fbc"]
    assert context.dimensions == {axis: "2024-07-01"}
    assert axis in xbrl.parser.typed_dimensions

    found = xbrl._find_facts_for_element("us-gaap_RevenueRemainingPerformanceObligationPercentage")
    wrapped = found["C_097df665-adbd-440a-b214-b2ac02a48fbc"]
    assert wrapped["fact"].value == "0.45"
    assert wrapped["dimension_info"][0]["member"] == "2024-07-01"
