# EdgarTools (edgar)

**EdgarTools** is a comprehensive Python library for accessing, analyzing, and processing SEC filings (EDGAR). It provides a high-level API for financial data, entity management, and document parsing, with specific optimizations for AI agents.

## Project Overview

*   **Package Name:** `edgartools` (imported as `edgar`)
*   **Version:** 5.6.0
*   **Primary Language:** Python
*   **Key Capabilities:**
    *   Retrieve filings for Companies, Funds, and Individuals.
    *   Parse complex SEC HTML documents into clean text and structured data.
    *   Extract financial statements (Income, Balance Sheet, Cash Flow).
    *   AI-native integration via "Skills" (Context-Oriented Programming) and an MCP Server.

## Key Concepts & Modules

### 1. Identity & Configuration (`edgar.core`, `edgar.config`)
**CRITICAL:** You *must* set a user identity to access SEC EDGAR data.
```python
from edgar import set_identity
set_identity("Name email@domain.com")
# OR set environment variable EDGAR_IDENTITY="Name email@domain.com"
```

### 2. Entities (`edgar.entity`)
The entry point for most data retrieval.
*   **Company:** Public companies (e.g., `Company("AAPL")`).
*   **Fund:** Mutual funds and ETFs (e.g., `Fund("0000036405")`).
*   **Entity:** Generic SEC filer wrapper.

### 3. Filings (`edgar._filings`, `edgar.current_filings`)
*   **Retrieval:** `company.get_filings(form="10-K")`
*   **Filtering:** By form type, date, accession number.
*   **Content:** Access raw HTML, XML, or parsed text/tables.
*   **Lazy Loading:** Recent filings loaded first; history loaded on demand.

### 4. Document Parsing (`edgar.documents`)
A high-performance HTML parser designed for SEC filings.
*   **Features:** Section detection, table extraction, Markdown rendering.
*   **Usage:**
    ```python
    doc = filing.html()
    print(doc.text())
    markdown = doc.markdown()
    ```

### 5. AI Integration (`edgar.ai`)
*   **Skills:** Documentation-driven approach where agents learn from `SKILL.md` to write Python code directly.
*   **MCP Server:** Structured tool calling (Model Context Protocol) for batch processing and automated pipelines.
*   **Tools:** `TokenOptimizer`, `SemanticEnricher`.

## Common Usage Patterns

### Fetching Company Data
```python
from edgar import Company, set_identity

set_identity("MyAgent agent@example.com")

company = Company("MSFT")
print(company.name)
print(company.financials.income_statement)
```

### Analyzing Filings
```python
filings = company.get_filings(form="10-K")
latest_10k = filings.latest()

# Get the document
doc = latest_10k.html()

# Search within the document
results = doc.search("revenue")
```

### Accessing Financials
```python
financials = company.get_financials()
income = financials.income_statement
bs = financials.balance_sheet
```

## Development & Testing

*   **Install:** `pip install "edgartools[ai]"`
*   **Dev Install:** `pip install -e ".[ai,ai-dev]"`
*   **Run Tests:** `pytest`
*   **Run MCP Server:** `python -m edgar.ai`

## Project Structure
*   `edgar/`: Main package source.
    *   `ai/`: AI skills and MCP server implementation.
    *   `documents/`: HTML parsing logic (nodes, strategies, renderers).
    *   `entity/`: Entity models (Company, Fund).
    *   `files/`: (Legacy) File handling.
    *   `financials/`: Financial statement parsing.
