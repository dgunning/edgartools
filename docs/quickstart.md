# Quick Start Guide

Get up and running with EdgarTools in 5 minutes. This guide will take you from installation to your first meaningful analysis.

## Prerequisites

- Python 3.8 or higher
- Internet connection
- Basic familiarity with Python

## Step 1: Install EdgarTools

```bash
pip install edgartools
```

## Step 2: Set Your Identity

The SEC requires all API users to identify themselves. Set your identity once:

```python
from edgar import set_identity

# Use your name and email (required by SEC)
set_identity("John Doe john.doe@company.com")
```

**💡 Tip:** You can also set the `EDGAR_IDENTITY` environment variable to avoid doing this in every script.

## Step 3: Your first filings

Let's see available filings on the SEC Edgar

```python
from edgar import *

filings = get_filings()
```

![Filings](images/filings.png)


## Step 4: Filtering for insider trading filings

To focus on insider trading activity, filter for Form 4 filings:

```python
insider_filings = filings.filter(form="4")
```

![Form 4 Filings](images/form4filings.png)

## Step 5: Getting a Company

If you would like to focus on a specific company, you can use the `Company` class. For example, to analyze Apple Inc. (AAPL):

```python
c = Company("AAPL")  # Apple Inc.
```

![AAPL](images/AAPL.png)

## Step 6: Getting filings for a Company
You can retrieve all filings for a company using the `company.get_filings` method:

```python
# Get Apple's recent SEC filings
aapl_filings = c.get_filings()
```

![AAPL Filings](images/aapl-filings.png)

## Step 7: Insider Filings for Apple Inc.

To analyze insider trading activity for Apple Inc., filter the filings for Form 4:

```python
insider_filings = c.get_filings(form="4")
# Get the first insider filing
f = insider_filings[0]

# Convert to a Form4 object
form4 = f.obj()
```

![Apple Insider Filing](images/aapl-form4.png)

## What You Just Learned

In 5 minutes, you:

1. ✅ **Installed and configured** EdgarTools
2. ✅ **Retrieved and filtered** SEC filings
3. ✅ **Focused on insider trading** with Form 4
4. ✅ **Analyzed a specific company** (Apple Inc.)
5. ✅ **Extracted structured data** from filings
6. ✅ **Converted filings to data objects** for easy analysis
7. ✅ **Explored company filings** and insider activity

<!-- 
## Next Steps

Now that you've seen the basics, explore more advanced features:

### 🔍 **Deep Dive Analysis**
- **[Financial Statement Analysis](guides/extract-statements.md)** - Balance sheets, cash flow statements
- **[XBRL Querying](xbrl-querying.md)** - Custom financial metrics and ratios
- **[Time Series Analysis](guides/compare-periods.md)** - Multi-year trend analysis

### 📈 **Specialized Use Cases**
- **[Insider Trading Monitoring](guides/track-form4.md)** - Track insider transactions
- **[Fund Holdings Analysis](guides/analyze-13f.md)** - Research institutional investments
- **[Event Monitoring](guides/monitor-8k.md)** - Track corporate events via 8-K filings

### 🚀 **Advanced Features**
- **[Bulk Processing](guides/bulk-processing.md)** - Analyze hundreds of companies
- **[Custom Dashboards](cookbook/dashboards.md)** - Build interactive visualizations
- **[AI Integration](guides/ai-integration.md)** - LLM-powered analysis

### 📚 **Learning Resources**
- **[Complete Tutorials](tutorials/company-analysis.md)** - Step-by-step guides
- **[API Reference](api/company.md)** - Full documentation
- **[Cookbook](cookbook/revenue-growth.md)** - Ready-to-use recipes

### Rate Limiting
EdgarTools automatically handles SEC rate limits. If you hit limits:
- Add delays between requests
- Use local caching to reduce API calls
- Process data in smaller batches
-->

## Getting Help

- **📖 [Documentation](https://edgartools.readthedocs.io/en/latest/)**: Browse our comprehensive guides
- **💬 [GitHub Discussions](https://github.com/dgunning/edgartools/discussions)**: Ask questions and share insights  
- **🐛 [Issues](https://github.com/dgunning/edgartools/issues)**: Report bugs or request features

## Support EdgarTools

If you found this quickstart helpful, consider supporting EdgarTools development:

<a href="https://www.buymeacoffee.com/edgartools" target="_blank">
  <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 40px !important;width: 144px !important;" >
</a>

Your support helps us maintain and improve EdgarTools!

---

**🎉 Congratulations!** You're now ready to analyze SEC data with EdgarTools. 

**What's your next analysis goal?** Choose a path above and dive deeper into the world of financial data analysis.