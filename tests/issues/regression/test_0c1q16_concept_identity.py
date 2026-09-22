"""
Regression tests for edgartools-0c1q.16 (cluster D): what identifies a thing.

  .4  gh #1188 — the expanded name (namespace URI + local name) identifies a
      concept and the prefix is a display choice, but the parser derived the
      prefix from the namespace URI's final path segment whenever the namespace
      was declared somewhere other than the instance root. Two taxonomies whose
      URIs end in the same segment collapsed into one concept string: both facts
      survived, their technical identity did not, and grouping by concept
      silently merged concepts from different taxonomies.
  .11 gh #1234 — `Axis.is_typed_dimension` and `Axis.typed_domain_ref` were
      declared on the model and never written by any code path, so every
      dimension read as explicit. A dimension is typed when its element
      declaration carries `xbrldt:typedDomainRef`; that is now read into the
      element catalog and onto the axis.

SCOPE, RECORDED DELIBERATELY. gh #1234 was triaged as "the root cause is a
missing xs:import/DTS traversal". That is only half true and the smaller half
first: even with a complete DTS traversal the fields would still have been
False, because `ElementCatalog` carried no field for it and `DefinitionParser`
read none. This closes the half that does not need the network — an axis the
filer declares in its own schema, which is where typed dimensions almost always
live. Following `xs:import` into a remote taxonomy is a separate capability
(every import in the fixture corpus is an absolute URL to xbrl.org, fasb.org or
xbrl.sec.gov) and stays open as edgartools-0c1q.16.1.

Coverage note: no fixture in the corpus contains a `typedDomainRef` at all, so
the typed case is synthetic. Explicit dimension declarations are real, and
Microsoft's FY2024 10-K carries one.
"""

from pathlib import Path

from edgar.xbrl.parsers import XBRLParser

AAPL_INSTANCE = Path("tests/fixtures/xbrl/aapl/10k_2023/aapl-20230930_htm.xml")
MSFT_SCHEMA = Path("tests/fixtures/xbrl/msft/10k_2024/msft-20240730.xsd")

ALPHA = "http://example.com/l01/alpha/2024"
BETA = "http://example.com/l01/beta/2024"


def _instance(facts: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<xbrl xmlns="http://www.xbrl.org/2003/instance"
      xmlns:xlink="http://www.w3.org/1999/xlink"
      xmlns:iso4217="http://www.xbrl.org/2003/iso4217">
  <context id="c1">
    <entity><identifier scheme="http://www.sec.gov/CIK">0000000000</identifier></entity>
    <period><instant>2024-12-31</instant></period>
  </context>
  <unit id="u1"><measure>iso4217:USD</measure></unit>
  {facts}
</xbrl>"""


def _concepts(parser: XBRLParser) -> set:
    return {fact.element_id for fact in parser.facts.values()}


# ---------------------------------------------------------------------------
# .4 — two namespaces collapsed into one concept string
# ---------------------------------------------------------------------------

def test_distinct_namespaces_keep_distinct_concepts():
    """
    The construct from gh #1188. Both URIs end in `/2024`, so the final path
    segment made both facts `2024:Collision` — two concepts from different
    taxonomies, indistinguishable.
    """
    parser = XBRLParser()
    parser.parse_instance_content(_instance(
        f'<a:Collision xmlns:a="{ALPHA}" contextRef="c1" unitRef="u1" decimals="0">1</a:Collision>'
        f'<b:Collision xmlns:b="{BETA}" contextRef="c1" unitRef="u1" decimals="0">2</b:Collision>'
    ))

    assert _concepts(parser) == {"a:Collision", "b:Collision"}


def test_each_concept_selects_only_its_own_fact():
    """
    The reporter's symptom stated as values: an exact query for either concept
    returned 0 rows, and the merged spelling returned both facts.
    """
    parser = XBRLParser()
    parser.parse_instance_content(_instance(
        f'<a:Collision xmlns:a="{ALPHA}" contextRef="c1" unitRef="u1" decimals="0">1</a:Collision>'
        f'<b:Collision xmlns:b="{BETA}" contextRef="c1" unitRef="u1" decimals="0">2</b:Collision>'
    ))
    by_concept = {}
    for fact in parser.facts.values():
        by_concept.setdefault(fact.element_id, []).append(fact.value)

    assert by_concept["a:Collision"] == ["1"]
    assert by_concept["b:Collision"] == ["2"]
    assert "2024:Collision" not in by_concept


def test_the_declared_prefix_is_used_wherever_it_is_declared():
    """
    A namespace declared on the fact element is as validly declared as one on
    the root. Its prefix is the filer's, not one invented from the URI.
    """
    parser = XBRLParser()
    parser.parse_instance_content(_instance(
        f'<mine:Revenue xmlns:mine="{ALPHA}" contextRef="c1" unitRef="u1" decimals="0">5</mine:Revenue>'
    ))

    assert _concepts(parser) == {"mine:Revenue"}


def test_undeclared_namespaces_are_still_kept_apart():
    """
    With no prefix declared anywhere the URI segment is all there is, so a
    segment already claimed by another namespace is suffixed rather than shared.
    Both concepts stay distinct even though neither has a name of its own.
    """
    parser = XBRLParser()
    parser.parse_instance_content(f"""<?xml version="1.0" encoding="UTF-8"?>
<xbrl xmlns="http://www.xbrl.org/2003/instance"
      xmlns:xlink="http://www.w3.org/1999/xlink"
      xmlns:iso4217="http://www.xbrl.org/2003/iso4217">
  <context id="c1">
    <entity><identifier scheme="http://www.sec.gov/CIK">0000000000</identifier></entity>
    <period><instant>2024-12-31</instant></period>
  </context>
  <unit id="u1"><measure>iso4217:USD</measure></unit>
  <Collision xmlns="{ALPHA}" contextRef="c1" unitRef="u1" decimals="0">1</Collision>
  <Collision xmlns="{BETA}" contextRef="c1" unitRef="u1" decimals="0">2</Collision>
</xbrl>""")

    assert len(_concepts(parser)) == 2


def test_real_filing_concept_strings_are_untouched():
    """
    The control. Apple's FY2023 10-K declares every namespace on the instance
    root, like almost every filing, so resolving prefixes properly must return
    exactly the concept strings it already returned — 1,164 facts over 394
    distinct concepts.
    """
    parser = XBRLParser()
    parser.parse_instance_content(AAPL_INSTANCE.read_text())

    concepts = _concepts(parser)
    assert len(parser.facts) == 1164
    assert len(concepts) == 394
    assert "us-gaap:Assets" in concepts
    assert not any(c.startswith("2023:") for c in concepts)


# ---------------------------------------------------------------------------
# .11 — the typed-dimension fields were never written by anything
# ---------------------------------------------------------------------------

def _schema(elements: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
            xmlns:xbrli="http://www.xbrl.org/2003/instance"
            xmlns:xbrldt="http://xbrl.org/2005/xbrldt"
            targetNamespace="http://example.com/ext">
  {elements}
</xsd:schema>"""


def _definition(arcs: str, locators: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<linkbase xmlns="http://www.xbrl.org/2003/linkbase"
          xmlns:xlink="http://www.w3.org/1999/xlink">
  <definitionLink xlink:type="extended" xlink:role="http://example.com/role/R">
    {locators}
    {arcs}
  </definitionLink>
</linkbase>"""


def _typed_axis_parser() -> XBRLParser:
    parser = XBRLParser()
    parser.parse_schema_content(_schema(
        '<xsd:element id="ext_TypedAxis" name="TypedAxis" type="xbrli:stringItemType"'
        ' substitutionGroup="xbrldt:dimensionItem" xbrli:periodType="duration"'
        ' abstract="true" xbrldt:typedDomainRef="#ext_TypedDomain"/>'
        '<xsd:element id="ext_PlainAxis" name="PlainAxis" type="xbrli:stringItemType"'
        ' substitutionGroup="xbrldt:dimensionItem" xbrli:periodType="duration"'
        ' abstract="true"/>'
    ))
    locators = ''.join(
        f'<loc xlink:type="locator" xlink:href="ext.xsd#{label}" xlink:label="{label}"/>'
        for label in ("ext_Table", "ext_TypedAxis", "ext_PlainAxis")
    )
    arcs = ''.join(
        '<definitionArc xlink:type="arc" '
        'xlink:arcrole="http://xbrl.org/int/dim/arcrole/hypercube-dimension" '
        f'xlink:from="ext_Table" xlink:to="{axis}"/>'
        for axis in ("ext_TypedAxis", "ext_PlainAxis")
    )
    parser.parse_definition_content(_definition(arcs, locators))
    return parser


def test_a_typed_dimension_is_reported_as_typed():
    """
    `xbrldt:typedDomainRef` on the declaration is what makes a dimension typed.
    Nothing read it, so every dimension was explicit.
    """
    axis = _typed_axis_parser().axes["ext_TypedAxis"]

    assert axis.is_typed_dimension is True
    assert axis.typed_domain_ref == "#ext_TypedDomain"


def test_an_explicit_dimension_is_still_explicit():
    """The control that separates "we read false" from "we never looked"."""
    axis = _typed_axis_parser().axes["ext_PlainAxis"]

    assert axis.is_typed_dimension is False
    assert axis.typed_domain_ref == ""


def test_the_element_catalog_carries_the_declaration():
    """
    The catalog is where the answer has to live for the definition parser to
    reach it, and it had no field for it at all.
    """
    parser = XBRLParser()
    parser.parse_schema_content(_schema(
        '<xsd:element id="ext_TypedAxis" name="TypedAxis" type="xbrli:stringItemType"'
        ' substitutionGroup="xbrldt:dimensionItem" xbrli:periodType="duration"'
        ' xbrldt:typedDomainRef="#ext_TypedDomain"/>'
    ))
    element = parser.element_catalog["ext_TypedAxis"]

    assert element.typed_domain_ref == "#ext_TypedDomain"
    assert element.substitution_group == "xbrldt:dimensionItem"


def test_a_real_filer_declared_dimension_reads_as_explicit():
    """
    Microsoft's FY2024 10-K declares `msft_ProductsOrServicesSecondaryCategorizationAxis`
    as an explicit dimension in its own schema. It is in the catalog, so False
    here is an answer rather than an untouched default.
    """
    parser = XBRLParser()
    parser.parse_schema_content(MSFT_SCHEMA.read_text())
    element = parser.element_catalog["msft_ProductsOrServicesSecondaryCategorizationAxis"]

    assert element.substitution_group == "xbrldt:dimensionItem"
    assert element.typed_domain_ref is None


def test_an_axis_outside_the_catalog_still_reads_as_explicit():
    """
    The half that stays open. An axis declared only in an imported taxonomy
    never reaches the element catalog, because there is no xs:import traversal,
    so it still reports False — see edgartools-0c1q.16.1.
    """
    parser = XBRLParser()
    locators = ''.join(
        f'<loc xlink:type="locator" xlink:href="ext.xsd#{label}" xlink:label="{label}"/>'
        for label in ("ext_Table", "us-gaap_ImportedAxis")
    )
    arcs = ('<definitionArc xlink:type="arc" '
            'xlink:arcrole="http://xbrl.org/int/dim/arcrole/hypercube-dimension" '
            'xlink:from="ext_Table" xlink:to="us-gaap_ImportedAxis"/>')
    parser.parse_definition_content(_definition(arcs, locators))

    assert "us-gaap_ImportedAxis" not in parser.element_catalog
    assert parser.axes["us-gaap_ImportedAxis"].is_typed_dimension is False
