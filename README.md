<p align="center">
<a href="https://github.com/dgunning/edgartools">
    <img src="docs/images/edgartools-logo.png" alt="edgar-tools-logo" height="80">
</a>
</p>

<h3 align="center">Unlock SEC data in seconds, not hours</h3>

<p align="center">
  <a href="https://pypi.org/project/edgartools"><img src="https://img.shields.io/pypi/v/edgartools.svg" alt="PyPI - Version"></a>
  <a href="https://github.com/dgunning/edgartools/actions"><img src="https://img.shields.io/github/actions/workflow/status/dgunning/edgartools/python-hatch-workflow.yml" alt="GitHub Workflow Status"></a>
  <a href="https://www.codefactor.io/repository/github/dgunning/edgartools"><img src="https://www.codefactor.io/repository/github/dgunning/edgartools/badge" alt="CodeFactor"></a>
  <a href="https://github.com/pypa/hatch"><img src="https://img.shields.io/badge/%F0%9F%A5%9A-Hatch-4051b5.svg" alt="Hatch project"></a>
  <a href="https://github.com/dgunning/edgartools/blob/main/LICENSE"><img src="https://img.shields.io/github/license/dgunning/edgartools" alt="GitHub"></a>
  <a href="https://pypi.org/project/edgartools"><img src="https://img.shields.io/pypi/dm/edgartools" alt="PyPI - Downloads"></a>
</p>

<p align="center">
  <b>Extract financial data from SEC filings in 3 lines of code instead of 100+</b>
</p>

<!-- MEDIA PLACEHOLDER: Hero Video Demo (30-second overview of key capabilities) -->
![Edgartools Demo](docs/images/edgartools-demo.gif)

## Why Financial Professionals Choose EdgarTools


| Without EdgarTools | With EdgarTools |
|---|---|
| ❌ Hours spent navigating SEC.gov | ✅ Instant access to any filing since 1994 |
| ❌ Complex web scraping code | ✅ Clean Python API with intuitive methods |
| ❌ Manual extraction of financial data | ✅ Automatic parsing into pandas DataFrames |
| ❌ Custom code for each filing type | ✅ Specialized data objects for each form type |
| ❌ Messy HTML parsing for text extraction | ✅ One-line conversion to clean, readable text |
| ❌ Extra processing for AI/LLM compatibility | ✅ LLM-ready text extraction for AI pipelines |
| ❌ Rate limiting headaches | ✅ Automatic throttling to avoid blocks |

## 🔍 Key Features

- **Comprehensive Coverage**: Access any SEC filing since 1994
- **Intuitive API**: Simple, consistent interface for all SEC data
- **Smart Data Objects**: Automatic parsing of filings into structured objects
- **Clean Text Extraction**: One-line conversion from HTML to clean, readable text
- **AI/LLM Ready**: Text formatting and chunking optimized for AI pipelines
- **Financial Statements**: Extract balance sheets, income statements, and cash flows
- **Performance Optimized**: Uses PyArrow for efficient data handling
- **Beautiful Output**: Rich terminal displays and visualization helpers
- **Insider Transactions**: Track Form 3, 4, and 5 filings
- **Investment Funds**: Analyze fund structures, classes, and holdings
- **XBRL Support**: Extract and analyze XBRL-tagged data
- **Automatic Throttling**: Respectful of SEC.gov rate limits

## 📦 Installation

```bash
pip install edgartools
```

## 🚀 Quick Start (2-minute tutorial)

```python
# 1. Import the library
from edgar import *

# 2. Tell the SEC who you are (required by SEC regulations)
set_identity("your.name@example.com")  # Replace with your email

# 3. Find a company
company = Company("MSFT")  # Microsoft

# 4. Get company filings
filings = company.get_filings() 

# 5. Filter by form 
insider_filings = filings.filter(form="4")  # Insider transactions

# 6. Get the latest filing
insider_filing = insider_filings[0]

# 7. Convert to a data object
ownership = insider_filing.obj()
```

![Apple Insider Transaction](docs/images/aapl-insider.png)


## 🛠️ Advanced Usage

### Bulk Data Downloads

For faster processing or offline use, download bulk data:

```python
from edgar import download_edgar_data, use_local_storage

# Download all company data (one-time operation)
download_edgar_data()

# Use local data for all subsequent operations
use_local_storage()
```

## 🧭 Solve Real Problems

### Company Financial Analysis

**Problem:** Need to analyze a company's financial health across multiple periods.

![Microsoft Revenue Trend](docs/images/MSFT_financial_complex.png)

[See full code](docs/examples.md#company_financial_analysis)


</details>


## 📚 Documentation

- [Full API Documentation](https://edgartools.readthedocs.io/)
- [User Guides](https://edgartools.readthedocs.io/en/latest/guides/)
- [Examples Gallery](https://edgartools.readthedocs.io/en/latest/examples/)
- [Blog & Tutorials](https://www.edgartools.io)

## 👥 Community & Support

- [GitHub Issues](https://github.com/dgunning/edgartools/issues) - Bug reports and feature requests
- [Discussions](https://github.com/dgunning/edgartools/discussions) - Questions and community discussions

## 🔮 Roadmap

- **Coming Soon**: Enhanced visualization tools for financial data
- **In Development**: Machine learning integrations for financial sentiment analysis
- **Planned**: Interactive dashboard for filing exploration

## 🤝 Contributing

We welcome contributions from the community! Here's how you can help:

- **Code**: Fix bugs, add features, improve documentation
- **Examples**: Share interesting use cases and examples
- **Feedback**: Report issues or suggest improvements
- **Spread the Word**: Star the repo, share with colleagues

See our [Contributing Guide](CONTRIBUTING.md) for details.

## ❤️ Sponsors & Support

If you find EdgarTools valuable, please consider supporting its development:

<a href="https://buy.polar.sh/polar_cl_4URWus0XT8CtHrbOEP4FfDTAbVFkp0RiZqgwd1tNIdg" data-polar-checkout data-polar-checkout-theme="dark">**Donate to EdgarTools**</a>

## 📜 License

EdgarTools is distributed under the [MIT License](LICENSE).

## 📊 Star History

[![Star History Chart](https://api.star-history.com/svg?repos=dgunning/edgartools&type=Timeline)](https://star-history.com/#dgunning/edgartools&Timeline)