"""Regression test for GitHub Issue #1672.

``Financials.get_shares_outstanding_basic()`` promises the weighted-average
basic EPS denominator. Its pattern list did not match the us-gaap element for a
single basic-and-diluted count, ``WeightedAverageNumberOfShareOutstandingBasicAndDiluted``
(singular "Share"), and then fell back to ``CommonStockSharesOutstanding``, an
ending (or opening) instant count. The diluted getter had no match at all.

The getters now match the combined element and no longer fall back to an
instant share count.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1672
"""
from pathlib import Path

import pytest

from edgar.financials import Financials
from edgar.httprequests import download_file
from edgar.xbrl import XBRL

pytestmark = pytest.mark.regression

COMBINED = "WeightedAverageNumberOfShareOutstandingBasicAndDiluted"


def _write_synthetic_package(d: Path, with_weighted_average: bool = True) -> XBRL:
    """The issue's synthetic 10-K: a combined weighted-average row (100M) and a
    CommonStockSharesOutstanding row with periodEndLabel (130M)."""
    concepts = {
        "IncomeStatementAbstract": ("string", "duration", "true"),
        "NetIncomeLoss": ("monetary", "duration", "false"),
        COMBINED: ("shares", "duration", "false"),
        "CommonStockSharesOutstanding": ("shares", "instant", "false"),
    }
    if not with_weighted_average:
        del concepts[COMBINED]
    els = "".join(
        f'<xs:element name="{n}" id="us-gaap_{n}" type="xbrli:{k}ItemType" substitutionGroup="xbrli:item" '
        f'xbrli:periodType="{p}" abstract="{a}" nillable="true"/>' for n, (k, p, a) in concepts.items())
    (d / "shares.xsd").write_text(
        '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xbrli="http://www.xbrl.org/2003/instance" '
        'xmlns:link="http://www.xbrl.org/2003/linkbase" targetNamespace="http://fasb.org/us-gaap/2024" '
        'elementFormDefault="qualified"><xs:annotation><xs:appinfo><link:roleType roleURI="http://example.com/role/IS" '
        'id="IS"><link:definition>100000 - Statement - Consolidated Statements of Operations</link:definition>'
        '<link:usedOn>link:presentationLink</link:usedOn></link:roleType></xs:appinfo></xs:annotation>'
        + els + '</xs:schema>', encoding="utf-8")
    ent = '<xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0000000001</xbrli:identifier></xbrli:entity>'
    weighted = (f'<us-gaap:{COMBINED} contextRef="year" unitRef="shares" decimals="0">100000000</us-gaap:{COMBINED}>'
                if with_weighted_average else "")
    (d / "shares.xml").write_text(
        '<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:us-gaap="http://fasb.org/us-gaap/2024" '
        'xmlns:dei="http://xbrl.sec.gov/dei/2024" xmlns:iso4217="http://www.xbrl.org/2003/iso4217">'
        f'<xbrli:context id="year">{ent}<xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate>'
        '<xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>'
        f'<xbrli:context id="end">{ent}<xbrli:period><xbrli:instant>2025-12-31</xbrli:instant></xbrli:period></xbrli:context>'
        '<xbrli:unit id="shares"><xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unit>'
        '<xbrli:unit id="USD"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>'
        '<dei:EntityRegistrantName contextRef="year">Synthetic Example</dei:EntityRegistrantName>'
        '<dei:DocumentType contextRef="year">10-K</dei:DocumentType>'
        '<dei:DocumentPeriodEndDate contextRef="year">2025-12-31</dei:DocumentPeriodEndDate>'
        '<dei:DocumentFiscalPeriodFocus contextRef="year">FY</dei:DocumentFiscalPeriodFocus>'
        '<dei:DocumentFiscalYearFocus contextRef="year">2025</dei:DocumentFiscalYearFocus>'
        '<us-gaap:NetIncomeLoss contextRef="year" unitRef="USD" decimals="0">-10000000</us-gaap:NetIncomeLoss>'
        + weighted +
        '<us-gaap:CommonStockSharesOutstanding contextRef="end" unitRef="shares" decimals="0">130000000'
        '</us-gaap:CommonStockSharesOutstanding></xbrli:xbrl>', encoding="utf-8")
    end_label = ' preferredLabel="http://www.xbrl.org/2003/role/periodEndLabel"'
    locs = "".join(f'<link:loc xlink:type="locator" xlink:href="shares.xsd#us-gaap_{n}" xlink:label="{n}"/>'
                   for n in concepts)
    arcs = "".join(
        f'<link:presentationArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/parent-child" '
        f'xlink:from="IncomeStatementAbstract" xlink:to="{n}" order="{i}"'
        f'{end_label if n == "CommonStockSharesOutstanding" else ""}/>'
        for i, n in enumerate(list(concepts)[1:], 1))
    (d / "shares_pre.xml").write_text(
        '<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink">'
        f'<link:presentationLink xlink:type="extended" xlink:role="http://example.com/role/IS">{locs}{arcs}'
        '</link:presentationLink></link:linkbase>', encoding="utf-8")
    return XBRL.from_files(instance_file=d / "shares.xml", schema_file=d / "shares.xsd",
                           presentation_file=d / "shares_pre.xml")


def test_combined_weighted_average_is_returned_not_the_period_end_count(tmp_path):
    financials = Financials(_write_synthetic_package(tmp_path))
    # Before the fix: 130,000,000 (the period-end instant count) and None.
    assert financials.get_shares_outstanding_basic() == 100_000_000
    assert financials.get_shares_outstanding_diluted() == 100_000_000


def test_period_end_count_alone_is_not_reported_as_the_weighted_average(tmp_path):
    financials = Financials(_write_synthetic_package(tmp_path, with_weighted_average=False))
    # An instant share count does not establish the EPS weighted average.
    assert financials.get_shares_outstanding_basic() is None


# Snowflake's FY2021 10-K (year ended 2021-01-31) tags its one EPS denominator
# with the combined element. Schema, presentation, label and instance documents.
SNOW_10K_FOLDER = "https://www.sec.gov/Archives/edgar/data/1640147/000164014721000073/"
SNOW_10K_XBRL_FILES = ("snow-20210131.xsd", "snow-20210131_pre.xml",
                       "snow-20210131_lab.xml", "snow-20210131_htm.xml")


@pytest.mark.vcr
def test_snowflake_fy2021_weighted_average_shares(tmp_path):
    """Ground truth: Snowflake 10-K, accession 0001640147-21-000073, statement of
    operations: weighted-average shares used in computing net loss per share,
    basic and diluted, 141,613,196 (FY2021) and 44,847,442 (FY2020)."""
    for name in SNOW_10K_XBRL_FILES:
        (tmp_path / name).write_text(download_file(SNOW_10K_FOLDER + name), encoding="utf-8")
    financials = Financials(XBRL.from_directory(tmp_path))

    # Before the fix both getters returned None for this filing.
    assert financials.get_shares_outstanding_basic() == 141_613_196
    assert financials.get_shares_outstanding_basic(period_offset=1) == 44_847_442
    assert financials.get_shares_outstanding_diluted() == 141_613_196
