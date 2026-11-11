"""
Inline XBRL formats resolve by namespace URI and exact local name, and the
missing TR4/TR5 rules are implemented.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1743

A ``format`` is an expanded name. The registry used to strip the prefix or
namespace and the separators, so ``{TR3}fixed-zero`` was "known" although TR3
has no such rule, and TR4's ``date-month-year`` and ``date-year-month`` and
TR5's ``num-*-decimal-apos`` rules were missing.
"""
from pathlib import Path

import pytest

from edgar.documents import HTMLParser
from edgar.documents.strategies.ixbrl_transforms import (
    UnknownTransformError,
    apply_transform,
    is_known_format,
)

TR2_NS = 'http://www.xbrl.org/inlineXBRL/transformation/2011-07-31'
TR3_NS = 'http://www.xbrl.org/inlineXBRL/transformation/2015-02-26'
TR4_NS = 'http://www.xbrl.org/inlineXBRL/transformation/2020-02-12'
TR5_NS = 'http://www.xbrl.org/inlineXBRL/transformation/2022-02-16'
IXT_SEC_NS = 'http://www.sec.gov/inlineXBRL/transformation/2015-08-31'

FIXTURE = Path(__file__).parents[2] / 'fixtures' / 'parity_gate' / '8-K' / '0000887919-21-000012.html'


def _q(namespace, local_name):
    return f'{{{namespace}}}{local_name}'


@pytest.mark.parametrize('namespace,local_name,known', [
    (TR3_NS, 'fixed-zero', False),          # TR3 has no fixed-zero
    (TR4_NS, 'fixed-zero', True),
    (TR2_NS, 'booleantrue', True),
    (TR4_NS, 'booleantrue', False),         # TR4 renamed it fixed-true
    (TR4_NS, 'numdotdecimal', False),       # TR4 spells it num-dot-decimal
    (TR4_NS, 'num-dot-decimal', True),
    (TR4_NS, 'num-dot-decimal-apos', False),  # TR5 only
    (TR5_NS, 'num-dot-decimal-apos', True),
    (TR4_NS, 'exchnameen', False),          # an ixt-sec rule, not an ixt one
    (IXT_SEC_NS, 'exchnameen', True),
    ('http://example.com/not-a-registry', 'num-dot-decimal', False),
])
def test_declared_namespace_resolves_exactly(namespace, local_name, known):
    assert is_known_format(_q(namespace, local_name)) is known


def test_unknown_expanded_name_raises():
    with pytest.raises(UnknownTransformError):
        apply_transform(_q(TR3_NS, 'fixed-zero'), '-')


@pytest.mark.parametrize('format_attr,content,expected', [
    # The issue's reproduction: TR4 gYearMonth rules.
    ('ixt:date-month-year', '12/2025', '2025-12'),
    (_q(TR4_NS, 'date-month-year'), '12/2025', '2025-12'),
    (_q(TR4_NS, 'date-month-year'), '3.25', '2025-03'),
    (_q(TR4_NS, 'date-year-month'), '2025-12', '2025-12'),
    (_q(TR3_NS, 'datemonthyear'), '07/2024', '2024-07'),
    # TR5 Swiss-style apostrophe thousands separators.
    (_q(TR5_NS, 'num-dot-decimal-apos'), "1'234'567.89", '1234567.89'),
    (_q(TR5_NS, 'num-comma-decimal-apos'), '1’234’567,89', '1234567.89'),
    (_q(TR5_NS, 'num-unit-decimal-apos'), "1'234 Franken 5 Rappen", '1234.05'),
    # num-unit-decimal is major and minor units, not a dotted number.
    (_q(TR4_NS, 'num-unit-decimal'), '5 dollars 25 cents', '5.25'),
    # Roman-numeral months.
    (_q(TR4_NS, 'date-day-monthroman-year'), '31 XII 2024', '2024-12-31'),
    (_q(TR4_NS, 'date-monthroman-year'), 'IV/2024', '2024-04'),
    (_q(TR4_NS, 'date-day-monthroman'), '5 iii', '--03-05'),
    # TR1 rules that were absent.
    ('{http://www.xbrl.org/inlineXBRL/transformation/2010-04-20}numcommadot', '1,234.5', '1234.5'),
    ('{http://www.xbrl.org/inlineXBRL/transformation/2010-04-20}datelonguk', '5 January 2010', '2010-01-05'),
    # ixt-sec rules that were absent.
    (_q(IXT_SEC_NS, 'datequarterend'), 'third quarter of 2024', '2024-09-30'),
    (_q(IXT_SEC_NS, 'datequarterend'), '2024 Q4', '2024-12-31'),
    (_q(IXT_SEC_NS, 'yesnoballotbox'), '☒', 'Yes'),
    (_q(IXT_SEC_NS, 'yesnoballotbox'), '☐', 'No'),
    (_q(IXT_SEC_NS, 'numnan'), 'n/a', 'NaN'),
])
def test_added_rules(format_attr, content, expected):
    assert apply_transform(format_attr, content) == expected


def _doc(namespace, format_local, content):
    return f"""<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" xmlns:ixt="{namespace}"><body>
    <ix:nonFraction name="us-gaap:Revenues" contextRef="c1" unitRef="usd" decimals="0"
        format="ixt:{format_local}">{content}</ix:nonFraction>
    </body></html>"""


def test_document_format_resolves_in_its_declared_registry():
    """The prefix ixt is bound per document; the same local name differs by registry."""
    fact = HTMLParser().parse(_doc(TR4_NS, 'fixed-zero', '—')).metadata.xbrl_data[0]
    assert fact.value == '0'
    assert not (fact.metadata or {}).get('format_issue')

    fact = HTMLParser().parse(_doc(TR3_NS, 'fixed-zero', '—')).metadata.xbrl_data[0]
    assert fact.value == '—'
    assert 'unsupported format ixt:fixed-zero' in fact.metadata['format_issue']


def test_real_tr3_filing_resolves_through_its_declarations():
    """
    Premier Financial Bancorp 8-K, accession 0000887919-21-000012, declares
    ixt as Transformation Registry 3 (2015-02-26) and ixt-sec as the SEC
    registry. Its cover page writes "March 29, 2021" under ixt:datemonthdayyearen
    and "Kentucky" under ixt-sec:stateprovnameen.
    """
    html = FIXTURE.read_text(encoding='utf-8')
    facts = {f.concept: f for f in HTMLParser().parse(html).metadata.xbrl_data}
    assert facts['dei:DocumentPeriodEndDate'].value == '2021-03-29'
    assert facts['dei:EntityIncorporationStateCountryCode'].value == 'KY'
    assert facts['dei:AmendmentFlag'].value == 'false'
    assert not any((f.metadata or {}).get('format_issue') for f in facts.values())
