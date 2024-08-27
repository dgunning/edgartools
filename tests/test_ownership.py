from decimal import Decimal
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup
from rich import print

from edgar._filings import Filing
from edgar.ownership import *
from edgar.ownership.form345 import compute_average_price, compute_total_value, format_amount, is_numeric

pd.options.display.max_columns = None

snow_form3 = Ownership.from_xml(Path('data/form3.snow.xml').read_text())
snow_form3_nonderiv = Ownership.from_xml(Path('data/form3.snow.nonderiv.xml').read_text())
snow_form4 = Ownership.from_xml(Path('data/form4.snow.xml').read_text())
aapl_form4: Ownership = Filing(company='Apple Inc.', cik=320193, form='4', filing_date='2023-10-03',
                               accession_no='0000320193-23-000089').obj()


def test_is_numeric():
    # Test that these pandas series are numeric
    assert is_numeric(pd.Series([1, 2, 3]))
    assert is_numeric(pd.Series([1.0, 2.0, 3.0]))
    assert is_numeric(pd.Series([1.0, 2.0, 3.0, None]))
    assert not is_numeric(pd.Series([1.0, 2.0, 3.0, '']))
    assert not is_numeric(pd.Series([1.0, 2.0, 3.0, 'None']))
    assert is_numeric(pd.Series([1.0, 2.0, 3.0, 'nan']))
    assert is_numeric(pd.Series([1.0, 2.0, 3.0, 'NAN']))


def test_translate():
    assert translate_ownership('I') == 'Indirect'
    assert translate_ownership('D') == 'Direct'


def test_derivative_table_repr():
    form3_content = Path('data/form3.snow.xml').read_text()
    ownership = Ownership.from_xml(form3_content)
    print()
    print(ownership)
    print()
    # print(snow_form4.derivative_table.transactions)
    # print(ownership.derivative_table.holdings)
    # print(ownership.derivative_table.transactions)
    # print(ownership.derivative_table)


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
    assert ownership.signatures.signatures[0].signature == "/s/ Travis Shrout, Attorney-in-Fact"

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
    assert ownership.signatures.signatures[0].signature == (
        "/s/ Warren E. Buffett, on behalf of himself and each other "
        "reporting person hereunder")


def test_reporting_relationship():
    filing = Filing(form='4', filing_date='2023-10-18', company='ANDERSON SCOTT LLOYD', cik=1868662,
                    accession_no='0001415889-23-014419')

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
    assert holding.underlying_shares == 134018.0
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
    assert transaction.shares == 200000
    assert transaction.price == 0
    assert transaction.form == '4'
    assert transaction.equity_swap == False
    assert transaction.transaction_code == 'M'
    assert transaction.acquired_disposed == 'A'
    assert transaction.exercise_date == '[F16]'
    assert transaction.exercise_price == 8.88
    assert transaction.underlying_shares == 200000.0
    assert transaction.underlying == 'Class A Common Stock'


def test_parse_reporting_owners_from_xml():
    soup = BeautifulSoup(Path('data/form3.snow.nonderiv.xml').read_text(), 'xml')
    reporting_owner_tags = soup.find_all("reportingOwner")
    reporting_owners: ReportingOwners = ReportingOwners.from_reporting_owner_tags(reporting_owner_tags, remarks='')
    assert reporting_owners
    assert len(reporting_owners) == 2

    owner: Owner = reporting_owners[0]
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
    # Test that there are no derivative transactions
    assert ownership.derivative_table.empty

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


def test_ownership_transaction_with_non_numeric_price():
    filing = Filing(form='4', filing_date='2024-01-30', company='Adams Diane', cik=1475901,
                    accession_no='0001209191-24-002430')
    form4: Form4 = filing.obj()
    print()
    print(form4)


def test_ownership_from_filing_xml_document():
    filing = Filing(form='3', company='Bio-En Holdings Corp.', cik=1568139,
                    filing_date='2013-04-29', accession_no='0001477932-13-002021')
    xml = filing.xml()
    print()
    form3: Form3 = Form3(**Ownership.parse_xml(xml))
    assert form3.issuer.name == 'Olivia Inc.'
    assert form3.form == '3'

    assert len(form3.reporting_owners) == 1
    assert form3.reporting_owners[0].name == 'Eliyahu Prager'
    assert form3.reporting_owners[0].cik == '0001568141'
    assert form3.reporting_owners[0].is_director
    assert form3.reporting_owners[0].is_officer
    assert form3.reporting_owners[0].is_ten_pct_owner
    assert form3.reporting_owners[0].address.city == 'LOS ANGELES'

    # Has no derivative transactions
    assert form3.derivative_table.empty
    assert not form3.non_derivative_table.empty

    # Has holdings
    assert not form3.non_derivative_table.holdings.empty
    holdings = form3.non_derivative_table.holdings
    assert len(holdings) == 1
    holding = holdings[0]
    assert holding.security == 'Common Stock'
    assert holding.direct
    assert holding.nature_of_ownership == ''

    assert holding.shares == 250000

    print(form3)

    print()

    # print(ownership_document.derivative_table)
    # print(ownership_document.non_derivative_table)

    holding = form3.non_derivative_table.holdings[0]
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
        assert "Aron R. English" in out


def test_form5_common_transactions():
    filing = Filing(form='5', filing_date='2023-10-18', company='COSTCO WHOLESALE CORP /NEW', cik=909832,
                    accession_no='0001209191-23-053139')
    ownership: Form5 = filing.obj()
    assert ownership.form == '5'

    print()
    # Common stock transactions

    # Get common transactions
    common_transactions = ownership.non_derivative_table.transactions
    # Test individual transactions
    transaction = common_transactions[0]
    assert transaction.date == '2018-09-27'
    assert transaction.security == 'Common Stock'
    assert transaction.shares == 413
    assert transaction.remaining == 413
    assert transaction.price is None
    assert transaction.transaction_type == 'Purchase'

    print(ownership)


def test_form4_common_trades():
    filing = Filing(company='Day One Biopharmaceuticals, Inc.', cik=1845337, form='4', filing_date='2023-10-20',
                    accession_no='0001209191-23-053235')
    form4: Form4 = filing.obj()
    print()

    # Common stock transactions
    common_stock_trades = form4.market_trades
    assert not common_stock_trades.empty
    assert len(common_stock_trades) == 3
    assert common_stock_trades.iloc[2].Shares == 111387
    assert common_stock_trades.iloc[2].Code == 'P'
    print(form4)

    # Shares trades
    assert form4.shares_traded == 1475454.0

    # Common stock transactions
    common_trades = aapl_form4.market_trades
    assert len(common_trades) == 3
    print()
    print(common_trades[['Date', 'Security', 'Shares', 'Remaining', 'Price', 'Code', 'TransactionType']])

    # This filing has lots of common and derivative trades and some missing prices
    filing = Filing(form='4', filing_date='2023-10-25', company='210 Capital, LLC', cik=1694780,
                    accession_no='0000899243-23-020039')
    form4 = filing.obj()
    # The common trades should be empty because there are no Sales (S) or Purchases (P)
    assert form4.market_trades.empty


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
    assert derivative_trades.data.iloc[0].Security == 'Restricted Stock Unit'
    assert derivative_trades.data.iloc[0].Shares == 511000

    print(type(aapl_form4.derivative_table.derivative_trades))


def test_derivative_disposed_and_acquired():
    filing = Filing(form='4', filing_date='2023-05-22', company='BrightView Holdings, Inc.', cik=1734713,
                    accession_no='0001209191-23-031406')
    form4: Ownership = filing.obj()
    non_derivative_table = form4.non_derivative_table
    derivative_table = form4.derivative_table
    print()
    print(non_derivative_table)
    print(derivative_table)
    disposals = derivative_table.transactions.disposals
    assert len(disposals) == 1
    assert disposals.iloc[0].Shares == 1500
    print(form4.non_derivative_table.exercised_trades)


def test_form4_derivative_trades_include_exercised():
    filing = Filing(form='4', filing_date='2023-10-25', company='AAON, INC.', cik=824142,
                    accession_no='0000824142-23-000163')
    form4: Form4 = filing.obj()
    print()
    print(form4)
    assert form4.issuer.name == 'AAON, INC.'
    assert form4.reporting_period == '2023-10-23'
    assert len(form4.reporting_owners) == 1
    assert form4.reporting_owners[0].name == 'Gordon Douglas Wichman'


def test_form4_fields_summary():
    filing = Filing(company='Day One Biopharmaceuticals, Inc.', cik=1845337, form='4', filing_date='2023-10-20',
                    accession_no='0001209191-23-053235')
    form4: Form4 = filing.obj()
    print()
    assert form4.shares_traded == 1475454.0

    filing = Filing(form='4', filing_date='2023-10-24', company='AMKOR TECHNOLOGY, INC.', cik=1047127,
                    accession_no='0001209191-23-053496')
    form4: Form4 = filing.obj()
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


def test_compute_ownership_title():
    assert Owner.display_title(officer_title="Chief Executive Officer", is_director=True,
                               is_ten_pct_owner=False) == "Chief Executive Officer"
    assert Owner.display_title(officer_title=None, is_director=True, is_ten_pct_owner=False) == "Director"
    assert Owner.display_title(officer_title=None, is_director=False, is_officer=True,
                               is_ten_pct_owner=False) == "Officer"
    assert Owner.display_title(officer_title=None, is_director=False, is_officer=True,
                               is_ten_pct_owner=True) == "Officer, 10% Owner"
    assert Owner.display_title(officer_title=None, is_director=True, is_officer=False,
                               is_ten_pct_owner=True) == "Director, 10% Owner"


def test_ownership_with_multiple_owners():
    filing = Filing(form='4', filing_date='2024-01-26', company='OrbiMed Genesis GP LLC', cik=1808744,
                    accession_no='0000950170-24-008053')
    form4: Ownership = filing.obj()
    print()
    print(form4)
    assert len(form4.reporting_owners) == 8
    assert form4.reporting_owners[0].name == 'ORBIMED ADVISORS LLC'
    assert form4.reporting_owners[0].is_ten_pct_owner
    assert form4.reporting_owners[0].position == 'Director, 10% Owner'
    assert form4.reporting_owners[0].officer_title is None


def test_ownership_with_remarks():
    filing = Filing(form='4', filing_date='2021-09-17', company='Kerrest Jacques Frederic', cik=1700842,
                    accession_no='0001209191-21-056678')
    form4: Ownership = filing.obj()
    assert form4.reporting_owners[
               0].officer_title == 'Executive Vice Chairperson of the Board and Chief Operating Officer'
    assert form4.remarks == 'Executive Vice Chairperson of the Board and Chief Operating Officer'


def test_insider_transaction_sell():
    # Sell
    filing = Filing(form='4', filing_date='2024-01-18', company='MAHON PAUL A', cik=1231589,
                    accession_no='0001415889-24-001537')
    form4: Ownership = filing.obj()

    insider_transaction = form4.get_insider_market_trade_summary()
    assert insider_transaction.owner == 'Paul A Mahon'
    assert insider_transaction.position == 'EVP & GENERAL COUNSEL'
    assert insider_transaction.buy_sell == 'Sell'
    assert insider_transaction.shares == 6000.0
    assert insider_transaction.price == 218.72
    assert insider_transaction.remaining == 36599.0
    print()
    print(form4)


def test_insider_transaction_buy():
    # Buy
    filing = Filing(form='4', filing_date='2024-01-18', company='FROST PHILLIP MD ET AL', cik=898860,
                    accession_no='0000950170-24-005448')
    form4: Ownership = filing.obj()
    insider_transaction = form4.get_insider_market_trade_summary()
    assert insider_transaction.owner == 'Phillip Frost MD ET AL and one other'
    assert insider_transaction.position == 'CEO & Chairman'
    assert insider_transaction.buy_sell == 'Buy'
    assert insider_transaction.shares == 400000.0
    assert insider_transaction.price == 0.97
    assert insider_transaction.remaining == 205368225.0
    print()
    print(form4)


def test_format_amount():
    assert format_amount(100000) == '100,000'
    assert format_amount(100000.0) == '100,000'
    assert format_amount(100000.11) == '100,000.11'
    assert format_amount(100000.1) == '100,000.10'
    assert format_amount(1100000.013) == '1,100,000.01'
    assert format_amount(1100000.019) == '1,100,000.02'
    assert format_amount(1100000.91) == '1,100,000.91'


def test_ownership_with_no_company():
    # These filings failed because no company was found for the reporting owner
    filing = Filing(form='4', filing_date='2024-08-26', company='Gray Zarrell Thomas', cik=2030612,
                    accession_no='0001437749-24-027791')
    form4: Ownership = filing.obj()
    assert form4

    filing = Filing(form='4', filing_date='2024-08-26', company='HALLADOR ENERGY CO', cik=788965,
                    accession_no='0001437749-24-027791')
    form4: Ownership = filing.obj()
    assert form4
    filing = Filing(form='4', filing_date='2024-08-23', company='Hut 8 Corp.', cik=1964789, accession_no='0001127602-24-022866')
    form4: Ownership = filing.obj()
    assert form4
