"""
Regression test for edgartools-ga4a: a 20-F that writes its lettered items
with the letter as a separate token resolved no 16-series section at all.

20-F 0001062993-16-008650 (tracked at tests/fixtures/parity_gate/20-F/) heads
the series 'Item 16. A. Audit Committee Financial Expert' through
'Item 16. H. Mine Safety'. Every section pattern expected the letter attached
('Item 16A'), so all eight were missed. Two rows also restate the label in
their title cell, which the filer's HTML does itself:
``<td>Item 16.B.</td><td><b>Item 16.B. Code of Ethics.</b></td>`` and
``<td>Item 16.H.</td><td><b>H. Mine Safety</b></td>``.

``form_schema._item_no`` is now the one spelling of a lettered item number.
It accepts the split letter and one restatement, for every lettered item of
10-K, 10-Q and 20-F. Across the 128-filing parser corpus the change added these
eight sections and moved nothing else.
"""

import re

import pytest

from edgar.documents import HTMLParser, ParserConfig
from edgar.documents.form_schema import get_form_schema
from tests.paths import FIXTURES_DIR

GATE_20F = FIXTURES_DIR / "parity_gate" / "20-F" / "0001062993-16-008650.html"


@pytest.fixture(scope="module")
def sections():
    html = GATE_20F.read_text(encoding="utf-8", errors="replace")
    return HTMLParser(ParserConfig(form="20-F", detect_sections=True)).parse(html).sections


@pytest.mark.parametrize("key, opening", [
    ("item_16a", "Item 16. A. Audit Committee Financial Expert"),
    ("item_16b", "Item 16. B. Item 16. B. Code of Ethics."),
    ("item_16c", "Item 16. C. Principal Accountant Fees and Services"),
    ("item_16d", "Item 16. D. Exemptions from the Listing Standards for"),
    ("item_16e", "Item 16. E. Purchase of Equity Securities by the Issuer"),
    ("item_16f", "Item 16. F. Change in Registrant's Certifying"),
    ("item_16g", "Item 16. G. Corporate Governance"),
    ("item_16h", "Item 16. H. H. Mine Safety"),
])
def test_each_16_series_item_opens_on_its_heading(sections, key, opening):
    assert key in sections, f"{key} missing; got {sorted(sections)}"
    text = " ".join(sections[key].text().split())
    assert text.startswith(opening), text[:120]


def test_sections_end_before_the_next_item(sections):
    # Values read from the filing: 16A ends on the NYSE MKT independence
    # standard, 16C on the audit committee's approval, 16H on 'Not applicable.'
    assert " ".join(sections["item_16a"].text().split()).endswith(
        "Section 803A of the NYSE MKT Company Guide.")
    assert sections["item_16c"].text().rstrip().endswith("approved by the Audit Committee.")
    assert sections["item_16h"].text().rstrip().endswith("Not applicable.")
    assert "Item 16. B." not in sections["item_16a"].text()


@pytest.mark.parametrize("form, key, header", [
    ("10-K", "risk_factors", "Item 1A. Risk Factors"),
    ("10-K", "risk_factors", "ITEM 1. A. RISK FACTORS"),
    ("20-F", "item_16a", "ITEM 16A - Audit Committee Financial Expert"),
    ("20-F", "item_16k", "Item 16K. Cybersecurity"),
])
def test_lettered_items_match_attached_or_split(form, key, header):
    patterns = get_form_schema(form).section_patterns[key]
    assert any(re.match(p, header, re.IGNORECASE) for p, _ in patterns), header


@pytest.mark.parametrize("form, key, header", [
    # The split letter must not let one item's header claim another's slot.
    ("10-K", "risk_factors", "Item 1. Business"),
    ("20-F", "item_16a", "Item 16. Reserved"),
    ("20-F", "item_16b", "Item 16. A. Audit Committee Financial Expert"),
])
def test_split_letter_does_not_cross_items(form, key, header):
    patterns = get_form_schema(form).section_patterns[key]
    assert not any(re.match(p, header, re.IGNORECASE) for p, _ in patterns), header
