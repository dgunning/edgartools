"""What `Form144.parse_xml` owes its callers, with no network.

`edgar/ownership/form144.py` (then `edgar/form144.py`) moved from BeautifulSoup to lxml under edgartools-07lk.11.3.
Form 144 XML is namespaced twice — `xmlns="http://www.sec.gov/edgar/ownership"`
for the body and `xmlns:com="http://www.sec.gov/edgar/common"` for every address
block — so a plain lxml `.//street1` finds nothing at all, silently. Every read
in that module goes through the `xmltools` helpers, which match on the local name.

`tests/test_form144.py` is classified `network` in `tests/conftest.py`, so
nothing added there runs in the fast job. Ground truth here is SEC's own published
sample notice, checked in at `data/144/EDGAR Form 144 XML Samples/Sample 144.xml`.
"""
from pathlib import Path

import pytest

from edgar.form144 import Form144

SAMPLE = Path('data/144/EDGAR Form 144 XML Samples/Sample 144.xml')
SAMPLE_AMENDMENT = Path('data/144/EDGAR Form 144 XML Samples/Sample 144dashA.xml')


@pytest.fixture(scope="module")
def sample():
    return Form144.parse_xml(SAMPLE.read_text())


def test_the_document_is_namespaced_twice(sample):
    """The premise the rest of this file rests on, asserted rather than assumed."""
    text = SAMPLE.read_text()
    assert 'xmlns="http://www.sec.gov/edgar/ownership"' in text
    assert 'xmlns:com="http://www.sec.gov/edgar/common"' in text
    assert "<com:street1>" in text


def test_the_issuer_block_is_read(sample):
    assert sample['issuer_cik'] == "0001118676"
    assert sample['issuer_name'] == "RUFUS TEST CO"
    assert sample['sec_file_number'] == "033-100039"
    assert sample['issuer_contact_phone'] == "972-717-0300"
    assert sample['person_selling'] == "van der Velden Jan"
    assert sample['relationships'] == ["Officer", "Director", "Stakeholder"]


def test_the_issuer_address_is_read_across_the_com_namespace(sample):
    """`<issuerAddress>` sits in the ownership namespace and its children in the
    common one, which is the shape that defeats the parent's-namespace shortcut in
    `xmltools` and leaves only the local-name scan behind it."""
    address = sample['address']
    assert address.street1 == "5601 N. MacArthur Blvd"
    assert address.city == "Irving"
    assert address.state_or_country == "TX"
    assert address.zipcode == "75038"


def test_every_security_line_is_found_with_its_broker(sample):
    """Two `<securitiesInformation>` blocks, each with a nested broker whose own
    address is `com:`-namespaced two levels down."""
    rows = sample['securities_information'].to_dict('records')
    assert len(rows) == 2
    assert rows[0]['security_class'] == "Common stock"
    assert rows[0]['units_to_be_sold'] == 17087
    assert rows[0]['market_value'] == 1282000.0
    assert rows[0]['units_outstanding'] == 161514066
    assert rows[0]['exchange_name'] == "CHX"
    assert rows[0]['broker_name'] == "Virtu Financial"
    assert rows[1]['broker_name'] == "Virtu Financial 1"
    assert rows[1]['exchange_name'] == "NYSE"


def test_securities_sold_in_the_past_three_months_are_read(sample):
    rows = sample['securities_sold_past_3_months'].to_dict('records')
    assert len(rows) == 1
    assert rows[0]['seller_name'] == "Virtu Financial"
    assert rows[0]['sale_date'] == "08/27/2022"
    assert rows[0]['amount_sold'] == 0
    assert sample['nothing_to_report'] == "N"


def test_each_plan_adoption_date_keeps_its_own_text(sample):
    """These are read off the elements themselves rather than through
    `child_text`, because they have no child to look into — which makes them the
    one place in this module where lxml's `.text` truncation would bite. Duplicates
    are real data and must survive.
    """
    signature = sample['notice_signature']
    assert signature.plan_adoption_dates == ["08/15/2022", "08/15/2022", "01/02/1933"]
    assert signature.notice_date == "09/08/2022"
    assert signature.signature == "/s/ Jan van der Velden"


def test_remarks_survive(sample):
    assert sample['remarks'] == "This is new 144 form"


def test_the_amendment_sample_parses_too():
    amendment = Form144.parse_xml(SAMPLE_AMENDMENT.read_text())
    assert amendment['issuer_name']
    assert amendment['securities_information'].shape[0] >= 1


def test_a_contact_block_under_filer_info_is_read_when_one_is_present():
    """The truthiness guard, at the one place in this module where it decides a
    whole object. `<contact>` with children is truthy on both backends, but an
    empty one is falsy only on lxml — so the guard reads `is not None`.

    SEC puts `<contact>` under `<filerInfo>` as a sibling of `<filer>`, not
    inside `<filer>`, and names its children `contactName` / `contactPhoneNumber`
    / `contactEmailAddress`. `Form144.parse_xml` used to search under `<filer>`
    for `name`/`phone`/`email` and so returned `contact=None` for every real
    filing, including SEC's own sample. Fixed under edgartools-wsdm;
    `test_the_contact_block_is_read_from_the_real_sample` below asserts against
    that real sample.
    """
    parsed = Form144.parse_xml("""<?xml version="1.0" encoding="UTF-8"?>
<edgarSubmission xmlns="http://www.sec.gov/edgar/ownership"
                 xmlns:com="http://www.sec.gov/edgar/common">
  <headerData><filerInfo><filer>
      <filerCredentials><cik>0000000001</cik></filerCredentials>
  </filer>
  <contact><contactName>Dana Reid</contactName><contactPhoneNumber>555-0100</contactPhoneNumber><contactEmailAddress>dana@example.com</contactEmailAddress></contact>
  </filerInfo></headerData>
  <formData>
    <issuerInfo><issuerCik>0000000002</issuerCik>
      <relationshipsToIssuer><relationshipToIssuer>Officer</relationshipToIssuer></relationshipsToIssuer>
      <issuerAddress><com:city>Boston</com:city></issuerAddress></issuerInfo>
    <noticeSignature><noticeDate>01/02/2025</noticeDate><signature>/s/ Dana Reid</signature></noticeSignature>
  </formData>
</edgarSubmission>""")

    assert parsed['contact'].name == "Dana Reid"
    assert parsed['contact'].phone_number == "555-0100"
    assert parsed['contact'].email == "dana@example.com"


def test_the_contact_block_is_read_from_the_real_sample(sample):
    """Ground truth from SEC's own sample notice (edgartools-wsdm)."""
    contact = sample['contact']
    assert contact is not None
    assert contact.name == "Raj C"
    assert contact.phone_number == "2025516129"
    assert contact.email == "joe@gmail.com"


def test_contact_is_none_when_the_filing_has_no_contact_block():
    """A real filing with no `<contact>` element at all must yield `None`,
    not raise. `data/xml/apple.144.xml` is a genuine SEC Form 144 notice
    (Apple/Luca Maestri) whose `<filerInfo>` has no `<contact>` child."""
    xml = Path('data/xml/apple.144.xml').read_text()
    parsed = Form144.parse_xml(xml)
    assert parsed['contact'] is None


def test_parse_rejects_a_document_that_is_not_an_edgar_submission():
    with pytest.raises(ValueError, match="edgarSubmission"):
        Form144.parse_xml("<?xml version='1.0'?><ownershipDocument><a/></ownershipDocument>")
