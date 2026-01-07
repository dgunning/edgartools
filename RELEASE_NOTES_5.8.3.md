# EdgarTools 5.8.3 Release Notes

Release Date: January 7, 2026

## Overview

This is a bug fix release addressing three data accuracy issues in XBRL statement handling.

## Bug Fixes

### Statement of Equity Labels and Dimensional Matching (#583)
- Fixed incorrect labels in Statement of Equity
- Improved dimensional value matching for equity statements
- Ensures accurate representation of equity transactions

### Period Selection Logging (#585)
- Downgraded period selection fallback messages from warning to debug level
- Reduces log noise for normal operations
- Improves user experience with cleaner output

### Combined Statement Support (#584)
- Added support for combined Operations and Comprehensive Income statements
- Specifically addresses REGN (Regeneron) filing format
- Enhances compatibility with diverse XBRL presentation formats

## Impact

All three fixes improve data accuracy and reliability when parsing XBRL financial statements. No breaking changes or API modifications.

## Installation

```bash
pip install edgartools==5.8.3
```

## Upgrade Notes

This release is fully backward compatible. Upgrading is recommended for all users to benefit from improved XBRL statement accuracy.

## Thanks

Thanks to all contributors who reported these issues and helped improve EdgarTools.
