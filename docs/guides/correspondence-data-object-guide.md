---
description: Parse SEC correspondence filings (CORRESP/UPLOAD) with Python. Access comment letters, company responses, and reconstruct full review threads using edgartools.
---

# SEC Correspondence: Parse Comment Letters and Review Threads with Python

When the SEC reviews a filing, a back-and-forth conversation happens through CORRESP and UPLOAD filings. The SEC sends comment letters (UPLOAD), the company responds (CORRESP), and the cycle repeats until the review is complete. EdgarTools parses these into structured Python objects with automatic classification, metadata extraction, and full thread reconstruction.

```python
from edgar import *

filing = Company("SNOW").get_filings(form="CORRESP").latest()
corresp = filing.obj()
corresp
```

Two lines to get a parsed correspondence filing with sender, type classification, file number, and referenced form.

---

## How Correspondence Works at the SEC

SEC correspondence filings are the paper trail of the filing review process:

| Form | Direction | What it is |
|------|-----------|------------|
| **UPLOAD** | SEC to company | Comment letters, review-complete notices |
| **CORRESP** | Company to SEC | Responses to comments, acceleration requests |

These filings reference each other by **file number** (e.g., `333-293459` for registration statements, `001-36743` for exchange filings) and **referenced form** (e.g., `S-1`, `10-K`). EdgarTools uses these to reconstruct the full conversation thread.

---

## Access Correspondence Metadata

Every correspondence filing is automatically classified and its metadata extracted from the "Re:" block:

```python
corresp.correspondence_type   # CorrespondenceType.COMPANY_RESPONSE
corresp.sender                 # 'company' or 'sec'
corresp.referenced_file_number # '333-293459'
corresp.referenced_form        # 'S-1'
corresp.response_date          # 'March 15, 2024' (if present)
corresp.fiscal_year_end        # 'December 31, 2023' (if present)
```

### Classification Types

EdgarTools detects the type of correspondence from form and text content:

| Type | Description | Detection |
|------|-------------|-----------|
| `COMPANY_RESPONSE` | Response to SEC comments | "in response to your comment" patterns |
| `ACCELERATION_REQUEST` | Request to accelerate effective date | Rule 461 references |
| `SEC_COMMENT` | SEC comment letter with questions | Numbered comments or "please explain" |
| `REVIEW_COMPLETE` | SEC confirms no further comments | "completed our review" |
| `NO_REVIEW` | SEC will not review the filing | "will not review" |
| `COMPANY_LETTER` | Generic company-to-SEC letter | CORRESP fallback |
| `SEC_LETTER` | Generic SEC-to-company letter | UPLOAD fallback |

---

## Read the Full Text

The `.body` property contains the full text content of the letter:

```python
text = corresp.body
print(text[:500])  # First 500 characters
```

---

## Reconstruct Correspondence Threads

The real power is thread reconstruction. From any single correspondence filing, EdgarTools finds all related CORRESP and UPLOAD filings by matching file number and referenced form:

```python
thread = corresp.thread

thread.entries          # List[Correspondence] in chronological order
thread.is_resolved      # True if the last entry is a review-complete notice
thread.duration_days    # Days between first and last entry
thread.comment_count    # Number of SEC comment letters
thread.response_count   # Number of company responses
len(thread)             # Total entries in the thread
```

Each entry in the thread is itself a `Correspondence` object with all the same properties.

---

## Find Correspondence from Any Filing

You don't need to start from a CORRESP or UPLOAD filing. The `correspondence()` method works on **any** filing type. Call it on a 10-K, S-1, or any other filing to find the SEC review thread:

```python
from edgar import Company

company = Company("SNOW")
ten_k = company.get_filings(form="10-K").latest().obj()

# Find SEC review correspondence for this 10-K
thread = ten_k.filing.correspondence()

if thread:
    print(f"{len(thread)} entries over {thread.duration_days} days")
    print(f"Resolved: {thread.is_resolved}")
```

This works by extracting the file number from the filing and searching for all CORRESP/UPLOAD filings that reference it.

---

## Common Analysis Patterns

### Check if a registration statement had SEC comments

```python
company = Company("SNOW")
s1_filing = company.get_filings(form="S-1").latest()
thread = s1_filing.correspondence()

if thread and thread.comment_count > 0:
    print(f"SEC sent {thread.comment_count} comment letters")
    print(f"Company responded {thread.response_count} times")
    print(f"Review took {thread.duration_days} days")
```

### Browse all correspondence for a company

```python
company = Company("TSLA")
corresp_filings = company.get_filings(form="CORRESP")
upload_filings = company.get_filings(form="UPLOAD")

for filing in corresp_filings.head(5):
    c = filing.obj()
    print(f"{c.filing_date} | {c.correspondence_type.display_name} | Re: {c.referenced_form}")
```

### Identify SEC comment letters

```python
from edgar.correspondence import CorrespondenceType

company = Company("META")
uploads = company.get_filings(form="UPLOAD")

for filing in uploads.head(10):
    c = filing.obj()
    if c.correspondence_type == CorrespondenceType.SEC_COMMENT:
        print(f"{c.filing_date}: SEC comment letter re: {c.referenced_form}")
```

---

## Metadata Quick Reference

| Property | Returns | Example |
|----------|---------|---------|
| `form` | Form type | `"CORRESP"` or `"UPLOAD"` |
| `company` | Company name | `"Snowflake Inc."` |
| `cik` | CIK number | `1640147` |
| `filing_date` | Date filed | `"2024-03-15"` |
| `accession_no` | Accession number | `"0001193125-24-..."` |
| `correspondence_type` | Classification | `CorrespondenceType.COMPANY_RESPONSE` |
| `sender` | Who sent it | `"company"` or `"sec"` |
| `referenced_file_number` | SEC file number | `"333-293459"` |
| `referenced_form` | Form under review | `"S-1"` |
| `response_date` | Response date reference | `"March 15, 2024"` |
| `fiscal_year_end` | Fiscal year end | `"January 31, 2024"` |
| `body` | Full text content | `str` or `None` |
| `thread` | Reconstructed thread | `CorrespondenceThread` or `None` |

---

## Thread Quick Reference

| Property | Returns | What it does |
|----------|---------|--------------|
| `entries` | `List[Correspondence]` | All entries in chronological order |
| `is_resolved` | `bool` | True if last entry is review-complete |
| `duration_days` | `int` or `None` | Days between first and last entry |
| `comment_count` | `int` | Number of SEC comment letters |
| `response_count` | `int` | Number of company responses |
| `file_number` | `str` | The file number linking the thread |
| `referenced_form` | `str` or `None` | The form under review |
| `len(thread)` | `int` | Total number of entries |

---

## Things to Know

**Thread reconstruction requires network calls.** Building a thread fetches all CORRESP and UPLOAD filings for the company, then parses each one to match on file number. This can be slow for companies with many correspondence filings. The thread is lazily loaded -- it won't fetch until you access `.thread`.

**Not all correspondence has extractable metadata.** Some older filings or unusual formats may not have a clear "Re:" block. In these cases, `referenced_file_number` and `referenced_form` will be `None`, and the filing will be classified as a generic `COMPANY_LETTER` or `SEC_LETTER`.

**File numbers link the thread.** The correspondence thread is built by matching the SEC file number (e.g., `333-293459`). If a filing doesn't have a parseable file number, it can't be linked into a thread.

**UPLOAD filings may not have HTML.** SEC UPLOAD filings are often plain text. The `body` property returns the text content regardless of format.

---

## Related

- [Working with Filings](working-with-filing.md) -- general filing access patterns
- [Search & Filter](searching-filings.md) -- find specific filing types
- [Current Filings](current-filings.md) -- monitor new filings as they arrive
