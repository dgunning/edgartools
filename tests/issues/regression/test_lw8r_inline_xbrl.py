"""
Inline XBRL extraction in edgar/documents (bead edgartools-lw8r).

parse_html()'s iXBRL support was wired up only at the shallowest level: raw ref
strings and leading display text were captured, every semantic resolution step
was absent or wrong, and the data that WAS captured never reached the public
API. Seven reports, one coherent failure mode - every one of them silent.

Covers gh #1232, #1233, #1237, #1239, #1250, #1251 and #1189.

Assertions are against the raw iXBRL source or hand-checked filing values, not
against parser output: asserting against the parser is what let this survive.
"""

from decimal import Decimal
from pathlib import Path

import pytest

from edgar.documents import ParserConfig, parse_html
from edgar.documents.strategies.ixbrl_transforms import (
    TransformError,
    UnknownTransformError,
    apply_scale,
    apply_transform,
    normalize_format,
)

CONFIG = ParserConfig(extract_xbrl=True, detect_sections=False)

# A tracked real filing, used as the ground-truth anchor. Caterpillar rather
# than Apple: a different industry, and its cover page exercises the state,
# exchange, filer-category, ballot-box and date transforms in one document.
CAT_10K = (Path(__file__).parents[2] / 'fixtures' / 'html' / 'cat' / '10k'
           / 'cat-10-k-2025-02-14.html')


def parse(html: str):
    return parse_html(html, CONFIG)


# ---------------------------------------------------------------------------
# gh #1232 - context and unit references never resolved
# ---------------------------------------------------------------------------

CONTEXT_HTML = """<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
      xmlns:xbrli="http://www.xbrl.org/2003/instance"
      xmlns:xbrldi="http://xbrl.org/2006/xbrldi">
<body><ix:header><ix:hidden>
  <xbrli:context id="D2024">
    <xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0000018230</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:startDate>2024-01-01</xbrli:startDate><xbrli:endDate>2024-12-31</xbrli:endDate></xbrli:period>
  </xbrli:context>
  <xbrli:context id="I2024">
    <xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0000018230</xbrli:identifier>
      <xbrli:segment>
        <xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">cat:EnergyMember</xbrldi:explicitMember>
      </xbrli:segment>
    </xbrli:entity>
    <xbrli:period><xbrli:instant>2024-12-31</xbrli:instant></xbrli:period>
  </xbrli:context>
  <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
  <xbrli:unit id="usdPerShare"><xbrli:divide>
      <xbrli:unitNumerator><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unitNumerator>
      <xbrli:unitDenominator><xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unitDenominator>
  </xbrli:divide></xbrli:unit>
</ix:hidden></ix:header>
<p><ix:nonFraction name="us-gaap:Revenues" contextRef="D2024" unitRef="usd" decimals="-6">61,363</ix:nonFraction></p>
<p><ix:nonFraction name="us-gaap:EarningsPerShareBasic" contextRef="I2024" unitRef="usdPerShare" decimals="2">22.17</ix:nonFraction></p>
</body></html>"""


def test_context_and_unit_references_resolve():
    """
    gh #1232: the resolution branch was never entered.

    _extract_contexts/_extract_units used namespace-aware XPath (//xbrli:context)
    against a tree from lxml.html.fromstring(), whose elements carry the LITERAL
    tag "xbrli:context" and no namespace URI, so the XPath matched nothing and
    self.contexts/self.units stayed permanently empty. Every fact's .context and
    .unit came back None while the raw refs sat right there on the fact.
    """
    facts = {f.concept: f for f in parse(CONTEXT_HTML).metadata.xbrl_data}

    revenues = facts['us-gaap:Revenues']
    assert revenues.context_ref == 'D2024'
    assert revenues.context is not None, "contextRef present but never resolved"
    assert revenues.context['period_type'] == 'duration'
    assert revenues.context['start_date'] == '2024-01-01'
    assert revenues.context['end_date'] == '2024-12-31'
    assert revenues.context['entity'] == '0000018230'
    assert revenues.unit == 'USD'

    eps = facts['us-gaap:EarningsPerShareBasic']
    assert eps.context['period_type'] == 'instant'
    assert eps.context['instant'] == '2024-12-31'
    assert eps.context['dimensions'] == {
        'us-gaap:StatementBusinessSegmentsAxis': 'cat:EnergyMember'
    }
    # A divide unit contains measures too, so checking for a measure first
    # would have resolved this as plain "USD".
    assert eps.unit == 'USD/shares'


# ---------------------------------------------------------------------------
# gh #1189 / #1239 / #1237 - _get_fact_value read only element.text
# ---------------------------------------------------------------------------

CONTINUATION_HTML = """<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">
<body>
<p><ix:nonNumeric name="us-gaap:TwoHop" contextRef="c1" continuedAt="k1">Alpha <b>nested beta</b> tail</ix:nonNumeric></p>
<p><ix:continuation id="k1">gamma</ix:continuation></p>
<p><ix:nonNumeric name="us-gaap:OneHop" contextRef="c1" continuedAt="k2">First disclosure sentence.</ix:nonNumeric></p>
<p><ix:continuation id="k2">Second disclosure sentence.</ix:continuation></p>
<p><ix:nonNumeric name="us-gaap:Excluded" contextRef="c1">Keep <ix:exclude>DROP</ix:exclude> after</ix:nonNumeric></p>
</body></html>"""


def test_continuation_chains_are_followed():
    """
    gh #1189: continuedAt chains truncated to the origin element's leading text.

    element.text is only the text node before the first child, so descendant
    markup, tail text and the whole continuation chain were dropped - and the
    truncated string looked like a complete value. continuedAt is how issuers
    split long narrative disclosures, so this fell on exactly the text an LLM
    reads.
    """
    facts = {f.concept: f for f in parse(CONTINUATION_HTML).metadata.xbrl_data}

    assert facts['us-gaap:TwoHop'].value == 'Alpha nested beta tail gamma'
    assert facts['us-gaap:OneHop'].value == (
        'First disclosure sentence. Second disclosure sentence.'
    )
    assert facts['us-gaap:TwoHop'].continued_at == 'k1'


def test_ix_exclude_subtree_is_omitted_but_its_tail_is_kept():
    """
    An ix:exclude subtree contributes nothing, while text FOLLOWING it does.
    That asymmetry is the whole point of the construct: it marks display-only
    material sitting inside the tagged span.
    """
    facts = {f.concept: f for f in parse(CONTINUATION_HTML).metadata.xbrl_data}
    assert facts['us-gaap:Excluded'].value == 'Keep after'


ESCAPE_HTML = """<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">
<body>
<ix:nonNumeric name="us-gaap:PolicyTextBlock" contextRef="c1" escape="true"><div class="d"><p>First para.</p><p>Second para.</p></div></ix:nonNumeric>
<ix:nonNumeric name="us-gaap:PlainBlock" contextRef="c1"><span>Flattened <b>inline</b> text</span></ix:nonNumeric>
</body></html>"""


def test_escape_true_serializes_child_markup():
    """
    gh #1239: escape="true" was never even read off the element, so there was no
    branch for "serialize child markup" against "flatten descendant text". Any
    fact with child markup - which is most dei:*TextBlock fields - came back as
    '' or the first text node only.
    """
    facts = {f.concept: f for f in parse(ESCAPE_HTML).metadata.xbrl_data}

    block = facts['us-gaap:PolicyTextBlock']
    assert block.escape is True
    assert '<p>First para.</p>' in block.value
    assert '<p>Second para.</p>' in block.value

    # Without escape the same shape flattens to text, and the descendant and
    # tail content still has to survive.
    plain = facts['us-gaap:PlainBlock']
    assert plain.escape is False
    assert plain.value == 'Flattened inline text'


FOOTNOTE_HTML = """<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">
<body>
<ix:nonNumeric name="us-gaap:Real" contextRef="c1">A real fact</ix:nonNumeric>
<ix:footnote id="fn1" footnoteRole="http://www.xbrl.org/2003/role/footnote"><span>Footnote body</span></ix:footnote>
<ix:continuation id="k9">Continuation body</ix:continuation>
</body></html>"""


def test_footnote_and_continuation_resources_are_not_facts():
    """
    gh #1237: ix:footnote was whitelisted alongside the real fact tags, so a
    footnote resource was routed through extract_fact(). It has no name, so
    concept came out '', and its text sits in descendant spans so the value came
    out '' too - a blank fake fact injected into the list, corrupting counts and
    iteration.
    """
    facts = parse(FOOTNOTE_HTML).metadata.xbrl_data

    assert [f.concept for f in facts] == ['us-gaap:Real']
    assert not any(f.concept == '' for f in facts), "a resource was extracted as a fact"


def test_a_continuation_cycle_does_not_hang():
    """A chain that points back at itself must terminate, not spin."""
    html = """<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><body>
    <ix:nonNumeric name="us-gaap:Loop" contextRef="c1" continuedAt="a">start</ix:nonNumeric>
    <ix:continuation id="a" continuedAt="b">middle</ix:continuation>
    <ix:continuation id="b" continuedAt="a">end</ix:continuation>
    </body></html>"""
    facts = {f.concept: f for f in parse(html).metadata.xbrl_data}
    assert facts['us-gaap:Loop'].value == 'start middle end'


# ---------------------------------------------------------------------------
# gh #1250 - the transformation registry covered about 5% of what filers use
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('format_attr,content,expected', [
    # The dominant spelling in real filings, and the one the five-entry dict
    # missed entirely: TR3/TR4 hyphenate. 68,880 of 90,000 format attributes in
    # the fixture corpus are this one.
    ('ixt:num-dot-decimal', '1,234,567', '1234567'),
    ('ixt:numdotdecimal', '1,234,567', '1234567'),
    ('ixt:num-comma-decimal', '1.234.567,89', '1234567.89'),
    ('ixt:fixed-zero', '—', '0'),
    ('ixt:zerodash', '-', '0'),
    ('ixt:fixed-true', '☒', 'true'),
    ('ixt:fixed-false', '☐', 'false'),
    # ixt-sec: substituting human display text for the semantic value is the
    # failure mode the RAG segment cannot detect.
    ('ixt-sec:stateprovnameen', 'Delaware', 'DE'),
    ('ixt-sec:stateprovnameen', 'New York', 'NY'),
    ('ixt-sec:stateprovnameen', 'Ontario', 'A6'),
    ('ixt-sec:countrynameen', 'United Kingdom', 'GB'),
    ('ixt-sec:edgarprovcountryen', 'Canada', 'Z4'),
    ('ixt-sec:exchnameen', 'New York Stock Exchange', 'NYSE'),
    ('ixt-sec:exchnameen', 'The Nasdaq Stock Market LLC', 'NASDAQ'),
    ('ixt-sec:entityfilercategoryen', 'Large accelerated filer', 'Large Accelerated Filer'),
    ('ixt-sec:boolballotbox', '☒', 'true'),
    ('ixt-sec:boolballotbox', '☐', 'false'),
    ('ixt-sec:duryear', '10', 'P10Y'),
    ('ixt-sec:durmonth', '18', 'P18M'),
    ('ixt-sec:durday', '364', 'P364D'),
    ('ixt-sec:durwordsen', 'ten years', 'P10Y'),
    ('ixt-sec:durwordsen', 'three-year', 'P3Y'),
    ('ixt-sec:durwordsen', '364-day', 'P364D'),
    ('ixt-sec:durwordsen', 'two years and six months', 'P2Y6M'),
    ('ixt-sec:numwordsen', 'twenty-five', '25'),
    ('ixt-sec:numwordsen', 'none', '0'),
    # Dates, in both the TR1 and TR4 spellings of the same rule.
    ('ixt:date-monthname-day-year-en', 'December 31, 2024', '2024-12-31'),
    ('ixt:datemonthdayyearen', 'December 31, 2024', '2024-12-31'),
    ('ixt:date-monthname-day-en', 'December 31', '--12-31'),
    ('ixt:date-monthname-year-en', 'July 2025', '2025-07'),
    ('ixt:date-month-day-year', '1/24/2019', '2019-01-24'),
    ('ixt:date-month-day', '12-31', '--12-31'),
    ('ixt:dateyearmonthday', '2029-01-01', '2029-01-01'),
    ('ixt:datedoteu', '31.12.2024', '2024-12-31'),
    ('ixt:datedotus', '12.31.2024', '2024-12-31'),
    # A non-breaking space is what a filer's editor actually emits.
    ('ixt:date-monthname-day-year-en', 'June\xa028, 2025', '2025-06-28'),
])
def test_transformation_registry(format_attr, content, expected):
    """gh #1250: an unsupported format silently passed raw display text through."""
    assert apply_transform(format_attr, content) == expected


def test_format_name_normalization_unifies_registry_versions():
    """Prefix, namespace URI and separator spelling all reduce to one key."""
    assert normalize_format('ixt:date-monthname-day-year-en') == 'datemonthnamedayyearen'
    assert normalize_format('{http://www.xbrl.org/inlineXBRL/transformation/2020-02-12}num-dot-decimal') \
        == 'numdotdecimal'
    assert normalize_format('ixt-sec:stateprovnameen') == 'stateprovnameen'


def test_an_unapplied_format_is_reported_not_swallowed():
    """
    An untransformed display string is indistinguishable from a real value once
    it is in the fact list, so neither failure may be silent.
    """
    with pytest.raises(UnknownTransformError):
        apply_transform('ixt:no-such-transform', 'whatever')

    # Known format, content it cannot accept.
    with pytest.raises(TransformError):
        apply_transform('ixt-sec:stateprovnameen', 'Atlantis')
    with pytest.raises(TransformError):
        apply_transform('ixt:date-monthname-day-year-en', 'December 31')


def test_a_fact_records_the_format_it_could_not_apply():
    html = """<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><body>
    <ix:nonNumeric name="dei:EntityIncorporationStateCountryCode" contextRef="c1"
        format="ixt-sec:stateprovnameen">Atlantis</ix:nonNumeric>
    </body></html>"""
    fact = parse(html).metadata.xbrl_data[0]
    # The raw content is still available, but the fact says so.
    assert fact.value == 'Atlantis'
    assert 'stateprovnameen' in fact.metadata['format_issue']


# ---------------------------------------------------------------------------
# gh #1251 - scale applied in binary float, baked into the lexical value
# ---------------------------------------------------------------------------

def test_scale_is_exact():
    """
    gh #1251: scale did float(value) * 10 ** scale and str()'d the result back
    into the lexical value, so binary float error was baked in - and because the
    corrupted string became the fact's value, numeric_value inherited it. This
    is not a display artefact.
    """
    # The reporter's case: a filed 0.7 at scale -2 came back 0.006999999999999999.
    assert float(0.7) * (10 ** -2) == 0.006999999999999999   # the old arithmetic
    assert apply_scale('0.7', '-2') == '0.007'

    assert apply_scale('1,234', '6') == '1234000000'         # no trailing '.0'
    assert apply_scale('7', '-3') == '0.007'
    assert apply_scale('8.2', '9') == '8200000000'
    assert apply_scale('61,363', '6') == '61363000000'
    # Non-numeric content leaves the value alone rather than raising.
    assert apply_scale('not a number', '3') is None
    assert apply_scale('5', 'x') is None


def test_scaled_fact_value_is_exact_end_to_end():
    html = """<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><body>
    <ix:nonFraction name="us-gaap:Rate" contextRef="c1" unitRef="pure"
        format="ixt:num-dot-decimal" scale="-2" decimals="4">0.7</ix:nonFraction>
    </body></html>"""
    fact = parse(html).metadata.xbrl_data[0]
    assert fact.value == '0.007'
    assert Decimal(fact.value) == Decimal('0.007')
    assert fact.numeric_value == pytest.approx(0.007)


def test_sign_attribute_negates_exactly():
    html = """<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><body>
    <ix:nonFraction name="us-gaap:Loss" contextRef="c1" unitRef="usd"
        format="ixt:num-dot-decimal" scale="6" sign="-">1,234</ix:nonFraction>
    </body></html>"""
    fact = parse(html).metadata.xbrl_data[0]
    assert fact.value == '-1234000000'
    assert fact.numeric_value == -1234000000.0


# ---------------------------------------------------------------------------
# gh #1233 - the public surface read a pipeline that was never populated
# ---------------------------------------------------------------------------

def test_public_api_sees_the_extracted_facts():
    """
    gh #1233: Document.xbrl_facts called a separate extractor that scanned the
    node tree for ix_tag metadata the inline pre-process path never sets. Two
    unconnected pipelines: a filing with thousands of extracted facts reported
    has_xbrl False, which is worse than missing data - it makes a working
    extraction look like an absent feature, so a caller correctly branches away.
    """
    doc = parse(CONTEXT_HTML)

    assert doc.metadata.xbrl_data, "precondition: the inline pass extracted facts"
    assert doc.has_xbrl is True
    assert len(doc.xbrl_facts) == len(doc.metadata.xbrl_data)
    assert {f.concept for f in doc.xbrl_facts} == {
        'us-gaap:Revenues', 'us-gaap:EarningsPerShareBasic'
    }
    assert doc.extract_key_information()['xbrl_facts'] == len(doc.metadata.xbrl_data)


def test_a_document_with_no_inline_xbrl_still_reports_absence():
    doc = parse("<html><body><p>No iXBRL here.</p></body></html>")
    assert doc.has_xbrl is False
    assert doc.xbrl_facts == []


# ---------------------------------------------------------------------------
# Ground truth: a real filing, hand-checked values
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not CAT_10K.exists(), reason=f"fixture not present: {CAT_10K}")
def test_caterpillar_10k_ground_truth():
    """
    Caterpillar's FY2024 10-K, hand-checked against the filing.

    us-gaap:Revenues is the Machinery, Energy & Transportation sales line:
    $61,363M, which with Financial Products revenues of $3,446M gives the
    $64,809M total sales and revenues on the income statement. Basic EPS $22.17.
    """
    doc = parse(CAT_10K.read_text(encoding='utf-8', errors='replace'))
    facts = doc.metadata.xbrl_data

    assert doc.has_xbrl is True
    assert len(doc.xbrl_facts) == len(facts)

    # Every reference resolves; the reported figures were 0 of 2,477 contexts
    # and 0 of 2,237 units.
    with_context_ref = [f for f in facts if f.context_ref]
    with_unit_ref = [f for f in facts if f.unit_ref]
    assert with_context_ref and with_unit_ref
    assert all(f.context is not None for f in with_context_ref)
    assert all(f.unit is not None for f in with_unit_ref)

    # No resource was extracted as a fact.
    assert all(f.concept for f in facts)

    by_concept = {}
    for fact in facts:
        by_concept.setdefault(fact.concept, fact)

    assert by_concept['dei:EntityRegistrantName'].value == 'CATERPILLAR INC'
    assert by_concept['dei:EntityCentralIndexKey'].value == '0000018230'
    assert by_concept['dei:DocumentPeriodEndDate'].value == '2024-12-31'
    assert by_concept['dei:CurrentFiscalYearEndDate'].value == '--12-31'
    assert by_concept['dei:EntityIncorporationStateCountryCode'].value == 'DE'
    assert by_concept['dei:SecurityExchangeName'].value == 'NYSE'
    assert by_concept['dei:EntityFilerCategory'].value == 'Large Accelerated Filer'
    assert by_concept['dei:DocumentAnnualReport'].value == 'true'
    assert by_concept['dei:AmendmentFlag'].value == 'false'
    assert by_concept['dei:EntityCommonStockSharesOutstanding'].value == '477932024'

    revenues = by_concept['us-gaap:Revenues']
    assert revenues.value == '61363000000'          # scale="6" applied exactly
    assert revenues.numeric_value == 61363000000.0
    assert revenues.unit == 'USD'
    assert revenues.context['period_type'] == 'duration'
    assert revenues.context['end_date'] == '2024-12-31'

    eps = by_concept['us-gaap:EarningsPerShareBasic']
    assert eps.value == '22.17'
    assert eps.unit == 'USD/shares'                 # a divide unit, not "USD"

    # No fact carries a lexical value corrupted by float scaling.
    assert not [f for f in facts if f.value.endswith('.0')]
    assert not [f for f in facts if '00000000000' in f.value.replace('.', '')[3:]]

    # Every format the filing uses is implemented.
    unapplied = [f for f in facts if f.metadata and f.metadata.get('format_issue')]
    assert unapplied == [], f"formats not applied: {[f.metadata for f in unapplied][:3]}"
