from edgar import *
from edgar.sgml.filing_summary import Report
from edgar.files.html import TableNode
from rich import print
import pandas as pd
pd.options.display.max_columns = 20
pd.options.display.max_rows = 100

def show_attachment(attachment: Report):
    df = attachment.to_dataframe()
    print(df)


if __name__ == '__main__':
    c = Company("AAPL")
    filing = Filing(company='Apple Inc.', cik=320193, form='10-Q', filing_date='2025-05-02', accession_no='0000320193-25-000057')
    attachments = filing.attachments
    show_attachment(filing.reports[2])