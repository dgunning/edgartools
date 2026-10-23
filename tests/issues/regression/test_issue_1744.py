"""Regression: label resources in any English variant are kept, not only xml:lang="en-US".

GitHub Issue: https://github.com/dgunning/edgartools/issues/1744

`LabelsParser.parse_labels_content` grouped label resources by their raw
xml:lang and attached them to an element only when the exact key 'en-US' was
present. XBRL 2.1 section 5.2.2.2 allows any language code, and the IFRS
taxonomy writes "en": parsing the IFRS Foundation's IAS 1 documentation
linkbase (doc_ias_1-en_2025-03-27.xml) kept 0 of its 686 labels.

English labels are now merged by role, en-US first, then en, then other en-*
variants; labels in other languages are still ignored. EDGAR filers' own label
linkbases write en-US (all 32 20-F/40-F filings sampled on 2026-10-22
did), so their labels are unchanged; the CNI test pins that.
"""

import pytest

from edgar.httprequests import download_file
from edgar.xbrl.parsers.labels import LabelsParser

STANDARD = "http://www.xbrl.org/2003/role/label"
TERSE = "http://www.xbrl.org/2003/role/terseLabel"
DOCUMENTATION = "http://www.xbrl.org/2003/role/documentation"


def _linkbase(labels: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase"
               xmlns:xlink="http://www.w3.org/1999/xlink">
  <link:labelLink xlink:type="extended" xlink:role="http://www.xbrl.org/2003/role/link">
    <link:loc xlink:type="locator" xlink:href="x.xsd#ifrs-full_Revenue" xlink:label="loc"/>
    <link:labelArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/concept-label"
        xlink:from="loc" xlink:to="res"/>
    {labels}
  </link:labelLink>
</link:linkbase>
"""


def _label(lang: str, role: str, text: str) -> str:
    return (f'<link:label xlink:type="resource" xlink:label="res" xlink:role="{role}" '
            f'xml:lang="{lang}">{text}</link:label>')


@pytest.mark.parametrize("lang", ["en", "en-us", "EN-US", "en-GB"])
def test_english_label_in_any_variant_is_kept(lang):
    catalog = {}
    LabelsParser(catalog).parse_labels_content(_linkbase(_label(lang, STANDARD, "Revenue")))
    assert catalog["ifrs-full_Revenue"].labels == {STANDARD: "Revenue"}


def test_en_us_wins_per_role_and_other_languages_are_ignored():
    catalog = {}
    LabelsParser(catalog).parse_labels_content(_linkbase(
        _label("en", STANDARD, "Revenue (en)")
        + _label("en-US", STANDARD, "Revenue (en-US)")
        + _label("en-GB", TERSE, "Turnover")
        + _label("en", TERSE, "Revenue, terse")
        + _label("fr", DOCUMENTATION, "Produits")
    ))
    assert catalog["ifrs-full_Revenue"].labels == {
        STANDARD: "Revenue (en-US)",
        TERSE: "Revenue, terse",
    }


def _separate_resources_linkbase(order):
    """One resource and one arc per language, as Workiva writes them (lab_X_label_en-US)."""
    resources = {
        "us": ("en-US", "Revenue US"),
        "gb": ("en-GB", "Turnover GB"),
        "en": ("en", "Revenue EN"),
    }
    body = ""
    for key in order:
        lang, text = resources[key]
        body += (f'<link:labelArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/concept-label" '
                 f'xlink:from="loc" xlink:to="lab_{key}"/>'
                 f'<link:label xlink:type="resource" xlink:label="lab_{key}" xlink:role="{STANDARD}" '
                 f'xml:lang="{lang}">{text}</link:label>')
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase"
               xmlns:xlink="http://www.w3.org/1999/xlink">
  <link:labelLink xlink:type="extended" xlink:role="http://www.xbrl.org/2003/role/link">
    <link:loc xlink:type="locator" xlink:href="x.xsd#us-gaap_Revenue" xlink:label="loc"/>
    {body}
  </link:labelLink>
</link:linkbase>
"""


@pytest.mark.parametrize("order", [("us", "gb"), ("gb", "us"), ("us", "en", "gb"), ("gb", "en", "us"), ("gb", "en")])
def test_language_rank_holds_across_separate_label_resources(order):
    catalog = {}
    LabelsParser(catalog).parse_labels_content(_separate_resources_linkbase(order))
    expected = "Revenue US" if "us" in order else "Revenue EN"
    assert catalog["us-gaap_Revenue"].labels[STANDARD] == expected


def test_label_in_no_english_variant_is_still_ignored():
    catalog = {}
    LabelsParser(catalog).parse_labels_content(_linkbase(_label("de", STANDARD, "Umsatzerlöse")))
    assert catalog == {}


IFRS_IAS1_DOC = ("https://xbrl.ifrs.org/taxonomy/2025-03-27/full_ifrs/labels/"
                 "doc_ias_1-en_2025-03-27.xml")


@pytest.mark.vcr
def test_ifrs_ias1_documentation_labels_are_kept():
    """Ground truth: IFRS Foundation taxonomy 2025-03-27, doc_ias_1-en_2025-03-27.xml (686 labels, all xml:lang="en")."""
    catalog = {}
    LabelsParser(catalog).parse_labels_content(download_file(IFRS_IAS1_DOC))
    assert len(catalog) == 686
    assert catalog["ifrs-full_Revenue"].labels[DOCUMENTATION] == (
        "The income arising in the course of an entity's ordinary activities. Income is "
        "increases in assets, or decreases in liabilities, that result in increases in equity, "
        "other than those relating to contributions from holders of equity claims."
    )


CNI_LABELS = "https://www.sec.gov/Archives/edgar/data/16868/000110465926010352/cni-20251231_lab.xml"


@pytest.mark.vcr
def test_sec_filer_en_us_labels_are_unchanged():
    """Ground truth: Canadian National Railway 40-F, 0001104659-26-010352, cni-20251231_lab.xml."""
    catalog = {}
    LabelsParser(catalog).parse_labels_content(download_file(CNI_LABELS))
    assert catalog["dei_BusinessContactMember"].labels[STANDARD] == "Business Contact [Member]"
    assert catalog["dei_EntityAddressesAddressTypeAxis"].labels[STANDARD] == "Entity Addresses, Address Type [Axis]"
