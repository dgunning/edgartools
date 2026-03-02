---
title: "Understanding 10-K, 10-Q, and 8-K Report Objects in Python"
description: "Learn how edgartools converts SEC annual reports (10-K), quarterly reports (10-Q), and current reports (8-K) into Python data objects."
category: "concepts"
difficulty: "intermediate"
time_required: "15 minutes"
prerequisites: ["installation", "sec-filings"]
related: ["xbrl-fundamentals", "statement-structure"]
keywords: ["data objects", "parsing", "structured data", "SEC filings", "XBRL", "object-oriented", "10-K", "10-Q", "8-K"]
---

# Understanding 10-K, 10-Q, and 8-K Report Objects in Python

## Introduction

One of the most powerful features of edgartools is its Data Objects system. This system transforms raw SEC filing data into structured, easy-to-use Python objects that expose filing-specific properties and methods. Instead of dealing with complex HTML, XML, or XBRL parsing yourself, Data Objects handle all the heavy lifting, allowing you to focus on analysis rather than data extraction.

This guide explains the conceptual framework behind Data Objects, how they work under the hood, and how to leverage them effectively in your SEC data analysis workflows.

## The Problem Data Objects Solve

SEC filings are notoriously complex documents:

- They contain a mix of structured and unstructured data
- They use different formats (HTML, XML, XBRL) depending on filing type and date
- Their structure evolves over time as SEC requirements change
- They often contain inconsistencies in formatting and organization
- They require domain knowledge to interpret correctly

Without Data Objects, working with SEC filings would require:

1. Downloading raw filing documents
2. Writing custom parsers for each filing type
3. Handling edge cases and inconsistencies
4. Extracting and organizing the data manually
5. Converting data into usable formats for analysis

Data Objects eliminate these challenges by providing a consistent, intuitive interface to SEC filing data, regardless of the underlying format or structure.

## The Data Objects Architecture

### Core Principles

The Data Objects system is built on several key principles:

1. **Type-Specific Interfaces**: Each filing type has its own specialized interface that exposes only the relevant properties and methods.
2. **Lazy Parsing**: Content is parsed on-demand to minimize memory usage and processing time.
3. **Consistent Access Patterns**: Similar data is accessed through consistent patterns across different filing types.
4. **Rich Metadata**: Each object includes metadata about the filing, such as dates, filer information, and document structure.
5. **Transformation Capabilities**: Data can be easily transformed into formats like pandas DataFrames for analysis.

### Object Hierarchy

Data Objects follow a hierarchical structure:

```plaintext
Filing (base class)
├── CompanyFiling
│   ├── TenK (10-K Annual Report)
│   ├── TenQ (10-Q Quarterly Report)
│   └── EightK (8-K Current Report)
├── OwnershipFiling
│   ├── Form3 (Initial Ownership)
│   ├── Form4 (Changes in Ownership)
│   └── Form5 (Annual Ownership Summary)
├── InvestmentFiling
│   └── ThirteenF (13F Holdings Report)
└── Other specialized filing types
```

Each object in this hierarchy inherits common functionality while adding specialized features for its filing type.

## How Data Objects Work

### The Creation Process

When you call the `.obj()` method on a Filing object, the following process occurs:

1. **Filing Type Detection**: The system identifies the filing type based on the form type and content.
2. **Parser Selection**: The appropriate parser is selected for that filing type.
3. **Object Instantiation**: A new Data Object of the correct type is created.
4. **Initial Parsing**: Basic metadata is parsed immediately.
5. **Lazy Loading Setup**: More complex content is set up for on-demand parsing.

### Parsing Strategies

Data Objects use different parsing strategies depending on the filing type:

- **HTML Parsing**: For narrative sections like business descriptions and risk factors
- **XML Parsing**: For structured data like ownership transactions and fund holdings
- **XBRL Processing**: For financial statements and other tagged financial data
- **Table Extraction**: For tabular data embedded in filings
- **Text Processing**: For extracting plain text from complex HTML structures

These strategies are applied automatically based on the content being accessed.

## Working with Data Objects

### Common Patterns

Across all Data Objects, you'll find these common patterns:

1. **Property Access**: Access filing sections or data through properties (e.g., `tenk.risk_factors`, `tenk.auditor`, `tenk.subsidiaries`, `tenk.reports`)
2. **Method Calls**: Perform operations on the data (e.g., `form4.get_net_shares_traded()`)
3. **Dictionary-Like Access**: Access specific items by key (e.g., `eightk["Item 2.01"]`)
4. **Iteration**: Iterate over collections within the filing (e.g., `for holding in thirteen_f.infotable`)
5. **Conversion**: Transform data into other formats (e.g., `balance_sheet.to_dataframe()`)

### Object Persistence

Data Objects are designed to be lightweight and don't persist the entire filing content in memory. Instead, they:

1. Store references to the original filing content
2. Parse specific sections only when accessed
3. Cache parsed results to avoid repeated parsing
4. Release memory when no longer needed

This approach allows you to work with very large filings efficiently.

## Advanced Usage Patterns

### Combining Multiple Data Objects

You can combine data from multiple Data Objects for more sophisticated analysis:

```python
# Compare financial data across quarters
company = Company("AAPL")
filings = company.get_filings(form=["10-K", "10-Q"]).head(5)
data_objects = [filing.obj() for filing in filings]

# Extract revenue from each filing
revenues = []
for obj in data_objects:
    if hasattr(obj, "income_statement"):
        period_end = obj.period_end_date
        revenue = obj.income_statement.get_value("Revenues")
        revenues.append((period_end, revenue))

# Sort by date and analyze trend
revenues.sort(key=lambda x: x[0])
```

### Custom Data Extraction

You can extend Data Objects with your own extraction logic:

```python
def extract_cybersecurity_risks(tenk):
    """Extract cybersecurity-related content from risk factors."""
    if not hasattr(tenk, "risk_factors"):
        return None
        
    risk_text = tenk.risk_factors
    cyber_keywords = ["cyber", "hack", "breach", "data security", "privacy"]
    
    # Find paragraphs containing cyber keywords
    paragraphs = risk_text.split("\n\n")
    cyber_paragraphs = [p for p in paragraphs if any(k in p.lower() for k in cyber_keywords)]
    
    return cyber_paragraphs

# Apply to a 10-K
tenk = company.latest("10-K").obj()
cyber_risks = extract_cybersecurity_risks(tenk)
```

### Batch Processing

For processing many filings efficiently:

```python

# Process all 8-Ks from the past year
company = Company("MSFT")
filings = company.get_filings(form="8-K", start_date="2024-01-01")

# Extract all press releases
all_press_releases = []
for filing in filings:
    try:
        eightk = filing.obj()
        if eightk.has_press_release:
            for pr in eightk.press_releases:
                all_press_releases.append({
                    "date": eightk.date_of_report,
                    "title": pr.title,
                    "content": pr.content
                })
    except Exception as e:
        print(f"Error processing filing {filing.accession_number}: {e}")

print(f"Found {len(all_press_releases)} press releases")
```

## Common Challenges and Solutions

### Challenge: Handling Missing Data

Not all filings contain all expected sections or data points:

```python
# Safe access pattern
tenk = filing.obj()
if hasattr(tenk, "risk_factors") and tenk.risk_factors:
    # Process risk factors
    pass
else:
    print("No risk factors section found")

# For financial data
try:
    revenue = income_stmt.get_value("Revenues")
except ValueError:
    revenue = income_stmt.get_value("RevenueFromContractWithCustomerExcludingAssessedTax")
except:
    revenue = None
```

### Challenge: Handling Format Changes

SEC filing formats evolve over time:

```python
# Version-aware code
tenk = filing.obj()
filing_year = tenk.period_end_date.year

if filing_year >= 2021:
    # Use newer XBRL taxonomy concepts
    revenue = income_stmt.get_value("RevenueFromContractWithCustomerExcludingAssessedTax")
else:
    # Use older concepts
    revenue = income_stmt.get_value("Revenues")
```

### Challenge: Processing Large Filings

Some filings (especially 10-Ks) can be very large:

```python
# Memory-efficient processing
tenk = filing.obj()

# Process one section at a time
sections = ["business", "risk_factors", "management_discussion"]
for section_name in sections:
    if hasattr(tenk, section_name):
        section = getattr(tenk, section_name)
        # Process section
        # ...
        # Explicitly delete to free memory
        del section
```

## Best Practices

### 1. Use the Right Object for the Task

Choose the most specific Data Object for your needs:

- Use `TenK`/`TenQ` for financial statement analysis
- Use `TenK` for auditor info (`tenk.auditor`), subsidiaries (`tenk.subsidiaries`), and XBRL report pages (`tenk.reports`)
- Use `EightK` for event monitoring
- Use `Form4` for insider trading analysis
- Use `ThirteenF` for fund holdings analysis

### 2. Leverage Built-in Methods

Data Objects include many helpful methods that save you from writing custom code:

```python
# Instead of parsing manually:
form4 = filing.obj()
net_shares = form4.get_net_shares_traded()  # Built-in method

# Instead of calculating manually:
thirteen_f = filing.obj()
top_10 = thirteen_f.get_top_holdings(10)  # Built-in method
```

### 3. Handle Errors Gracefully

SEC filings can have inconsistencies that cause parsing errors:

```python
try:
    data_obj = filing.obj()
    # Work with the object
except Exception as e:
    print(f"Error parsing filing {filing.accession_number}: {e}")
    # Fall back to simpler access methods
    text = filing.text
```

### 4. Use Local Storage

- Data Objects parse filing content on-demand
- Large filings (like 10-Ks) may take a few seconds to parse
- Consider using local storage for batch processing


## Conclusion

Data Objects are the heart of edgartools' power and usability. By abstracting away the complexities of SEC filing formats and structures, they allow you to focus on analysis rather than data extraction. Understanding how Data Objects work and how to use them effectively will help you build more powerful, efficient, and maintainable SEC data analysis workflows.

Whether you're analyzing financial statements, tracking insider trading, or researching investment funds, Data Objects provide a consistent, intuitive interface that makes working with SEC data a breeze.

## Additional Resources

- [Working with Financial Statements](../guides/extract-statements.md)
- [Current Events (8-K)](../eightk-filings.md)
- [Analyzing Insider Trading](../guides/track-form4.md)
- [Institutional Holdings (13F)](../guides/thirteenf-data-object-guide.md)
