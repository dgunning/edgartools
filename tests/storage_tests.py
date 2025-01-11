from edgar.storage import download_filing_in_bulk


if __name__ == '__main__':
    download_filing_in_bulk(':2025-01-03', overwrite_existing=False)