from edgar.storage import download_filings


if __name__ == '__main__':
    download_filings(':2025-01-03', overwrite_existing=False)