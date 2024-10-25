from pathlib import Path

import pytest

from edgar.xbrl.concepts import concept_to_label
from edgar.xbrl.labels import parse_label_linkbase


def test_parse_labels_with_namespace():
    label_text = Path('data/xbrl/datafiles/aapl/aapl-20230930_lab.xml').read_text()
    labels = parse_label_linkbase(label_text)
    assert 'dei_CoverAbstract' in labels
    print(labels)


def test_parse_labels_with_no_namespace():
    label_text = Path('data/xbrl/datafiles/radcq/rad-20230304_lab.xml').read_text()
    labels = parse_label_linkbase(label_text)
    assert 'dei_CoverAbstract' in labels



@pytest.mark.parametrize("concept,expected", [
    ("us-gaap_ClassOfStockDomain", "Class Of Stock"),
    ("dei_CoverPage", "Cover Page"),
    ("us-gaap_StatementOfIncome", "Statement Of Income"),
    ("ifrs-full_Revenue", "Revenue"),
    ("us-gaap_AssetsAbstract", "Assets"),
    ("dei_DocumentType", "Document Type"),
    ("us-gaap_LiabilitiesAndStockholdersEquity", "Liabilities And Stockholders Equity"),
    ("custom_XBRL2023", "Xbrl 2023"),
])
def test_concept_to_label(concept, expected):
    assert concept_to_label(concept) == expected
