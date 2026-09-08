"""What `FormD.from_xml` owes its callers, with no network.

`edgar/offerings/exempt/formd.py` and `Issuer.from_xml` in `edgar/_party.py` are
one unit — the second is only ever called by the first — and both moved from
BeautifulSoup to lxml under edgartools-07lk.11.3.

Form D is one of the few SEC form XMLs with NO namespace, so the hazard here is
not the searches; it is the guards. This module builds most of its objects with
`X if element else None`, and an lxml element with no children is falsy where the
bs4 one is truthy — so a merely-empty `<investors/>` or `<offeringSalesAmounts/>`
would take the same branch as an absent one and produce `None` for a section that
is present.

`tests/test_formd_offerings.py` is classified `network` in `tests/conftest.py`, so
nothing added there runs in the fast job. Ground truth is the three Form D notices
checked in under `data/`.
"""
from pathlib import Path

import pytest

from edgar.offerings.exempt.formd import FormD

AP_FUND = Path('data/D.APFund.xml')
SHEPHERDS = Path('data/D.Shepards.xml')
REIT_1685 = Path('data/D.1685REIT.xml')


@pytest.fixture(scope="module")
def ap_fund():
    return FormD.from_xml(AP_FUND.read_text())


def test_the_issuer_block_is_read(ap_fund):
    issuer = ap_fund.primary_issuer
    assert issuer.cik == "0001958740"
    assert issuer.entity_name == "AP Fund IV, a series of Inference Technology Partners, LP"
    assert issuer.jurisdiction == "DELAWARE"
    assert issuer.entity_type == "Limited Partnership"
    assert issuer.year_of_incorporation == "2022"
    assert issuer.incorporated_within_5_years is True
    assert ap_fund.submission_type == "D"
    assert ap_fund.is_live is True


def test_the_issuer_address_is_read(ap_fund):
    address = ap_fund.primary_issuer.primary_address
    assert address.street1 == "119 South Main Street"
    assert address.city == "Seattle"
    assert address.state_or_country == "WA"
    assert address.zipcode == "98104"


def test_related_persons_keep_their_relationships(ap_fund):
    """The #874 path. `<relationship>` text is read off the element itself, which
    is the read lxml truncates at the first child."""
    people = [(p.first_name, p.last_name, p.relationships) for p in ap_fund.related_persons]
    assert people == [("Ltd.", "Belltower Fund Group", ["Director"]),
                      ("LLC", "Fund GP,", ["Director"])]


def test_the_offering_sections_are_each_present(ap_fund):
    """Each of these is built by an `if element else None` ternary, so a guard that
    read truthiness instead of identity would turn a populated section into None."""
    offering = ap_fund.offering_data

    assert offering.industry_group.industry_group_type == "Pooled Investment Fund"
    assert offering.industry_group.investment_fund_info.investment_fund_type == "Venture Capital Fund"
    assert offering.industry_group.investment_fund_info.is_40_act is False

    assert offering.revenue_range == "Decline to Disclose"
    assert offering.federal_exemptions == ["06b", "3C.1"]
    # D.APFund.xml files <submissionType>D</submissionType> with
    # <isAmendment>false</isAmendment>, so this is a base notice (gh #1192).
    assert offering.is_new is True
    assert offering.more_than_one_year is False
    assert offering.is_equity is False
    assert offering.is_pooled_investment is True
    assert offering.minimum_investment == "1400"

    assert offering.offering_sales_amounts.total_offering_amount == "659752"
    assert offering.offering_sales_amounts.total_amount_sold == "659752"
    assert offering.offering_sales_amounts.total_remaining == "0"

    assert offering.investors.has_non_accredited_investors is False
    assert offering.investors.total_already_invested == "27"


def test_the_signature_block_keeps_every_signature(ap_fund):
    assert [(s.signature_name, s.name_of_signer, s.date) for s in ap_fund.signature_block.signatures] == [
        ("Cathy Bui", "Cathy Bui", "2023-01-30"),
        ("Cathy Bui", "Cathy Bui", "2023-01-30")]
    assert ap_fund.signature_block.signatures[0].issuer_name == (
        "AP Fund IV, a series of Inference Technology Partners, LP")


def test_sales_compensation_recipients_are_read():
    """A recipient carries a nested address and a states-of-solicitation list whose
    entries appear as either `<state>` or `<value>`; both are collected."""
    parsed = FormD.from_xml("""<?xml version="1.0"?>
<edgarSubmission>
  <primaryIssuer><cik>0000000001</cik><entityName>Example Fund LP</entityName></primaryIssuer>
  <relatedPersonsList/>
  <offeringData>
    <industryGroup><industryGroupType>Other</industryGroupType></industryGroup>
    <issuerSize><revenueRange>Decline to Disclose</revenueRange></issuerSize>
    <typeOfFiling><newOrAmendment><isAmendment>false</isAmendment></newOrAmendment></typeOfFiling>
    <typesOfSecuritiesOffered><isEquityType>true</isEquityType></typesOfSecuritiesOffered>
    <salesCompensationList>
      <recipient>
        <recipientName>Broker One</recipientName>
        <recipientCRDNumber>123456</recipientCRDNumber>
        <recipientAddress><street1>1 Main St</street1><city>Atlanta</city>
          <stateOrCountry>GA</stateOrCountry></recipientAddress>
        <statesOfSolicitationList><state>FL</state><state>GA</state>
          <value>All States</value></statesOfSolicitationList>
      </recipient>
      <recipient><recipientName>None</recipientName><recipientCRDNumber>None</recipientCRDNumber></recipient>
    </salesCompensationList>
    <useOfProceeds><grossProceedsUsed><dollarAmount>0</dollarAmount></grossProceedsUsed>
      <clarificationOfResponse>n/a</clarificationOfResponse></useOfProceeds>
  </offeringData>
  <signatureBlock/>
</edgarSubmission>""")

    recipients = parsed.offering_data.sales_compensation_recipients
    assert len(recipients) == 2
    assert recipients[0].name == "Broker One"
    assert recipients[0].crd == "123456"
    assert recipients[0].address.city == "Atlanta"
    assert recipients[0].states_of_solicitation == ["FL", "GA", "All States"]
    # The literal string "None" is SEC's way of writing "not applicable" and is
    # stripped to empty rather than kept.
    assert recipients[1].name == ""
    assert recipients[1].address is None
    assert recipients[1].states_of_solicitation == []


def test_a_previous_name_list_of_literal_none_reads_as_no_previous_names(ap_fund):
    """SEC writes the string "None" when there are no previous names, in both
    spellings of the child element. It must not become a name."""
    assert ap_fund.primary_issuer.edgar_previous_names == []
    assert ap_fund.primary_issuer.issuer_previous_names == []
    assert FormD.from_xml(REIT_1685.read_text()).primary_issuer.issuer_previous_names == []


def test_previous_names_in_the_other_spelling_are_read():
    """SEC writes previous names as `<value>` in most filings but `<previousName>`
    in others — 7 of 42 Form D filings sampled across 2022-2025 use that spelling
    with real values. Both are read (edgartools-gi0a): Shepherd's Finance was
    renamed from "84 RE Partners, LLC" and the parser returns it.
    """
    shepherds = FormD.from_xml(SHEPHERDS.read_text())
    assert "84 RE Partners, LLC" in SHEPHERDS.read_text()
    assert shepherds.primary_issuer.issuer_previous_names == ["84 RE Partners, LLC"]


def test_from_xml_rejects_a_document_that_is_not_an_edgar_submission():
    with pytest.raises(ValueError, match="edgarSubmission"):
        FormD.from_xml("<?xml version='1.0'?><ownershipDocument><a/></ownershipDocument>")
