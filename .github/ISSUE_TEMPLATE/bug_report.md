---
name: Bug Report
about: Create a report to help us improve EdgarTools
title: ''
labels: 'bug'
assignees: ''
---

## Issue Type
<!-- Select the primary category for this issue by putting an 'x' in the brackets -->
- [ ] Data Quality Issue (incorrect financial values, missing data)
- [ ] XBRL Parsing Issue (statement rendering, concept mapping)  
- [ ] Filing Access Issue (download failures, attachment problems)
- [ ] Performance Issue (slow operations, memory problems)
- [ ] Compatibility Issue (platform/dependency conflicts)
- [ ] Documentation Issue (unclear instructions, missing examples)

## Environment
**EdgarTools Version:** (e.g., 4.9.0)
**Python Version:** (e.g., 3.10.5)  
**Operating System:** (e.g., macOS 14.0, Windows 11, Ubuntu 22.04)

## Bug Description
**What you expected to happen:**
A clear description of what you expected.

**What actually happened:**
A clear description of what went wrong.

**Error message (if any):**
```
Paste any error messages here
```

## Reproduction
**Company/Ticker:** (e.g., AAPL)
**Time Period:** (e.g., 2020-2023, Q4 2023)
**Relevant Forms:** (e.g., 10-K, 10-Q, 8-K)

**Minimal code to reproduce:**
```python
# Paste the minimal code that reproduces the issue
from edgar import Company

company = Company("AAPL")
# ... rest of reproduction code
```

## Additional Context
Add any other context about the problem here. Screenshots, related issues, etc.

---
*This issue will be handled using EdgarTools' systematic issue resolution workflow. A reproduction test will be created to verify the fix.*