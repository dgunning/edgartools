from edgar.ownership import *
from edgar.ownership import security, underlying_security
from pathlib import Path
from rich import print
from bs4 import BeautifulSoup


def test_translate():
    assert translate_ownership('I') == 'Indirect'
    assert translate_ownership('D') == 'Direct'


def test_parse_security():
    tag = (BeautifulSoup("<root><securityTitle><value>Series E</value></securityTitle></root>", "xml")
           .find("root"))
    assert security(tag) == ("security", "Series E")


def test_parse_underlying_security():
    tag = (BeautifulSoup("<root><underlyingSecurityTitle><value>Series E</value></underlyingSecurityTitle></root>",
                         "xml")
           .find("root"))
    assert underlying_security(tag) == ("underlying_security", "Series E")


def test_parse_form3_with_derivatives():
    form3_content = Path('data/form3.snow.xml').read_text()
    ownership = OwnershipDocument.from_xml(form3_content)
    print(ownership)

    # There should be a footnotes section
    assert ownership.footnotes
    assert len(ownership.footnotes) == 9
    assert ownership.footnotes["F1"] == ("Each share of Series E Preferred Stock will automatically convert into one "
                                         "share of Class B Common Stock immediately upon the closing of the Issuer's "
                                         "initial public offering (IPO), and has no expiration date.")

    assert ownership.form == "3"
    assert ownership.issuer.name == "Snowflake Inc."
    assert ownership.issuer.cik == "0001640147"
    assert ownership.reporting_period == "2020-09-15"

    assert ownership.reporting_owner.name == "GARRETT MARK"
    assert ownership.reporting_owner.cik == "0001246215"

    assert ownership.remarks == "Exhibit 24 - Power of Attorney"

    # Non Derivatives for this form is empty
    assert ownership.non_derivatives.empty
    assert not ownership.non_derivatives.has_transactions
    assert not ownership.non_derivatives.has_holdings
    assert ownership.non_derivatives.empty
    assert ownership.non_derivatives.holdings.empty
    assert ownership.non_derivatives.transactions.empty

    # Derivatives are not empty .. there are holdings
    assert not ownership.derivatives.empty
    assert ownership.derivatives.has_holdings
    assert not ownership.derivatives.holdings.empty
    assert len(ownership.derivatives.holdings) == 6

    # But there are no transactions
    assert not ownership.derivatives.has_transactions
    assert ownership.derivatives.transactions.empty
    assert len(ownership.derivatives.transactions) == 0

    assert len(ownership.signatures) == 1
    assert ownership.signatures[0].signature == "/s/ Travis Shrout, Attorney-in-Fact"

    # Security
    print(ownership.derivatives.holdings.data)


def test_parse_form3_with_non_derivatives():
    form3_content = Path('data/form3.snow.nonderiv.xml').read_text()
    ownership = OwnershipDocument.from_xml(form3_content)
    assert ownership.form == "3"
    assert ownership.issuer.name == "Snowflake Inc."
    assert ownership.issuer.cik == "0001640147"
    assert ownership.reporting_period == "2020-09-18"

    assert ownership.reporting_owner.name == "BERKSHIRE HATHAWAY INC"
    assert ownership.reporting_owner.cik == "0001067983"

    assert ownership.remarks == ""

    # There are non-derivatives
    assert not ownership.non_derivatives.empty

    # There are no derivatives
    assert ownership.derivatives.empty
    assert ownership.derivatives.holdings.empty
    assert ownership.derivatives.transactions.empty
    assert len(ownership.derivatives.holdings) == 0
    assert len(ownership.derivatives.transactions) == 0

    # Signatures
    assert len(ownership.signatures) == 1
    assert ownership.signatures[0].signature == ("/s/ Warren E. Buffett, on behalf of himself and each other "
                                                 "reporting person hereunder")


def test_reporting_relationship():
    ownership = OwnershipDocument.from_xml(Path('data/form3.snow.nonderiv.xml').read_text())
    print(ownership.reporting_relationship)
    assert ownership.reporting_relationship.is_ten_pct_owner
