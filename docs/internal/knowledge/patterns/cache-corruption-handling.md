# Cache Corruption Handling Pattern

## Issue Pattern: JSONDecodeError from Corrupted Cache Files

**GitHub Issues**: #443

### Problem Description
Users encounter `JSONDecodeError: Expecting value: line 1 column 1 (char 0)` when accessing certain filings. This occurs when cached submissions files become corrupted (empty or invalid JSON).

### Root Cause
The `load_company_submissions_from_local()` function in `edgar/entity/submissions.py` was not handling corrupted cache files gracefully. The function would:

1. Check if cache file exists
2. If yes, directly call `json.loads(submissions_file.read_text())` without error handling
3. If the file was corrupted/empty, this would raise JSONDecodeError

### Solution Applied
Added robust error handling to detect and recover from corrupted cache files:

```python
def load_company_submissions_from_local(cik: int) -> Optional[Dict[str, Any]]:
    # ... file existence check ...

    # File exists, try to parse it
    try:
        return json.loads(submissions_file.read_text())
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        # File is corrupted, log warning and re-download
        log.warning(f"Corrupted submissions cache file for CIK {cik}: {e}. Re-downloading...")
        try:
            submissions_json = download_entity_submissions_from_sec(cik)
            if submissions_json:
                # Write the fresh data to cache
                with open(submissions_file, "w", encoding='utf-8') as f:
                    json.dump(submissions_json, f)
                return submissions_json
            else:
                # If download failed, remove the corrupted file
                submissions_file.unlink(missing_ok=True)
                return None
        except Exception as download_error:
            log.error(f"Failed to re-download submissions for CIK {cik}: {download_error}")
            # Remove the corrupted file so it can be retried later
            submissions_file.unlink(missing_ok=True)
            return None
```

### Key Improvements
1. **Graceful Error Handling**: Catches both `JSONDecodeError` and `UnicodeDecodeError`
2. **Automatic Recovery**: Re-downloads data when corruption is detected
3. **Cache Cleanup**: Removes corrupted files if recovery fails
4. **User Transparency**: Logs warnings about cache corruption
5. **Consistency**: Fixed file I/O to use consistent text mode with UTF-8 encoding

### Testing Strategy
Created comprehensive regression tests in `tests/issues/regression/test_issue_443_corrupted_cache.py`:

- Empty cache file recovery
- Invalid JSON recovery
- Binary data (UnicodeDecodeError) recovery
- End-to-end scenario testing
- Download failure cleanup
- Normal operation preservation

### Impact
- **User Experience**: Users no longer see cryptic JSONDecodeError messages
- **Reliability**: System automatically recovers from cache corruption
- **Maintainability**: Clear error handling makes debugging easier
- **Performance**: Only affects corrupted files, normal operation unchanged

### Prevention
- Robust file I/O with proper encoding
- Error handling at cache boundaries
- Comprehensive test coverage for edge cases

### Related Files
- `edgar/entity/submissions.py` - Core fix implementation
- `tests/issues/regression/test_issue_443_corrupted_cache.py` - Regression tests
- `tests/issues/reproductions/filing-access/` - Issue reproduction scripts

### Future Considerations
- Monitor cache corruption frequency to identify underlying causes
- Consider atomic file operations to prevent partial writes
- Add cache validation on startup for proactive corruption detection