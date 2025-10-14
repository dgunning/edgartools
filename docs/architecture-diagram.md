# EdgarTools Architecture Diagram

## System Architecture

```mermaid
%%{init: {'theme':'base', 'themeVariables': { 'primaryColor':'#FFD700', 'primaryTextColor':'#3d5875', 'primaryBorderColor':'#3d5875', 'lineColor':'#3d5875', 'secondaryColor':'#f8f9fa', 'tertiaryColor':'#ffffff', 'background':'#ffffff', 'mainBkg':'#f8f9fa', 'secondBkg':'#FFD700', 'tertiaryBkg':'#3d5875'}}}%%

graph TB
    subgraph Users["🧑‍💻 Users & Applications"]
        A1[Python Developers]
        A2[AI Agents / LLMs]
        A3[Data Scientists]
        A4[Financial Analysts]
    end

    subgraph EdgarTools["EdgarTools Library"]
        direction TB
        B1[Core API Layer]
        B2[Filing Parser]
        B3[XBRL Processor]
        B4[Text Extractor]
        B5[MCP Server]

        B1 --> B2
        B1 --> B3
        B1 --> B4
        B1 --> B5
    end

    subgraph DataLayer["📊 Data Objects"]
        C1[Company]
        C2[Filings]
        C3[Financials]
        C4[Ownership]
        C5[Funds]
    end

    subgraph Output["💾 Output Formats"]
        D1[DataFrames]
        D2[Python Objects]
        D3[Markdown/Text]
        D4[JSON/Dict]
        D5[Rich Tables]
    end

    subgraph SEC["🏛️ SEC EDGAR Database"]
        E1[Filing Archive]
        E2[Company Data]
        E3[XBRL Datasets]
        E4[RSS Feeds]
    end

    A1 --> B1
    A2 --> B5
    A3 --> B1
    A4 --> B1

    B2 --> C1
    B2 --> C2
    B3 --> C3
    B2 --> C4
    B2 --> C5

    C1 --> D1
    C2 --> D2
    C3 --> D1
    C4 --> D2
    C5 --> D1
    C1 --> D3
    C2 --> D3
    C1 --> D4
    C1 --> D5

    B1 <--> SEC
    B2 <--> E1
    B3 <--> E3
    B1 <--> E2
    B1 <--> E4

    classDef userClass fill:#FFD700,stroke:#3d5875,stroke-width:2px,color:#3d5875
    classDef coreClass fill:#3d5875,stroke:#FFD700,stroke-width:2px,color:#FFD700
    classDef dataClass fill:#f8f9fa,stroke:#3d5875,stroke-width:2px,color:#3d5875
    classDef outputClass fill:#ffffff,stroke:#FFD700,stroke-width:2px,color:#3d5875
    classDef secClass fill:#3d5875,stroke:#3d5875,stroke-width:2px,color:#FFD700

    class A1,A2,A3,A4 userClass
    class B1,B2,B3,B4,B5 coreClass
    class C1,C2,C3,C4,C5 dataClass
    class D1,D2,D3,D4,D5 outputClass
    class E1,E2,E3,E4 secClass
```

## Component Details

### Core API Layer
- **Company**: Entry point for company-specific data
- **get_filings()**: Retrieve and filter filings
- **set_identity()**: SEC-required user identification
- **get_funds()**: Access fund holdings data

### Filing Parser
- **HTML Parsing**: lxml-based high-performance parsing
- **Form Recognition**: Automatic detection of form types
- **Data Extraction**: Structured data from forms (10-K, 10-Q, 8-K, Form 4, 13F, etc.)
- **Attachment Handling**: Access exhibits and attachments

### XBRL Processor
- **Financial Statements**: Balance sheets, income statements, cash flows
- **Standardization**: Cross-company comparable data
- **Tag Mapping**: XBRL tag to human-readable names
- **Validation**: Data quality checks

### Text Extractor
- **Clean Text**: HTML to clean text conversion
- **Section Extraction**: Item 1A (Risk Factors), Item 7 (MD&A), etc.
- **Markdown Conversion**: Formatted for LLMs
- **Chunking Support**: Large document handling

### MCP Server
- **Company Research**: AI-driven company analysis
- **Financial Analysis**: Automated financial metric extraction
- **Filing Search**: Natural language filing queries
- **Zero Configuration**: No API keys required

## Data Flow

1. **User Request** → Core API Layer
2. **API** → SEC EDGAR Database
3. **Raw Data** → Filing Parser
4. **Parsed Data** → Data Objects (Company, Filings, Financials)
5. **Data Objects** → Output Formats (DataFrame, Text, JSON)
6. **Output** → User Application

## Integration Points

### For Python Developers
```python
from edgar import Company
company = Company("AAPL")
financials = company.get_financials()
```

### For AI Agents (via MCP)
```python
# Automatic via Claude Desktop or other MCP clients
# No code needed - configure once, use forever
```

### For Data Scientists
```python
import pandas as pd
filings = Company("MSFT").get_filings()
df = filings.to_pandas()
```

---

**Diagram Usage in README:**

Add to README.md under an "Architecture" or "How It Works" section:

```markdown
## How It Works

EdgarTools provides a clean abstraction layer over the SEC EDGAR database:

[Include Mermaid diagram here]

The library handles all the complexity of SEC data access, parsing, and transformation, exposing a simple, intuitive API for financial data analysis.
```
