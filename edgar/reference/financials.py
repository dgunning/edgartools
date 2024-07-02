from edgar.httprequests import download_file
dera_data_url = 'https://www.sec.gov/dera/data'
financial_statement_datasets='financial-statement-data-sets'

if __name__ == '__main__':
    download_file('https://www.sec.gov/files/dera/data/financial-statement-data-sets/2024q1.zip')