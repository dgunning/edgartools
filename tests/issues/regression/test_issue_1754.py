"""
Inline duration transforms return valid xs:duration values, as the SEC writes them.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1754

ixt-sec:duryear and its siblings interpolated the count into the lexical form,
so 9.5 years came out as P9.5Y. An xs:duration allows a fraction only on its
seconds; the SEC's implementation spills the fraction into the next smaller
unit and truncates there (9.5 years is P9Y6M). The word rule durwordsen also
skipped what it could not read, so "twenty-five years" came out as P5Y.
"""
from pathlib import Path

import pytest
from lxml import etree

from edgar.documents import HTMLParser
from edgar.documents.strategies.ixbrl_transforms import TransformError, apply_transform

FIXTURES = Path(__file__).parents[2] / 'fixtures'
AAPL = FIXTURES / 'attachments' / 'aapl' / '20250329'


@pytest.mark.parametrize('format_attr,content,expected', [
    # The issue's reproduction.
    ('ixt-sec:duryear', '9.5', 'P9Y6M'),
    ('ixt-sec:durmonth', '2.5', 'P2M15D'),
    ('ixt-sec:durday', '1.5', 'P1DT12H'),
    ('ixt-sec:durhour', '1.5', 'PT1H'),
    # AAR 10-Q 0001104659-26-111786 and Applied Materials 10-Q
    # 0000006951-24-000032, per the SEC's extracted instances.
    ('ixt-sec:duryear', '12.5', 'P12Y6M'),
    ('ixt-sec:duryear', '5.5', 'P5Y6M'),
    # xs:duration has no weeks.
    ('ixt-sec:durweek', '2', 'P14D'),
    ('ixt-sec:durweek', '1.5', 'P10D'),
    # Whole counts, zero and a negative count.
    ('ixt-sec:duryear', '10', 'P10Y'),
    ('ixt-sec:duryear', '0', 'P0Y'),
    ('ixt-sec:duryear', '0.5', 'P0Y6M'),
    ('ixt-sec:duryear', '-2.25', '-P2Y3M'),
    ('ixt-sec:durhour', '0', 'PT0H'),
    ('ixt-sec:durwordsen', 'twenty-five years', 'P25Y'),
    ('ixt-sec:durwordsen', 'sixty-six months', 'P66M'),
    ('ixt-sec:durwordsen', 'one year and two weeks', 'P1Y14D'),
])
def test_durations_are_valid_xs_duration(format_attr, content, expected):
    assert apply_transform(format_attr, content) == expected


@pytest.mark.parametrize('content', ['5.5 years', 'five years remaining'])
def test_word_duration_rejects_what_it_cannot_read(content):
    with pytest.raises(TransformError):
        apply_transform('ixt-sec:durwordsen', content)


def _sec_instance_values(path):
    """(concept, context) -> value for every fact in the SEC's extracted instance."""
    values = {}
    for element in etree.parse(str(path)).getroot():
        if not isinstance(element.tag, str) or element.get('contextRef') is None:
            continue
        prefix = element.prefix or ''
        local = etree.QName(element).localname
        values[(f'{prefix}:{local}', element.get('contextRef'))] = (element.text or '').strip()
    return values


def test_apple_durations_match_the_sec_instance():
    """
    Apple 10-Q for the quarter ended 2025-03-29, accession 0000320193-25-000057.
    Fact f-696 is written "2.7" under ixt-sec:duryear; the SEC's extracted
    instance (aapl-20250329_htm.xml) has P2Y8M12D. Every duration fact in the
    document must equal the instance.
    """
    html = (AAPL / 'aapl-20250329.htm').read_text(encoding='utf-8')
    facts = HTMLParser().parse(html).metadata.xbrl_data
    sec = _sec_instance_values(AAPL / 'aapl-20250329_htm.xml')

    durations = [f for f in facts if (f.format or '').startswith('ixt-sec:dur')]
    assert durations
    for fact in durations:
        assert fact.value == sec[(fact.concept, fact.context_ref)], fact.concept

    period = next(f for f in durations if f.concept.endswith(
        'NonvestedAwardsTotalCompensationCostNotYetRecognizedPeriodForRecognition1'))
    assert period.value == 'P2Y8M12D'


def test_amazon_twenty_five_years():
    """
    Amazon 10-K, accession 0001018724-25-000004: fact f-865
    (us-gaap:FiniteLivedIntangibleAssetUsefulLife, context c-156) reads
    "twenty-five years" under ixt-sec:durwordsen; the SEC's instance has P25Y.
    """
    html = (FIXTURES / 'html' / 'amzn' / '10k' / 'amzn-10-k-2025-02-07.html').read_text(encoding='utf-8')
    facts = HTMLParser().parse(html).metadata.xbrl_data
    fact = next(f for f in facts
                if f.concept == 'us-gaap:FiniteLivedIntangibleAssetUsefulLife' and f.context_ref == 'c-156')
    assert fact.value == 'P25Y'
