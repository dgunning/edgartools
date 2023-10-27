from pathlib import Path
import pandas as pd
from rich import print
from decimal import Decimal
from edgar.ownership import *
from edgar.ownership import compute_average_price, compute_total_value
from edgar._filings import Filing
from bs4 import BeautifulSoup


pd.options.display.max_columns = None

snow_form3 = Ownership.from_xml(Path('data/form3.snow.xml').read_text())
snow_form3_nonderiv = Ownership.from_xml(Path('data/form3.snow.nonderiv.xml').read_text())
snow_form4 = Ownership.from_xml(Path('data/form4.snow.xml').read_text())
aapl_form4 = Filing(company='Apple Inc.', cik=320193, form='4', filing_date='2023-10-03',
                             accession_no='0000320193-23-000089').obj()


def test_translate():
    assert translate_ownership('I') == 'Indirect'
    assert translate_ownership('D') == 'Direct'


holding_xml = Path("data/derivative_holding.xml").read_text()


def test_derivative_table_repr():
    form3_content = Path('data/form3.snow.xml').read_text()
    ownership = Ownership.from_xml(form3_content)
    print()
    print(snow_form4.derivative_table.transactions)
    print(ownership.derivative_table.holdings)
    print(ownership.derivative_table.transactions)
    print(ownership.derivative_table)


def test_non_derivatives_repr():
    form3_content = Path('data/form3.snow.nonderiv.xml').read_text()
    print()
    ownership = Ownership.from_xml(form3_content)
    print(snow_form4.non_derivative_table.transactions)
    print(ownership.non_derivative_table.holdings)
    print(ownership.non_derivative_table)


def test_ownership_repr():
    form3_content = Path('data/form3.snow.xml').read_text()
    print()
    ownership = Ownership.from_xml(form3_content)
    print(ownership)

    # print(ownership.footnotes)


def test_parse_form3_with_derivatives():
    form3_content = Path('data/form3.snow.xml').read_text()
    ownership = Ownership.from_xml(form3_content)
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

    assert ownership.reporting_owners[0].name == "Mark Garrett"
    assert ownership.reporting_owners[0].cik == "0001246215"

    assert ownership.remarks == "Exhibit 24 - Power of Attorney"

    # Non Derivatives for this form is empty
    assert ownership.non_derivative_table.empty
    assert not ownership.non_derivative_table.has_transactions
    assert not ownership.non_derivative_table.has_holdings
    assert ownership.non_derivative_table.empty
    assert ownership.non_derivative_table.holdings.empty
    assert ownership.non_derivative_table.transactions.empty

    # Derivatives are not empty ... there are holdings
    assert not ownership.derivative_table.empty
    assert ownership.derivative_table.has_holdings
    assert not ownership.derivative_table.holdings.empty
    assert len(ownership.derivative_table.holdings) == 6

    # But there are no transactions
    assert not ownership.derivative_table.has_transactions
    assert ownership.derivative_table.transactions.empty
    assert len(ownership.derivative_table.transactions) == 0

    assert len(ownership.signatures) == 1
    assert ownership.signatures[0].signature == "/s/ Travis Shrout, Attorney-in-Fact"

    # Security
    print(ownership.derivative_table.holdings.data)


def test_parse_form3_with_non_derivatives():
    form3_content = Path('data/form3.snow.nonderiv.xml').read_text()
    ownership = Ownership.from_xml(form3_content)
    print()
    print(ownership)
    assert ownership.form == "3"
    assert ownership.issuer.name == "Snowflake Inc."
    assert ownership.issuer.cik == "0001640147"
    assert ownership.reporting_period == "2020-09-18"

    assert ownership.reporting_owners[0].name == "BERKSHIRE HATHAWAY INC"
    assert ownership.reporting_owners[0].cik == "0001067983"

    assert ownership.remarks == ""

    # There are non-derivatives
    assert not ownership.non_derivative_table.empty

    # There are no derivatives
    assert ownership.derivative_table.empty
    assert ownership.derivative_table.holdings.empty
    assert ownership.derivative_table.transactions.empty
    assert len(ownership.derivative_table.holdings) == 0
    assert len(ownership.derivative_table.transactions) == 0

    # Signatures
    assert len(ownership.signatures) == 1
    assert ownership.signatures[0].signature == ("/s/ Warren E. Buffett, on behalf of himself and each other "
                                                 "reporting person hereunder")

def test_reporting_relationship():
    filing = Filing(form='4', filing_date='2023-10-18', company='ANDERSON SCOTT LLOYD', cik=1868662, accession_no='0001415889-23-014419')

    owner = filing.obj().reporting_owners[0]

    assert owner.is_director
    assert not owner.is_ten_pct_owner
    assert not owner.is_officer
    assert not owner.is_other

def test_post_transaction_values():
    transaction: NonDerivativeTransaction = snow_form4.non_derivative_table.transactions[0]
    print(transaction)
    assert transaction.security == 'Class A Common Stock'
    assert transaction.date == '2022-12-13'
    assert transaction.form == '4'
    assert transaction.equity_swap == False
    assert transaction.transaction_code == "M"
    assert transaction.acquired_disposed == 'A'
    assert transaction.shares == 200000


def test_derivative_holdings_get_item():
    print()
    print(snow_form3.derivative_table.holdings.data)
    holding = snow_form3.derivative_table.holdings[0]
    assert holding.security == 'Series E Preferred Stock'
    assert holding.underlying == 'Class B Common Stock [F2,F3]'
    assert holding.underlying_shares == '134018.0'
    assert holding.exercise_price == "[F1]"
    assert holding.exercise_date == "[F1]"
    assert holding.expiration_date == "[F1]"
    assert holding.direct_indirect == 'I'
    assert holding.nature_of_ownership == 'Limited Partnership [F4]'


def test_non_derivative_holding_get_item():
    print()
    holding = snow_form3_nonderiv.non_derivative_table.holdings[0]
    assert holding.security == 'Class A Common Stock'
    assert holding.shares == 6125376
    assert holding.direct == "No"
    assert holding.nature_of_ownership == 'See footnote [F1]'
    print(holding)


def test_derivative_transaction_get_item():
    transaction = snow_form4.derivative_table.transactions[0]
    assert transaction.shares == '200000'
    assert transaction.price == '0'
    assert transaction.form == '4'
    assert transaction.equity_swap == False
    assert transaction.transaction_code == 'M'
    assert transaction.acquired_disposed == 'A'
    assert transaction.exercise_date == '[F16]'
    assert transaction.exercise_price == '8.88'
    assert transaction.underlying_shares == '200000.0'
    assert transaction.underlying == 'Class A Common Stock'


def test_parse_reporting_owners_from_xml():
    soup = BeautifulSoup(Path('data/form3.snow.nonderiv.xml').read_text(), 'xml')
    reporting_owner_tags = soup.find_all("reportingOwner")
    reporting_owners:ReportingOwners = ReportingOwners.from_reporting_owner_tags(reporting_owner_tags)
    assert reporting_owners
    assert len(reporting_owners) == 2

    owner:Owner = reporting_owners[0]
    assert owner.name == 'BERKSHIRE HATHAWAY INC'
    assert owner.cik == '0001067983'
    assert not owner.is_director
    assert owner.is_ten_pct_owner
    assert not owner.is_officer
    assert not owner.is_other
    assert owner.address.street1 == '3555 FARNAM STREET'
    assert owner.address.street2 == ''
    assert owner.address.city == 'OMAHA'
    assert owner.address.state_or_country == 'NE'
    assert owner.address.zipcode == '68131'

    warren = reporting_owners[1]
    assert warren.name == 'Warren E Buffett'
    assert warren.cik == '0000315090'
    assert not warren.is_director
    assert warren.is_ten_pct_owner
    assert not warren.is_officer

    print(reporting_owners)


def test_parse_form5():
    ownership = Ownership.from_xml(Path('data/form5.snow.xml').read_text())
    print()
    print(ownership)
    print(ownership.derivative_table)
    print(ownership.non_derivative_table)
    assert ownership.form == "5"
    assert ownership.issuer.name == 'Snowflake Inc.'
    assert ownership.issuer.cik == '0001640147'
    assert ownership.derivative_table.empty
    assert not ownership.non_derivative_table.empty
    assert len(ownership.non_derivative_table.transactions) == 1
    assert len(ownership.non_derivative_table.holdings) == 2

    assert not ownership.reporting_owners[0].is_ten_pct_owner

    holding: NonDerivativeHolding = ownership.non_derivative_table.holdings[0]
    assert holding.security == 'Class A Common Stock'
    assert holding.direct == "No"
    assert holding.nature_of_ownership == 'Trust [F3]'


def test_ownership_from_filing_xml_document():
    filing = Filing(form='3', company='Bio-En Holdings Corp.', cik=1568139,
                    filing_date='2013-04-29', accession_no='0001477932-13-002021')
    xml = filing.xml()
    ownership_document: Ownership = Ownership.from_xml(xml)
    assert ownership_document.issuer.name == 'Olivia Inc.'

    print(ownership_document.derivative_table)
    print(ownership_document.non_derivative_table)
    holding = ownership_document.non_derivative_table.holdings[0]
    assert holding.security == 'Common Stock'
    assert holding.direct


def test_no_securities_owned():
    form3_nosecurities = Ownership.from_xml(Path('data/form3.nosecurities.xml').read_text())
    assert form3_nosecurities.no_securities
    print()
    print(form3_nosecurities)


def test_aapl_form4():
    filing = Filing(company='Apple Inc.', cik=320193, form='4', filing_date='2023-10-17',
                    accession_no='0000320193-23-000099')
    ownership = filing.obj()
    assert len(ownership.derivative_table.transactions) == 4
    print()
    print(ownership)


def test_correct_number_of_transactions_for_form4(capsys):
    filing = Filing(company='Day One Biopharmaceuticals, Inc.', cik=1845337, form='4', filing_date='2023-10-20',
                    accession_no='0001209191-23-053235')
    ownership = filing.obj()
    assert len(ownership.non_derivative_table.transactions) == 3
    print()
    print(ownership)
    out, err = capsys.readouterr()
    with capsys.disabled():
        assert "Day One Biopharmaceuticals" in out


def test_form3_shows_holdings(capsys):
    filing = Filing(form='3', filing_date='2023-10-23', company='22NW Fund GP, LLC', cik=1770575,
                    accession_no='0000921895-23-002362')
    ownership = filing.obj()
    assert isinstance(ownership, Form3)
    # print the ownership and test that it contains "By: 22NW Fund LP"
    print()
    print(ownership)
    out, err = capsys.readouterr()
    with capsys.disabled():
        assert "By: 22NW Fund, LP" in out


def test_form5_shows_transactions(capsys):
    filing = Filing(form='5', filing_date='2023-10-18', company='COSTCO WHOLESALE CORP /NEW', cik=909832,
                    accession_no='0001209191-23-053139')
    ownership = filing.obj()

    print()
    print(ownership)
    out, err = capsys.readouterr()
    with capsys.disabled():
        print(ownership)
        assert "COSTCO WHOLESALE CORP /NEW" in out
        assert "+461" in out


def test_form4_common_trades():
    filing = Filing(company='Day One Biopharmaceuticals, Inc.', cik=1845337, form='4', filing_date='2023-10-20',
                    accession_no='0001209191-23-053235')
    form4: Form4 = filing.obj()

    # Common stock transactions
    common_stock_trades = form4.common_trades
    assert not common_stock_trades.empty
    assert len(common_stock_trades) == 3
    assert common_stock_trades.data.iloc[2].Shares == 111387
    assert common_stock_trades.data.iloc[2].Code == 'P'
    print(form4)

    # Shares trades
    assert form4.shares_traded == 1475454.0

    # Common stock transactions
    common_trades = aapl_form4.common_trades
    assert len(common_trades) == 3
    print()
    print(common_trades[['Date', 'Security', 'Shares', 'Remaining', 'Price', 'Code', 'TransactionType']])

    # This filing has lots of common and derivative tradeds and some missing prices
    filing = Filing(form='4', filing_date='2023-10-25', company='210 Capital, LLC', cik=1694780,
                    accession_no='0000899243-23-020039')
    form4 = filing.obj()
    # The common trades should be empty because there are no Sales (S) or Purchases (P)
    assert form4.common_trades.empty


def test_form4_derivative_trades():
    # Get exercised trades from the non derivative table
    exercised_trades = aapl_form4.non_derivative_table.exercised_trades
    assert not exercised_trades.empty
    assert len(exercised_trades) == 1
    assert exercised_trades.iloc[0].Security == 'Common Stock'
    assert exercised_trades.iloc[0].Shares == 511000

    # Now get derivative trades from the derivative table
    derivative_table_trades = aapl_form4.derivative_table.derivative_trades
    print(derivative_table_trades)
    assert len(derivative_table_trades) == 3

    # Now get all derivative trades.
    derivative_trades = aapl_form4.derivative_trades
    print(derivative_trades)
    assert len(derivative_trades) == 3
    assert derivative_trades.iloc[0].Security == 'Restricted Stock Unit'
    assert derivative_trades.iloc[0].Shares == '511000'

"""
def test_form4_derivative_trades_include_exercised():

    filing = Filing(form='4', filing_date='2023-10-25', company='AAON, INC.', cik=824142, accession_no='0000824142-23-000163')
    form4 = filing.obj()
    derivatives = form4.derivative_trades
    print(derivatives.data)
    assert derivatives.data.iloc[0].Security == 'Common Stock, par value $.004'
    assert derivatives.data.iloc[0].Shares == 321
"""

def test_insider_stock_summary():
    common_trade_summary = aapl_form4.insider_stock_summary
    print()
    print(common_trade_summary)
    assert common_trade_summary.insider == 'Timothy D Cook'
    assert common_trade_summary.shares_traded == 240569


def test_form4_fields_summary():
    filing = Filing(company='Day One Biopharmaceuticals, Inc.', cik=1845337, form='4', filing_date='2023-10-20',
                    accession_no='0001209191-23-053235')
    form4: Form4 = filing.obj()
    print()
    print(form4)
    assert form4.shares_traded == 1475454.0

    filing = Filing(form='4', filing_date='2023-10-24', company='AMKOR TECHNOLOGY, INC.', cik=1047127,
                    accession_no='0001209191-23-053496')
    form4: Form4 = filing.obj()
    print(form4)
    assert form4.shares_traded == 2700.0

def test_compute_total_value():
    shares = pd.Series([100, 200, 300])
    price = pd.Series([10, 20, 30])
    total_value = compute_total_value(shares, price)
    assert total_value == 14000

def test_compute_average_price():
    shares = pd.Series([100, 200, 300])
    price = pd.Series([10, 20, 30])
    average_price = compute_average_price(shares, price)
    assert average_price == Decimal('23.33')