"""
Verification tests for XmlFiling generic data object.

Ground truth filings:
  - Advanced Advisor Group (X-17A-5) — broker-dealer report
  - Aflac Inc (TA-2) — transfer agent annual report
  - PicMii Crowdfunding (CFPORTAL) — crowdfunding portal registration
"""
import pytest
from edgar.xmlfiling import (
    XmlFiling, XML_FILING_FORMS, _element_to_dict, _deep_get,
    _XSLT_PREFIXES, _FORM_DESCRIPTIONS,
)


# ---------------------------------------------------------------------------
# Unit tests (no network)
# ---------------------------------------------------------------------------

class TestElementToDict:

    def test_simple_element(self):
        from lxml import etree
        xml = "<root><name>Alice</name><age>30</age></root>"
        root = etree.fromstring(xml)
        result = _element_to_dict(root)
        assert result == {'name': 'Alice', 'age': '30'}

    def test_nested_element(self):
        from lxml import etree
        xml = "<root><address><city>NYC</city><state>NY</state></address></root>"
        root = etree.fromstring(xml)
        result = _element_to_dict(root)
        assert result == {'address': {'city': 'NYC', 'state': 'NY'}}

    def test_repeated_elements_become_list(self):
        from lxml import etree
        xml = "<root><item>A</item><item>B</item><item>C</item></root>"
        root = etree.fromstring(xml)
        result = _element_to_dict(root)
        assert result == {'item': ['A', 'B', 'C']}

    def test_empty_element(self):
        from lxml import etree
        xml = "<root><empty/></root>"
        root = etree.fromstring(xml)
        result = _element_to_dict(root)
        assert result == {'empty': None}


class TestDeepGet:

    def test_top_level_key(self):
        data = {'name': 'Alice', 'age': '30'}
        assert _deep_get(data, 'name') == 'Alice'

    def test_nested_key(self):
        data = {'address': {'city': 'NYC', 'state': 'NY'}}
        assert _deep_get(data, 'city') == 'NYC'

    def test_deeply_nested_key(self):
        data = {'a': {'b': {'c': 'found'}}}
        assert _deep_get(data, 'c') == 'found'

    def test_missing_key(self):
        data = {'name': 'Alice'}
        assert _deep_get(data, 'missing') is None

    def test_key_in_list(self):
        data = {'items': [{'name': 'A'}, {'name': 'B'}]}
        assert _deep_get(data, 'name') == 'A'


class TestXmlFilingForms:

    def test_all_forms_have_descriptions(self):
        for form in _XSLT_PREFIXES:
            assert form in _FORM_DESCRIPTIONS, f"Missing description for {form}"

    def test_amendments_included(self):
        assert 'X-17A-5' in XML_FILING_FORMS
        assert 'X-17A-5/A' in XML_FILING_FORMS
        assert 'TA-1' in XML_FILING_FORMS
        assert 'TA-1/A' in XML_FILING_FORMS

    def test_form_count(self):
        # Each form + its /A variant
        assert len(XML_FILING_FORMS) == len(_XSLT_PREFIXES) * 2


class TestObjInfo:

    def test_xml_filing_forms_registered(self):
        from edgar import get_obj_info
        for form in ['X-17A-5', 'TA-1', 'TA-2', 'CFPORTAL', 'SBSE']:
            has_obj, class_name, desc = get_obj_info(form)
            assert has_obj is True, f"{form} not registered"
            assert class_name == 'XmlFiling', f"{form} has wrong class: {class_name}"


# ---------------------------------------------------------------------------
# Network tests — real filings
# ---------------------------------------------------------------------------

@pytest.mark.network
class TestXmlFilingNetwork:

    def test_x17a5_broker_dealer(self):
        """X-17A-5 broker-dealer report — structured XML with dict access."""
        from edgar import get_filings
        f = get_filings(form='X-17A-5')[0]
        obj = f.obj()

        assert isinstance(obj, XmlFiling)
        assert obj.form == 'X-17A-5'
        assert obj.description == 'Broker-Dealer Financial Report'
        assert obj['brokerDealerName'] is not None
        assert obj['periodBegin'] is not None

    def test_ta2_transfer_agent(self):
        """TA-2 transfer agent annual report."""
        from edgar import get_filings
        f = get_filings(form='TA-2')[0]
        obj = f.obj()

        assert isinstance(obj, XmlFiling)
        assert obj.description == 'Transfer Agent Annual Report'
        assert obj.form_data is not None
        assert len(obj.form_data) > 0

    def test_cfportal_crowdfunding(self):
        """CFPORTAL crowdfunding portal registration."""
        from edgar import get_filings
        f = get_filings(form='CFPORTAL')[0]
        obj = f.obj()

        assert isinstance(obj, XmlFiling)
        assert obj.description == 'Crowdfunding Portal Registration'
        assert obj.form_data is not None
        assert len(obj.form_data) > 0

    def test_dict_access(self):
        """Deep key lookup via [] operator."""
        from edgar import get_filings
        f = get_filings(form='X-17A-5')[0]
        obj = f.obj()

        # accountantName is nested under accountantIdentification
        assert obj['accountantName'] is not None
        # Missing key returns None via .get()
        assert obj.get('nonexistentKey', 'default') == 'default'

    def test_to_html_xslt(self):
        """XSLT-rendered HTML from SEC endpoint."""
        from edgar import get_filings
        f = get_filings(form='X-17A-5')[0]
        obj = f.obj()

        html = obj.to_html()
        assert html is not None
        assert '<html' in html[:500].lower()

    def test_filing_html_integration(self):
        """filing.html() returns XSLT-rendered HTML for XML forms."""
        from edgar import get_filings
        f = get_filings(form='X-17A-5')[0]
        html = f.html()
        assert html is not None
        assert '<html' in html[:500].lower()

    def test_rich_display(self):
        """Rich display renders without error."""
        from edgar import get_filings
        f = get_filings(form='X-17A-5')[0]
        obj = f.obj()
        assert obj.__rich__() is not None

    def test_to_context(self):
        """AI context includes form type and data fields."""
        from edgar import get_filings
        f = get_filings(form='X-17A-5')[0]
        obj = f.obj()

        ctx = obj.to_context()
        assert 'XML FILING' in ctx
        assert 'Broker-Dealer Financial Report' in ctx

    def test_str(self):
        from edgar import get_filings
        f = get_filings(form='X-17A-5')[0]
        obj = f.obj()
        s = str(obj)
        assert 'XmlFiling' in s
        assert 'X-17A-5' in s
