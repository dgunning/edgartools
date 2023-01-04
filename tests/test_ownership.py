from pathlib import Path

from rich import print

from edgar.ownership import *
from edgar.filing import Filing

snow_form3 = OwnershipDocument.from_xml(Path('data/form3.snow.xml').read_text())
snow_form3_nonderiv = OwnershipDocument.from_xml(Path('data/form3.snow.nonderiv.xml').read_text())
snow_form4 = OwnershipDocument.from_xml(Path('data/form4.snow.xml').read_text())


def test_translate():
    assert translate_ownership('I') == 'Indirect'
    assert translate_ownership('D') == 'Direct'


holding_xml = Path("data/derivative_holding.xml").read_text()


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


def test_post_transaction_values():
    transaction: NonDerivativeTransaction = snow_form4.non_derivatives.transactions[0]
    print(transaction)
    assert transaction.security == 'Class A Common Stock'
    assert transaction.transaction_date == '2022-12-13'
    assert transaction.form == '4'
    assert transaction.equity_swap == False
    assert transaction.transaction_code == "M"
    assert transaction.acquired_disposed == 'A'
    assert transaction.num_shares == '200000'


def test_derivative_holdings_get_item():
    print()
    print(snow_form3.derivatives.holdings.data)
    holding = snow_form3.derivatives.holdings[0]
    assert holding.security == 'Series E Preferred Stock'
    assert holding.underlying_security == 'Class B Common Stock [F2,F3]'
    assert holding.underlying_shares == '134018.0'
    assert holding.exercise_price == "[F1]"
    assert holding.exercise_date == "[F1]"
    assert holding.expiration_date == "[F1]"
    assert holding.direct_indirect == 'I'
    assert holding.nature_of_ownership == 'Limited Partnership [F4]'


def test_non_derivative_holding_get_item():
    print()
    holding = snow_form3_nonderiv.non_derivatives.holdings[0]
    assert holding.security == 'Class A Common Stock'
    assert holding.direct_indirect == 'I'
    assert holding.nature_of_ownership == 'See footnote [F1]'
    print(holding)


def test_derivative_transaction_get_item():
    transaction = snow_form4.derivatives.transactions[0]
    assert transaction.num_shares == '200000'
    assert transaction.share_price == '0'
    assert transaction.form == '4'
    assert transaction.equity_swap == False
    assert transaction.transaction_code == 'M'
    assert transaction.acquired_disposed == 'A'
    assert transaction.exercise_date == '[F16]'
    assert transaction.exercise_price == '8.88'
    assert transaction.underlying_shares == '200000.0'
    assert transaction.underlying_security == 'Class A Common Stock'


def test_reporting_relationship():
    ownership = OwnershipDocument.from_xml(Path('data/form3.snow.nonderiv.xml').read_text())
    print(ownership.reporting_relationship)
    assert ownership.reporting_relationship.is_ten_pct_owner


def test_parse_form5():
    ownership = OwnershipDocument.from_xml(Path('data/form5.snow.xml').read_text())
    print()
    print(ownership)
    print(ownership.derivatives)
    print(ownership.non_derivatives)
    assert ownership.form == "5"
    assert ownership.issuer.name == 'Snowflake Inc.'
    assert ownership.issuer.cik == '0001640147'
    assert ownership.derivatives.empty
    assert not ownership.non_derivatives.empty
    assert len(ownership.non_derivatives.transactions) == 1
    assert len(ownership.non_derivatives.holdings) == 2

    assert not ownership.reporting_relationship.is_ten_pct_owner

    holding = ownership.non_derivatives.holdings[0]
    assert holding.security == 'Class A Common Stock'
    assert holding.direct_indirect == 'I'
    assert holding.nature_of_ownership == 'Trust [F3]'


def test_ownership_from_filing_xml_document():
    filing = Filing(form='3', company='Bio-En Holdings Corp.', cik=1568139,
                    date='2013-04-29', accession_no='0001477932-13-002021')
    xml = filing.xml()
    ownership_document: OwnershipDocument = OwnershipDocument.from_xml(xml)
    assert ownership_document.issuer.name == 'Olivia Inc.'

    print(ownership_document.derivatives)
    print(ownership_document.non_derivatives)
    holding = ownership_document.non_derivatives.holdings[0]
    assert holding.security == 'Common Stock'
    assert holding.direct_indirect == 'D'
