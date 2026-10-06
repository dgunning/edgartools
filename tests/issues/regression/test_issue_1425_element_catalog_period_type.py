"""
Regression test for GitHub issue #1425: the element catalog gave standard concepts placeholder metadata

A us-gaap, dei or srt concept reaches ``xbrl.element_catalog`` only through the
filer's label linkbase, because the schema that declares it is imported by the
filing rather than contained in it. Those entries were created with
``data_type=""``, ``period_type="duration"`` and ``balance=None`` whatever the
concept was, so every instant concept read as a duration and
``period_type == "instant"`` was never true for a standard concept. On Oracle's
10-Q for the period ended 2026-08-31 (0001193125-26-389274), 108 instant
concepts with facts, ``us-gaap_Assets`` among them, read "duration".

The period type now comes from the concept's own facts: XBRL 2.1 (5.1.1.1)
requires every fact of an instant concept to have an instant context, and every
fact of a duration concept a duration or forever one. What the filing cannot
say stays None rather than taking a value that reads as an answer: the period
type of a concept with no facts, and the data type and balance of any concept
declared outside the filing.

Ground truth is Apple's FY2023 10-K (0000320193-23-000106), committed under
tests/fixtures/xbrl/aapl/10k_2023. Its label linkbase gives 466 us-gaap concepts
a catalog entry and 305 of them have facts. All 305 period types were checked
against the FASB us-gaap 2023 taxonomy (us-gaap-2023.xsd): 141 instant and 164
duration, with no disagreement. The other 161 have no facts, and the taxonomy
declares every one of them abstract (abstracts, tables, axes, domains, members
and line items).

GitHub Issue: https://github.com/dgunning/edgartools/issues/1425
"""

from collections import Counter
from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.parsers import XBRLParser

AAPL_2023 = Path("tests/fixtures/xbrl/aapl/10k_2023")
SCHEMA = AAPL_2023 / "aapl-20230930.xsd"
LABELS = AAPL_2023 / "aapl-20230930_lab.xml"
INSTANCE = AAPL_2023 / "aapl-20230930_htm.xml"


def _parsed_in_from_filing_order():
    # XBRL.from_filing parses the schema and linkbases first and the instance last
    parser = XBRLParser()
    parser.parse_schema_content(SCHEMA.read_text(encoding="utf-8"))
    parser.parse_labels_content(LABELS.read_text(encoding="utf-8"))
    parser.parse_instance_content(INSTANCE.read_text(encoding="utf-8"))
    return parser.element_catalog


def _parsed_from_files():
    return XBRL.from_files(instance_file=INSTANCE, schema_file=SCHEMA, label_file=LABELS).element_catalog


def _parsed_from_directory():
    return XBRL.from_directory(AAPL_2023).element_catalog


@pytest.fixture(
    scope="module",
    params=[_parsed_in_from_filing_order, _parsed_from_files, _parsed_from_directory],
    ids=["from_filing_order", "from_files", "from_directory"],
)
def catalog(request):
    return request.param()


@pytest.mark.parametrize(
    "concept, period_type",
    [
        ("us-gaap_Assets", "instant"),
        ("us-gaap_StockholdersEquity", "instant"),
        ("us-gaap_NetIncomeLoss", "duration"),
        ("dei_EntityCommonStockSharesOutstanding", "instant"),
    ],
)
def test_standard_concept_has_the_period_type_its_facts_carry(catalog, concept, period_type):
    assert catalog[concept].period_type == period_type


def test_no_standard_instant_concept_reads_duration(catalog):
    """All 466 us-gaap entries read "duration" before the fix."""
    period_types = Counter(entry.period_type for name, entry in catalog.items() if name.startswith("us-gaap_"))

    assert period_types == {"instant": 141, "duration": 164, None: 161}


def test_what_the_filing_does_not_say_reads_none(catalog):
    """
    The half that stays open. The type and balance of a standard concept are
    declared in a schema the filing does not contain, and a concept with no
    facts carries no period type either. Filling them needs the taxonomy or the
    SEC's MetaLinks.json (GH #1426), which would give xbrli:monetaryItemType and
    debit for Assets and duration for StatementLineItems. Until then they read
    None, not "" or a "duration" that holds whatever the concept is.
    """
    assets = catalog["us-gaap_Assets"]
    line_items = catalog["us-gaap_StatementLineItems"]

    assert (assets.data_type, assets.balance) == (None, None)
    assert (line_items.data_type, line_items.period_type, line_items.balance) == (None, None, None)
    assert line_items.labels, "the entry still carries the filer's labels"


def test_filer_declared_concept_keeps_its_declaration(catalog):
    """The control: an extension concept is read from Apple's own schema, not from its facts."""
    entry = catalog["aapl_CashCashEquivalentsAndMarketableSecuritiesCost"]

    assert (entry.data_type, entry.period_type, entry.balance) == ("xbrli:monetaryItemType", "instant", "debit")


LABEL_LINKBASE = """<?xml version="1.0" encoding="UTF-8"?>
<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink">
  <link:labelLink xlink:type="extended" xlink:role="http://www.xbrl.org/2003/role/link">
    {labels}
  </link:labelLink>
</link:linkbase>"""

LABEL = """
    <link:loc xlink:type="locator" xlink:href="https://example.com/std-2024.xsd#std_{name}" xlink:label="loc_{name}"/>
    <link:label xlink:type="resource" xlink:label="lab_{name}" xlink:role="http://www.xbrl.org/2003/role/label"
                xml:lang="en-US">{name}</link:label>
    <link:labelArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/concept-label"
                   xlink:from="loc_{name}" xlink:to="lab_{name}"/>"""

INSTANCE_DOCUMENT = """<?xml version="1.0" encoding="UTF-8"?>
<xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:std="http://example.com/std/2024"
      xmlns:iso4217="http://www.xbrl.org/2003/iso4217">
  <context id="i"><entity><identifier scheme="http://www.sec.gov/CIK">0000000000</identifier></entity>
    <period><instant>2024-12-31</instant></period></context>
  <context id="d"><entity><identifier scheme="http://www.sec.gov/CIK">0000000000</identifier></entity>
    <period><startDate>2024-01-01</startDate><endDate>2024-12-31</endDate></period></context>
  <context id="f"><entity><identifier scheme="http://www.sec.gov/CIK">0000000000</identifier></entity>
    <period><forever/></period></context>
  <unit id="u"><measure>iso4217:USD</measure></unit>
  <std:Mixed contextRef="i" unitRef="u" decimals="0">1</std:Mixed>
  <std:Mixed contextRef="d" unitRef="u" decimals="0">2</std:Mixed>
  <std:Perpetual contextRef="f" unitRef="u" decimals="0">3</std:Perpetual>
</xbrl>"""


def test_facts_that_disagree_are_not_guessed_and_forever_is_a_duration():
    """
    An instance whose facts give one concept both an instant and a duration
    context is invalid XBRL; the period type stays unknown rather than taking
    whichever fact came first. A forever context is only allowed for a duration
    concept.
    """
    parser = XBRLParser()
    parser.parse_labels_content(LABEL_LINKBASE.format(labels=LABEL.format(name="Mixed") + LABEL.format(name="Perpetual")))
    parser.parse_instance_content(INSTANCE_DOCUMENT)

    assert parser.element_catalog["std_Mixed"].period_type is None
    assert parser.element_catalog["std_Perpetual"].period_type == "duration"
