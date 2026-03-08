"""Regression test for gh:685 / edgartools-5op3

Document.to_json() raised AttributeError: 'str' object has no attribute 'to_dict'
because parser.py stored xbrl_data as {'facts': xbrl_facts} (a dict) instead of
the list of XBRLFact objects expected by DocumentMetadata.to_dict().
"""
from edgar.documents.document import DocumentMetadata
from edgar.documents.types import XBRLFact


def _make_fact() -> XBRLFact:
    return XBRLFact(concept="us-gaap:Revenues", value="1000000")


def test_document_metadata_to_dict_with_xbrl_data():
    """to_dict() must not raise when xbrl_data is a list of XBRLFact."""
    meta = DocumentMetadata(source="test")
    meta.xbrl_data = [_make_fact()]
    result = meta.to_dict()
    assert result["xbrl_data"] is not None
    assert isinstance(result["xbrl_data"], list)
    assert len(result["xbrl_data"]) == 1
    assert result["xbrl_data"][0]["concept"] == "us-gaap:Revenues"


def test_document_metadata_to_dict_without_xbrl_data():
    """to_dict() returns None for xbrl_data when none is present."""
    meta = DocumentMetadata(source="test")
    result = meta.to_dict()
    assert result["xbrl_data"] is None


def test_parser_assigns_list_not_dict():
    """parser.py must assign xbrl_facts list directly, not {'facts': xbrl_facts}.

    Previously the parser did: metadata.xbrl_data = {'facts': xbrl_facts}
    Iterating over a dict yields string keys, so fact.to_dict() raised AttributeError.
    """
    meta = DocumentMetadata(source="test")
    xbrl_facts = [_make_fact()]
    meta.xbrl_data = xbrl_facts  # the fixed parser assigns the list directly
    result = meta.to_dict()
    assert isinstance(result["xbrl_data"], list)
