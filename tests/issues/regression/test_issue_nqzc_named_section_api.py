"""Named-section API surface: Section.kind, Sections.named(), report.signatures.

edgartools-nqzc Layer 1/2. Once a named section (Signatures) reaches
``document.sections`` (Layer 0), callers need to find and use it without
guessing the part-prefixed key. This adds:

* ``Section.kind`` -- 'item' for a numbered SEC item, else 'named', so iteration
  can distinguish a real Item from Signatures without string-matching the key.
* ``Sections.named(name)`` -- the get_item companion for non-item sections;
  resolves "signatures" -> "part_iv_signatures" (or a bare key), case-insensitive.
* ``CompanyReport.signatures`` -- a convenience accessor parallel to .business /
  .risk_factors. Signatures stays out of ``items`` (it is not an SEC Item).

The unit tests build synthetic Section objects (offline). The end-to-end
property is exercised in test_issue_837_workiva_item1_missing under VCR.
"""
import pytest

from edgar.documents.document import Section, Sections
from edgar.documents.nodes import SectionNode

pytestmark = [pytest.mark.fast, pytest.mark.regression]


def _section(name, title, item=None, part=None):
    return Section(name=name, title=title, node=SectionNode(section_name=name),
                   item=item, part=part)


@pytest.fixture
def sections():
    return Sections({
        "part_i_item_1": _section("part_i_item_1", "Business", item="1", part="I"),
        "part_ii_item_9c": _section("part_ii_item_9c", "Disclosure", item="9C", part="II"),
        "part_iv_signatures": _section("part_iv_signatures", "Signatures"),
    })


class TestSectionKind:
    def test_numbered_item_is_kind_item(self, sections):
        assert sections["part_i_item_1"].kind == "item"
        assert sections["part_ii_item_9c"].kind == "item"

    def test_named_section_is_kind_named(self, sections):
        assert sections["part_iv_signatures"].kind == "named"


class TestSectionsNamed:
    def test_resolves_part_prefixed_named_section(self, sections):
        sig = sections.named("signatures")
        assert sig is sections["part_iv_signatures"]

    def test_is_case_and_space_insensitive(self, sections):
        assert sections.named("Signatures") is sections["part_iv_signatures"]
        assert sections.named("  SIGNATURES ") is sections["part_iv_signatures"]

    def test_resolves_bare_named_key(self):
        bare = Sections({"signatures": _section("signatures", "Signatures")})
        assert bare.named("signatures") is bare["signatures"]

    def test_does_not_match_items(self, sections):
        """A numbered item is never returned by named() even by friendly name."""
        assert sections.named("business") is None

    def test_missing_named_section_returns_none(self, sections):
        assert sections.named("glossary") is None
