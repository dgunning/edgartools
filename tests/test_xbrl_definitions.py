from pathlib import Path

from edgar.xbrl.definitions import parse_definition_linkbase
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


def test_parse_definitions_with_namespace():
    definition_text = Path('data/xbrl/datafiles/aapl/aapl-20230930_def.xml').read_text()
    definitions = parse_definition_linkbase(definition_text)
    print(definitions)
    assert 'http://fasb.org/us-gaap/role/eedm/ExtensibleEnumerationLists' in definitions


def test_parse_definitions_with_no_namespace():
    definition_text = Path('data/xbrl/datafiles/radcq/rad-20230304_def.xml').read_text()
    definitions = parse_definition_linkbase(definition_text)
    assert 'http://fasb.org/us-gaap/role/eedm/ExtensibleEnumerationLists' in definitions
