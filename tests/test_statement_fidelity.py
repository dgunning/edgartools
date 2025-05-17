from edgar import *


def test_balance_sheet_matches_online():
    f = Filing(form='10-Q', filing_date='2023-11-13',
               company='AEON Biopharma, Inc.',
               cik=1837607, accession_no='0001558370-23-018706')
    print(str(f))
    xb = XBRL.parse_directory("data/xbrl/datafiles/aeon")
    #xb = XBRL.from_filing(f)
    bs = xb.statements.balance_sheet()
    print(bs)
    df = (xb.query()
        .by_concept("CashAndCashEquivalentsAtCarryingValue")
     ).to_dataframe("concept", "value", "period_end")
    print(df)

    """
    company = Company(1837607)
    filings = company.get_filings(form='10-Q')
    filings_df = filings.to_pandas()
    filings_df = filings_df[filings_df['reportDate'] == '2023-09-30']
    accession_number = filings_df['accession_number'].iloc[0]
    
    tenq = company.get_filings(form=form, accession_number=accession_number).latest(1).obj()
    df = tenq.balance_sheet.data
    print(df)
    
    line_items = df['Sep 30, 2023']
    print(line_items)
    """
