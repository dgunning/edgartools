import urllib.parse
from bs4 import BeautifulSoup
from edgar.httprequests import download_text
import pandas as pd

# Base URL for resolving relative links
SEC_BASE_URL = "https://www.sec.gov"


def _find_latest_fund_data_url():
    """Find the URL of the latest fund data CSV file from the SEC website."""
    list_url = "https://www.sec.gov/about/opendatasetsshtmlinvestment_company"
    html_content = download_text(list_url)
    soup = BeautifulSoup(html_content, 'html.parser')

    # Find all tables on the page
    tables = soup.find_all('table')

    for table in tables:
        # Look for a table with a header row containing 'File', 'Format', 'Size'
        headers = [th.get_text(strip=True) for th in table.find_all('th')]
        if 'File' in headers and 'Format' in headers and 'Size' in headers:
            # Find the index of the Format and File columns
            try:
                format_index = headers.index('Format')
                file_index = headers.index('File')
            except ValueError:
                continue # Headers not found in the expected order

            # Iterate through the rows of this table
            for row in table.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) > max(format_index, file_index):
                    # Check if the format is CSV
                    format_text = cells[format_index].get_text(strip=True)
                    if 'CSV' in format_text:
                        # Find the link in the File column
                        link_tag = cells[file_index].find('a')
                        if link_tag and 'href' in link_tag.attrs:
                            relative_url = link_tag['href']
                            # Construct the absolute URL
                            absolute_url = urllib.parse.urljoin(SEC_BASE_URL, relative_url)
                            return absolute_url
            # If CSV not found in this suitable table, continue to next table just in case
            # but typically the first one found is the correct one.

    # If no suitable table or CSV link is found after checking all tables
    raise ValueError("No fund data CSV file found on the SEC website.")


def get_fund_tickers() -> pd.DataFrame:
    """
    Downloads the latest Investment Company tickers and CIKs from the SEC website.

    Returns:
        pd.DataFrame: A DataFrame containing the fund ticker data.
                      Columns typically include 'Ticker', 'CIK', 'Series ID', 'Class ID', etc.
    """
    # Find the latest fund data file URL
    csv_url = _find_latest_fund_data_url()

    # Download the csv file into pandas
    try:
        # Provide a User-Agent header
        storage_options = {'User-Agent': 'EdgarTools/1.0 (your_email@example.com)'} # Replace with actual contact info
        fund_data = pd.read_csv(csv_url, storage_options=storage_options)
        return fund_data
    except Exception as e:
        print(f"Failed to download or parse fund data from {csv_url}. Error: {e}")
        raise


if __name__ == "__main__":
    try:
        fund_tickers_df = get_fund_tickers()
        print("Successfully downloaded fund ticker data:")
        print(fund_tickers_df.head())
        print(f"\nTotal records: {len(fund_tickers_df)}")
    except Exception as e:
        print(f"An error occurred: {e}")