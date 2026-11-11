"""
Escaped Inline XBRL TextBlock values drop nested ix: tags and ix:exclude content.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1770

For an escape="true" fact, XBRLExtractor._collect_content unwrapped ix:
elements and skipped ix:exclude only among the fact's direct children; any
deeper child was serialized whole, so nested <ix:nonfraction> tags and
ix:exclude page footers survived in the disclosure markup.
"""
import html as htmllib
import re
from pathlib import Path

from lxml import etree

from edgar.documents import HTMLParser, ParserConfig

MSFT = Path(__file__).parents[2] / 'fixtures' / 'xbrl' / 'msft' / '10k_2024'

SYNTHETIC = """<html xmlns="http://www.w3.org/1999/xhtml" xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">
<body><div>
<ix:nonNumeric name="us-gaap:BusinessCombinationDisclosureTextBlock" contextRef="c1" escape="true">
<p>Paid $<span><ix:nonFraction name="us-gaap:BusinessCombinationConsiderationTransferred1" contextRef="c1" unitRef="usd" decimals="-5" scale="6">36.3</ix:nonFraction></span> million.</p>
<div><ix:exclude><p>Page 12</p></ix:exclude></div><p>End.</p>
</ix:nonNumeric>
</div></body></html>"""


def _facts(html):
    return {f.concept: f for f in HTMLParser(ParserConfig()).parse(html).xbrl_facts}


def test_nested_inline_tags_and_excludes_are_projected_out():
    facts = _facts(SYNTHETIC)
    value = facts['us-gaap:BusinessCombinationDisclosureTextBlock'].value
    assert value == '<p>Paid $<span>36.3</span> million.</p>\n<div></div><p>End.</p>'
    # The nested fact is still its own fact, scaled.
    assert facts['us-gaap:BusinessCombinationConsiderationTransferred1'].value == '36300000'


def test_the_source_tree_is_not_modified():
    """The projection works on a copy: the nested fact is still extracted from the tree."""
    facts = _facts(SYNTHETIC)
    assert 'us-gaap:BusinessCombinationConsiderationTransferred1' in facts


def _words(markup):
    return htmllib.unescape(re.sub(r'<[^>]+>', ' ', markup)).split()


def test_microsoft_escaped_facts_match_the_sec_instance():
    """
    Microsoft 10-K, accession 0000950170-24-087843. Its escaped TextBlocks nest
    ix:nonFraction facts below the first level and wrap page footers
    ("61 PART II Item 8") in ix:exclude. Every escaped fact must carry no ix:
    markup and the same words as the SEC's extracted instance
    (msft-20240730_htm.xml).
    """
    html = (MSFT / 'msft-20240630.htm').read_text(encoding='utf-8')
    facts = HTMLParser().parse(html).metadata.xbrl_data
    sec = {}
    for element in etree.parse(str(MSFT / 'msft-20240730_htm.xml')).getroot():
        if isinstance(element.tag, str) and element.get('contextRef'):
            sec[(f'{element.prefix}:{etree.QName(element).localname}', element.get('contextRef'))] = element.text or ''

    escaped = [f for f in facts if f.escape and (f.concept, f.context_ref) in sec]
    assert len(escaped) == 92
    for fact in escaped:
        assert '<ix:' not in fact.value, fact.concept
        assert _words(fact.value) == _words(sec[(fact.concept, fact.context_ref)]), fact.concept

    policies = next(f for f in escaped if f.concept == 'us-gaap:SignificantAccountingPoliciesTextBlock')
    assert 'PART II' not in policies.value
