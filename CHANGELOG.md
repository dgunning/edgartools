# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.10.0] - 2025-01-26

### Changed
- This release uses SGML as the primary means of getting attachments and text from SEC filings. This is a significant change from the previous release that used the Filing homepage and access the documents directly. This will make it work better with local storage

### Added
- Implement getting attachments from the SGML text file
- Implement getting html and xml from the SGML attachments
- Add uu_decode function to decode uuencoded files

### Fixed
- Download related filings from the SEC when local storage is enabled but not yet refreshed
- Return empty filings when no filings are found for a company

## [3.9.1] - 2025-01-23

### Fixed
- Fixed bug when downloading data to local storage


## [3.9.0] - 2025-01-20


### Changed
- Refactored the code that used HTTPX client connections to reuse connections. Reusing HTTPX client connections yields about a 20ms savings per request in retrieval in limited tests. (Thanks to paul @ igmo)
- Consolidated the httpx client connection to a single edgartools.httpclient module. This will allow for more control over the client and the ability to pass the client explicitly to functions that need it.
- More logging statements when downloading filings to local storage
- Set throttling when listing the SEC filing bulk files

## [3.8.4] - 2025-01-19

### Added 
- `edgar.company` module to consolidate functions related to companies
- `public_companies` iterator over the public companies in the SEC dcik tickers list

## [3.8.3] - 2025-01-17

### Fixed
- Fix for Form **F-1** files not being detected as HTML

## [3.8.2] - 2025-01-16

### Fixed
- Fix issue with text being inadvertently printed to a notebook
- Allow for filing HTML inside <DOCUMENT> tags to be read as html

## [3.8.1] - 2025-01-15
- Minor fix for incorrect import statement introduced in 3.8.0

## [3.8.0] - 2025-01-15

### Added
- `edgar.storage` module to consolidate functions related to local storage
- Add `edgar.storage.download_filings` to download complete filings to local storage

### Changed
- Moved functions related to local storage to `edgar.storage` module