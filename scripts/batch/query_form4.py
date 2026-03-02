from edgar import *
from tqdm import tqdm
import pandas as pd


def query_owner_positions():
    filings = get_filings(year=[2021, 2022, 2023], form=4).sample(400)
    records = []
    for filing in tqdm(filings):
        form4 = filing.obj()
        for owner in form4.reporting_owners.owners:
            record = {'accession_number': filing.accession_no,
                      'filing_date': filing.filing_date,
                      'owner': owner.name,
                      'is_company': owner.is_company,
                      'title': owner.officer_title,
                      'director': owner.is_director,
                      'officer': owner.is_officer,
                      'ten_percent_owner': owner.is_ten_pct_owner,
                      'other': owner.is_other,
                      'position': owner.position}
            records.append(record)
    df = pd.DataFrame(records)
    df.to_csv('data/Form4_OwnerPositions.csv', index=False)


if __name__ == '__main__':
    query_owner_positions()
