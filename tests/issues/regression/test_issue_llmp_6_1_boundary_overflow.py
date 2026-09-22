"""Regression tests for edgartools-llmp.6.1 — pattern-path sections overshot their end.

`_create_sections` collected the nodes whose position fell in `[start, end)` and
attached the top-level ones to the section. A section's `end` is the position of
the *next* item's header, but that header is normally nested inside a container
which itself starts before it — so the container was in range, was attached
whole, and brought everything it held with it. The boundary was honoured as an
index and ignored as a content limit.

Wells Fargo's FY2024 10-K is the case that isolates this. Its computed
boundaries are provably correct — every section starts on its own item header
and ends on the next one, with no overlaps and no gaps — so anything extra is
attributable to node collection alone. Every item is a short
incorporation-by-reference pointer with a known correct length, and Item 8's
boundary span of 483-492 yielded 3,329 characters running through Items 9, 9A,
9B and 9C, because one container spanning 489-517 was attached to it.

20 of the filing's 23 sections carried a foreign item heading. The synthetic
tests show the same mechanism in four lines of HTML, where each section swallowed
the whole of the next.

Offline: Wells Fargo is a tracked fixture; the rest is inline HTML.
"""
import re
from pathlib import Path

import pytest

from edgar.documents import parse_html
from edgar.documents.config import ParserConfig

pytestmark = pytest.mark.fast

WFC = Path(__file__).parents[2] / "fixtures" / "html" / "wfc" / "10k" / "wfc-10-k-2025-02-25.html"

ITEM_HEADING = re.compile(r"ITEM\s+(\d+[A-C]?)\.", re.IGNORECASE)


def _normalise(text):
    return re.sub(r"\s+", " ", text or "").strip()


@pytest.fixture(scope="module")
def wfc_sections():
    assert WFC.exists(), f"committed Wells Fargo 10-K fixture is missing: {WFC}"
    doc = parse_html(WFC.read_bytes().decode("utf-8", "replace"), ParserConfig(form="10-K"))
    sections = {name: _normalise(section.text()) for name, section in doc.sections.items()}
    items = {name: section.item for name, section in doc.sections.items()}
    yield sections, items
    del doc


class TestWellsFargoDoesNotOvershoot:

    def test_no_section_carries_another_items_heading(self, wfc_sections):
        """The headline invariant: 20 of 23 sections failed this before."""
        sections, items = wfc_sections
        offenders = {}
        for name, text in sections.items():
            own = (items.get(name) or "").upper()
            foreign = sorted({h.upper() for h in ITEM_HEADING.findall(text)} - {own})
            if own and foreign:
                offenders[name] = foreign
        assert not offenders, f"sections carrying a foreign item heading: {offenders}"

    def test_item_8_is_the_by_reference_pointer_it_claims_to_be(self, wfc_sections):
        """3,329 chars before — Items 9, 9A, 9B and 9C rode in on one container."""
        sections, _ = wfc_sections
        text = sections["financial_statements"]
        assert "incorporated into this item by reference" in text
        assert len(text) < 1000, f"Item 8 over-captured: {len(text)} chars"
        for foreign in ("CONTROLS AND PROCEDURES", "Not applicable"):
            assert foreign not in text

    def test_reserved_item_6_is_just_its_heading(self, wfc_sections):
        sections, _ = wfc_sections
        assert sections["part_ii_item_6"].startswith("ITEM 6.")
        assert "RESERVED" in sections["part_ii_item_6"]
        assert "MANAGEMENT" not in sections["part_ii_item_6"]

    def test_every_section_opens_on_its_own_heading(self, wfc_sections):
        sections, items = wfc_sections
        for name, text in sections.items():
            item = items.get(name)
            if not item:
                continue
            assert text.upper().startswith(f"ITEM {item.upper()}."), (
                f"{name} does not open on its own heading: {text[:60]!r}")

    def test_no_content_is_lost_to_the_trim(self, wfc_sections):
        """Trimming must move text to the next section, never drop it."""
        sections, _ = wfc_sections
        for marker in ("MINE SAFETY DISCLOSURES", "CONTROLS AND PROCEDURES",
                       "OTHER INFORMATION", "FORM 10-K SUMMARY",
                       "MANAGEMENT’S DISCUSSION AND ANALYSIS"):
            assert any(marker in text for text in sections.values()), (
                f"{marker!r} is in no section at all")


# Each item's heading is wrapped in its own container, which is what puts the
# container's position inside the *previous* item's range.
WRAPPED_HEADINGS = """
<html><body>
<div><p><b>ITEM 1. BUSINESS</b></p><p>BUSINESS_BODY</p></div>
<div><p><b>ITEM 1A. RISK FACTORS</b></p><p>RISK_BODY</p></div>
<div><p><b>ITEM 2. PROPERTIES</b></p><p>PROPERTIES_BODY</p></div>
<div><p><b>ITEM 3. LEGAL PROCEEDINGS</b></p><p>LEGAL_BODY</p></div>
</body></html>
"""

BODIES = {
    "business": "BUSINESS_BODY",
    "risk_factors": "RISK_BODY",
    "properties": "PROPERTIES_BODY",
    "legal_proceedings": "LEGAL_BODY",
}


class TestWrappedHeadingsSynthetic:

    @pytest.fixture(scope="class")
    def sections(self):
        doc = parse_html(WRAPPED_HEADINGS, ParserConfig(form="10-K"))
        return {name: _normalise(section.text()) for name, section in doc.sections.items()}

    def test_all_four_items_are_detected_by_the_pattern_path(self, sections):
        assert set(sections) == set(BODIES)

    @pytest.mark.parametrize("name, body", sorted(BODIES.items()))
    def test_section_holds_its_own_body_and_no_other(self, sections, name, body):
        text = sections[name]
        assert body in text
        for other_name, other_body in BODIES.items():
            if other_name != name:
                assert other_body not in text, (
                    f"{name} swallowed {other_name}")

    def test_every_body_survives_somewhere(self, sections):
        """The trimmed remainder belongs to the next section, not to nobody."""
        for body in BODIES.values():
            assert sum(body in text for text in sections.values()) == 1


def test_a_container_wholly_inside_the_range_is_not_rebuilt():
    """Only a straddling container is replaced; the common case is untouched."""
    html = """
    <html><body>
    <div><p><b>ITEM 1. BUSINESS</b></p>
      <div><p>NESTED_ONE</p><p>NESTED_TWO</p></div>
    </div>
    <div><p><b>ITEM 2. PROPERTIES</b></p><p>PROPERTIES_BODY</p></div>
    </body></html>
    """
    doc = parse_html(html, ParserConfig(form="10-K"))
    business = _normalise(doc.sections["business"].text())
    assert "NESTED_ONE" in business and "NESTED_TWO" in business
    assert "PROPERTIES_BODY" not in business
