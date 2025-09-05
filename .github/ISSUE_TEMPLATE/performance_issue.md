---
name: Performance Issue
about: Report performance problems (slow operations, memory issues)
title: '[PERFORMANCE] '
labels: 'performance, bug'
assignees: ''
---

## Performance Issue Details

**Issue Type:**
- [ ] Slow operation (longer than expected)
- [ ] Memory usage too high
- [ ] Memory leak (increasing memory over time)
- [ ] CPU usage too high
- [ ] Hangs/freezes during operation

## Environment
**EdgarTools Version:** (e.g., 4.9.0)
**Python Version:** (e.g., 3.10.5)  
**Operating System:** (e.g., macOS 14.0, Windows 11, Ubuntu 22.04)
**Available RAM:** (e.g., 16GB)
**CPU:** (e.g., Intel i7, Apple M1, AMD Ryzen 7)

## Performance Metrics
**Expected performance:**
- Time: (e.g., should complete in under 30 seconds)
- Memory: (e.g., should use less than 1GB RAM)

**Actual performance:**
- Time: (e.g., takes 5 minutes to complete)
- Memory: (e.g., uses 8GB RAM and keeps growing)

## Reproduction Details
**Company/Ticker:** (e.g., AAPL)
**Dataset Size:** (e.g., 5 years of 10-K filings, all S&P 500 companies)
**Time Period:** (e.g., 2019-2023)

**Code to reproduce:**
```python
# Paste the code that demonstrates the performance issue
import time
from edgar import Company

start_time = time.time()

company = Company("AAPL")
# ... code that shows performance problem

end_time = time.time()
print(f"Execution time: {end_time - start_time:.2f} seconds")
```

## System Resource Usage
**During the slow operation, please check:**
- CPU usage: (e.g., 100% on all cores)
- Memory usage: (e.g., 12GB out of 16GB)
- Disk I/O: (e.g., high read activity)
- Network usage: (e.g., downloading large files)

## Comparison/Baseline
**Does this operation work normally with:**
- [ ] Smaller datasets (e.g., single company vs multiple companies)
- [ ] Different time periods (e.g., 1 year vs 5 years)
- [ ] Different companies (e.g., smaller companies vs large companies)
- [ ] Different forms (e.g., 10-Q vs 10-K)

## Additional Context
- Is this a regression? (worked faster in previous version)
- Any patterns you've noticed (e.g., gets slower over time)
- Workarounds you've found
- Screenshots of system monitor/task manager if relevant

---
*Performance issues will be analyzed using profiling tools and benchmarked against baseline performance metrics.*