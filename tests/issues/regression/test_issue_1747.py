"""
Regression test for GitHub issue #1747.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1747

A unit with several sibling `xbrli:measure` children is their product (XBRL 2.1
section 4.8.2, example 20: square feet is feet x feet), but the instance parser
kept only the first measure, so feet x feet read as feet and USD x shares read
as plain USD -- which the currency helpers then treated as a dollar amount.

No tracked fixture has a product unit (0 of 269 units across 38 instance
files), matching the issue's 0 in 80 sampled SEC instances, so the product case
is synthetic. Apple's FY2023 10-K (accession 0000320193-23-000106) guards the
single-measure and divided units every filing uses.
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.core import unit_currency, unit_currency_measure
from edgar.xbrl.parsers import XBRLParser

INSTANCE = """<?xml version="1.0" encoding="utf-8"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
    xmlns:my="http://example.com/my" xmlns:iso4217="http://www.xbrl.org/2003/iso4217">
  <xbrli:context id="c1">
    <xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0000000001</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:instant>2025-12-31</xbrli:instant></xbrli:period>
  </xbrli:context>
  <xbrli:unit id="sqft"><xbrli:measure>my:feet</xbrli:measure><xbrli:measure>my:feet</xbrli:measure></xbrli:unit>
  <xbrli:unit id="usdShares"><xbrli:measure>iso4217:USD</xbrli:measure>
    <xbrli:measure> xbrli:shares </xbrli:measure></xbrli:unit>
  <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
  <my:Area contextRef="c1" unitRef="sqft" decimals="0">1000</my:Area>
</xbrli:xbrl>
"""


@pytest.fixture(scope="module")
def units():
    parser = XBRLParser()
    parser.parse_instance_content(INSTANCE)
    return parser.units


@pytest.mark.fast
def test_product_unit_keeps_every_measure_including_repeats(units):
    assert units["sqft"] == {"type": "product", "measures": ["my:feet", "my:feet"],
                             "definition": {"numerator": ["{http://example.com/my}feet", "{http://example.com/my}feet"], "denominator": [], "expression": "my:feet*my:feet"}}
    assert units["usdShares"] == {"type": "product", "measures": ["iso4217:USD", "xbrli:shares"],
                                  "definition": {"numerator": ["{http://www.xbrl.org/2003/iso4217}USD", "{http://www.xbrl.org/2003/instance}shares"], "denominator": [], "expression": "iso4217:USD*xbrli:shares"}}


@pytest.mark.fast
def test_product_with_a_currency_factor_is_not_a_currency(units):
    assert unit_currency(units["usdShares"]) is None
    assert unit_currency_measure(units["usdShares"]) is None
    # The single-measure unit beside it still is one.
    assert units["usd"] == {"type": "simple", "measure": "iso4217:USD", "definition": {"numerator": ["{http://www.xbrl.org/2003/iso4217}USD"], "denominator": [], "expression": "iso4217:USD"}}
    assert unit_currency(units["usd"]) == "USD"


@pytest.mark.fast
def test_real_filing_units_are_unchanged():
    xbrl = XBRL.from_directory(Path("tests/fixtures/xbrl/aapl/10k_2023"))
    assert xbrl.units["usd"] == {"type": "simple", "measure": "iso4217:USD", "definition": {"numerator": ["{http://www.xbrl.org/2003/iso4217}USD"], "denominator": [], "expression": "iso4217:USD"}}
    # filed unprefixed, under the default (XBRL instance) namespace
    assert xbrl.units["shares"] == {"type": "simple", "measure": "shares", "definition": {"numerator": ["{http://www.xbrl.org/2003/instance}shares"], "denominator": [], "expression": "shares"}}
    assert xbrl.units["usdPerShare"] == {"type": "divide", "numerator": ["iso4217:USD"],
                                         "denominator": ["shares"],
                                         "definition": {"numerator": ["{http://www.xbrl.org/2003/iso4217}USD"], "denominator": ["{http://www.xbrl.org/2003/instance}shares"], "expression": "iso4217:USD/shares"}}
    assert not [u for u in xbrl.units.values() if u["type"] == "product"]
