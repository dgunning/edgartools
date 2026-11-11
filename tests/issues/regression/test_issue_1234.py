"""
Regression test for GitHub issue #1234 (partial).

GitHub Issue: https://github.com/dgunning/edgartools/issues/1234

An axis declared only in an imported taxonomy (the US-GAAP schema, never
loaded: there is no xs:import traversal) reported `is_typed_dimension=False`
although the instance used it through `xbrldi:typedMember`. Only a typed
dimension may carry a typedMember (XBRL Dimensions 1.0 section 3.1.4.4), so the
instance settles the axis's kind. `typed_domain_ref` stays '' because the
declaration that holds it is still never read -- that half waits for DTS
import traversal (edgartools-0c1q.16.1).

Ground truth: Apple's FY2023 10-K, accession 0000320193-23-000106, tracked at
tests/fixtures/xbrl/aapl/10k_2023. Its instance carries four typedMember
contexts on us-gaap:RevenueRemainingPerformanceObligationExpectedTimingOfSatisfactionStartDateAxis
(2023-10-01, 2024-09-29, 2025-09-28, 2026-09-27); Apple's extension schema does
not declare the axis.
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.parsers import XBRLParser

AAPL_DIR = Path("tests/fixtures/xbrl/aapl/10k_2023")
RPO_AXIS = "us-gaap_RevenueRemainingPerformanceObligationExpectedTimingOfSatisfactionStartDateAxis"


@pytest.mark.fast
def test_imported_typed_axis_is_typed():
    xbrl = XBRL.from_directory(AAPL_DIR)
    typed_values = sorted(context.dimensions[RPO_AXIS.replace("_", ":", 1)]
                          for context in xbrl.contexts.values()
                          if RPO_AXIS.replace("_", ":", 1) in context.dimensions)
    assert typed_values == ["2023-10-01", "2024-09-29", "2025-09-28", "2026-09-27"]

    axis = xbrl.axes[RPO_AXIS]
    assert axis.is_typed_dimension is True
    assert axis.typed_domain_ref == ""  # the declaration was never loaded
    for role_axes in xbrl.parser.axes_by_role.values():
        if RPO_AXIS in role_axes:
            assert role_axes[RPO_AXIS].is_typed_dimension is True


@pytest.mark.fast
def test_explicit_axes_stay_explicit():
    xbrl = XBRL.from_directory(AAPL_DIR)
    typed = sorted(axis_id for axis_id, axis in xbrl.axes.items() if axis.is_typed_dimension)
    assert typed == [RPO_AXIS]
    assert xbrl.axes["srt_ProductOrServiceAxis"].is_typed_dimension is False


DEFINITION = '''<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase"
 xmlns:xlink="http://www.w3.org/1999/xlink">
 <link:definitionLink xlink:type="extended" xlink:role="http://example.com/role/R">
  <link:loc xlink:type="locator" xlink:label="items" xlink:href="t.xsd#x_LineItems"/>
  <link:loc xlink:type="locator" xlink:label="cube" xlink:href="t.xsd#x_Table"/>
  <link:loc xlink:type="locator" xlink:label="axis" xlink:href="t.xsd#x_D"/>
  <link:definitionArc xlink:type="arc" xlink:from="items" xlink:to="cube" xlink:arcrole="http://xbrl.org/int/dim/arcrole/all"/>
  <link:definitionArc xlink:type="arc" xlink:from="cube" xlink:to="axis" xlink:arcrole="http://xbrl.org/int/dim/arcrole/hypercube-dimension"/>
 </link:definitionLink>
</link:linkbase>'''

INSTANCE = ("<xbrli:xbrl xmlns:xbrli='http://www.xbrl.org/2003/instance' xmlns:xbrldi='http://xbrl.org/2006/xbrldi' "
            "xmlns:x='http://example.com'><xbrli:context id='c1'><xbrli:entity>"
            "<xbrli:identifier scheme='http://www.sec.gov/CIK'>1</xbrli:identifier><xbrli:segment>"
            "<xbrldi:typedMember dimension='x:D'><x:d>7</x:d></xbrldi:typedMember></xbrli:segment></xbrli:entity>"
            "<xbrli:period><xbrli:instant>2026-09-30</xbrli:instant></xbrli:period></xbrli:context></xbrli:xbrl>")


@pytest.mark.fast
@pytest.mark.parametrize("instance_first", [False, True])
def test_read_order_does_not_matter(instance_first):
    parser = XBRLParser()
    if instance_first:
        parser.parse_instance_content(INSTANCE)
        parser.parse_definition_content(DEFINITION)
    else:
        parser.parse_definition_content(DEFINITION)
        parser.parse_instance_content(INSTANCE)
    assert parser.axes["x_D"].is_typed_dimension is True
    assert parser.axes_for_role("http://example.com/role/R")["x_D"].is_typed_dimension is True
