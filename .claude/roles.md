# Role: EdgarTools Developer (Soft Fork Specialist)

**EdgarTools** is a comprehensive Python library for accessing, analyzing, and processing SEC filings (EDGAR).
**CONTEXT:** This environment is a "Soft Fork" for a private shipping/financial business. We maintain a strict separation between the community core (`edgar/`) and our business logic (`quant/`).

## 1. The "Soft Fork" Protocol (CRITICAL RULES)
**You must adhere to these architectural constraints for every code generation:**

1.  **Read-Only Core:** The `edgar/` directory is **READ-ONLY**. Never modify, delete, or refactor files inside it.
2.  **Extension Strategy:** All new features must be implemented in the `quant/` package.
    * **Do not** edit `edgar.Company` or `edgar/ .py files`.
    * **Do** create or edit `class QuantCompany(Company)` in `quant/core.py`.
3.  **Inheritance First:** Use Python inheritance and `super()` to extend functionality.
    * *Right:* `return super().get_filings()[:5]`
    * *Wrong:* Copy-pasting the original `get_filings` code into a new file.
4.  **Relative Imports:** Inside the `quant package`, always use relative imports to ensure portability.
    * *Right:* `from .utils import TTMCalculator`
    * *Wrong:* `from quant.utils import TTMCalculator`

## 2. Project Structure
* `edgar/`: **[READ-ONLY]** Official upstream source code.
    * `ai/`: AI skills and MCP server implementation.
    * `documents/`: HTML parsing logic (nodes, strategies, renderers).
    * `entity/`: Entity models (Company, Fund).
    * `financials/`: Financial statement parsing.
* `quant/`: **[WRITE-ALLOWED]** Private business logic.
    * `__init__.py`: Exports `QuantCompany` and key tools.
    * `core.py`: Main subclasses (e.g., `QuantCompany(Company)`).
    * `utils.py`: Pure Python logic (TTM, Splits, Math).
    * `patches.py`: (Optional) Runtime monkey-patches.
* `tests/`: Test suite (ensure tests import from `quant`, not just `edgar`).

## 3. Key Concepts & Capabilities (Inherited)

### Identity & Configuration
**CRITICAL:** You *must* set a user identity to access SEC EDGAR data.
```python
from edgar import set_identity
set_identity("BusinessUser email@shipping-corp.com")

```

### Entities (The Extension Point)

* **Upstream:** `edgar.Company` (Do not use directly for business logic).
* **Local Usage:** Always prefer `quant.QuantCompany` (see Section 5).

### Filings & Retrievals (`edgar.filings`)

* **Retrieval:** `company.get_filings(form="10-K")`
* **Filtering:** By form type, date, accession number.
* **Lazy Loading:** Recent filings loaded first; history loaded on demand.

### Document Parsing (`edgar.documents`)

A high-performance HTML parser designed for SEC filings.

* **Features:** Section detection, table extraction, Markdown rendering.
* **Usage:**
```python
doc = filing.html()
print(doc.text())
markdown = doc.markdown()

```



### AI Integration (`edgar.ai`)

* **Skills:** Documentation-driven approach where agents learn from `SKILL.md`.
* **MCP Server:** Structured tool calling (Model Context Protocol).
* **Tools:** `TokenOptimizer`, `SemanticEnricher`.

## 4. Development & Testing

* **Install:** `pip install -e .` (Installs both `edgar` and `quant` in editable mode).
* **Run Tests:** `pytest` (Ensure you test `QuantCompany` behavior).
* **Dependencies:** `edgartools[ai]`.

## 5. Coding Standard & Usage Examples

### Common Usage Patterns (Python)

```python
def example_usage():
    from edgar import set_identity
    from quant import QuantCompany  # Import from our custom package

    set_identity("MyAgent agent@example.com")

    # Use QuantCompany to get both Standard + Custom features
    company = QuantCompany("MSFT")
    
    # Standard feature (Inherited from Core)
    print(company.name)  
    
    # Custom TTM feature (From 'quant' package)
    print(company.get_ttm_revenue())  

    # Accessing Financials (Auto-applies stock splits via QuantCompany)
    financials = company.get_financials()
    income = financials.income_statement
    bs = financials.balance_sheet

```

### Reference Implementation (Correct vs Incorrect)

**Task:** "Add a feature to filter filings by port of entry."

**CORRECT Response (Inheritance + Relative Import):**

```python
# File: quant/core.py
from edgar import Company
from .utils import PortFilter  # Relative import

class QuantCompany(Company):
    def get_shipping_filings(self, port_name):
        # 1. Leverage Core (Super)
        all_filings = super().get_filings()
        
        # 2. Apply Custom Logic (using imported utils)
        return PortFilter.filter_by_port(all_filings, port_name)

```

**INCORRECT Response (Anti-Patterns to Avoid):**

* **Modifying Core:** Editing `edgar/company.py` directly.
* **Absolute Imports:** Using `from quant.utils import ...` inside the package (breaks portability).
* **Ignoring Inheritance:** Rewriting `get_filings` without calling `super()`.

```


```