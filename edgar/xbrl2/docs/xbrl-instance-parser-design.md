![img_1.png](img_1.png)# XBRL Instance Document Parser Design (Python)

## 1. Overview

The XBRL Instance Document Parser is a critical component of the XBRL processing system that extracts structured financial data from XBRL instance files. This document provides a detailed design for implementing a robust parser capable of handling SEC filing XBRL instance documents using Python.

```
┌─────────────────┐     ┌─────────────────────────┐     ┌─────────────────┐
│                 │     │                         │     │                 │
│  XBRL Instance  │────▶│  Instance Document      │────▶│  Parsed Data    │
│  Document       │     │  Parser                 │     │  Model          │
│                 │     │                         │     │                 │
└─────────────────┘     └─────────────────────────┘     └─────────────────┘
```

## 2. Input and Output

### 2.1 Input
- XBRL instance document (XML file, typically with .xml extension)
- Optional: Reference to associated taxonomy files for validation and context

### 2.2 Output
- Structured data collections containing:
  - Entity information
  - Reporting period information
  - Contexts
  - Facts
  - Units
  - Footnotes

## 3. Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Instance Document Parser                   │
│                                                             │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐    │
│  │ XML           │  │ Namespace     │  │ Schematron    │    │
│  │ Parser        │  │ Handler       │  │ Validator     │    │
│  └───────────────┘  └───────────────┘  └───────────────┘    │
│                                                             │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐    │
│  │ Context       │  │ Fact          │  │ Unit          │    │
│  │ Extractor     │  │ Extractor     │  │ Extractor     │    │
│  └───────────────┘  └───────────────┘  └───────────────┘    │
│                                                             │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐    │
│  │ Footnote      │  │ Dimension     │  │ Error         │    │
│  │ Extractor     │  │ Handler       │  │ Handler       │    │
│  └───────────────┘  └───────────────┘  └───────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 4. Data Structures

### 4.1 Entity Information
```python
class EntityInfo:
    def __init__(self):
        self.identifier = ""        # Usually the SEC CIK number
        self.identifier_scheme = "" # Usually "http://www.sec.gov/CIK"
        self.name = ""              # Optional, may be extracted from document
        self.fiscal_year = None     # Optional
        self.fiscal_period = ""     # Optional (Q1, Q2, Q3, FY)
        self.reporting_period_end_date = None  # datetime.date object
```

### 4.2 Context
```python
class Context:
    class Entity:
        def __init__(self):
            self.identifier = ""
            self.identifier_scheme = ""
            self.segment = []  # List of dimensional qualifiers
    
    class Period:
        def __init__(self):
            self.type = ""  # "instant", "duration", or "forever"
            self.start_date = None  # datetime.date or None
            self.end_date = None    # datetime.date or None
            self.instant = None     # datetime.date or None
    
    def __init__(self):
        self.id = ""           # The context ID as defined in the instance
        self.entity = self.Entity()
        self.period = self.Period()
        self.scenario = []     # List of dimensional qualifiers
        self.dimensions = {}   # Dictionary of dimension name -> member name
```

### 4.3 Unit
```python
class Unit:
    def __init__(self):
        self.id = ""           # Unit ID as defined in the instance
        self.is_simple = True  # Whether this is a simple measure or a divide
        self.measure = ""      # For simple units
        self.numerator = []    # List of measures in numerator for divide units
        self.denominator = []  # List of measures in denominator for divide units
```

### 4.4 Fact
```python
class Fact:
    def __init__(self):
        self.concept = ""           # Element name or ID from taxonomy
        self.context_ref = ""       # Reference to context ID
        self.value = ""             # The fact value as a string
        self.decimals = None        # Precision indicator (int, "INF", or None)
        self.unit_ref = None        # Reference to unit ID (None for non-numeric)
        self.id = None              # Optional fact ID
        self.footnotes = []         # Array of associated footnote IDs
        
        # Derived properties after parsing
        self.numeric_value = None   # Converted value for numeric facts (float)
        self.concept_ns = ""        # Namespace of the concept
        self.concept_local_name = "" # Local name of the concept
        self.is_nil = False         # Whether this is a nil value
```

### 4.5 Footnote
```python
class Footnote:
    def __init__(self):
        self.id = ""
        self.role = ""       # The footnote role URI
        self.type = ""       # The footnote type
        self.value = ""      # The footnote content
        self.language = ""   # The language code
        self.fact_refs = []  # List of fact IDs this footnote is linked to
```

## 5. Detailed Process Flow

### 5.1 Initialization and XML Parsing
1. Initialize parser with instance document
2. Set up XML parser with appropriate namespaces
3. Load instance document into DOM or streaming parser
4. Validate basic XML structure
5. Extract schema reference information

### 5.2 Entity Information Extraction
1. Locate `<xbrli:entity>` elements
2. Extract entity identifier and scheme
3. Look for optional entity name in document metadata
4. Determine fiscal year and period from context information

### 5.3 Context Extraction
1. Locate all `<xbrli:context>` elements
2. For each context:
   - Extract context ID
   - Extract entity information
   - Determine period type and extract relevant dates
   - Process segment information if present
   - Process scenario information if present
   - Validate context structure
   - Store in context registry with ID as key

### 5.4 Unit Extraction
1. Locate all `<xbrli:unit>` elements
2. For each unit:
   - Extract unit ID
   - Determine if simple or complex (divide) unit
   - For simple units, extract measure
   - For complex units, extract numerator and denominator measures
   - Validate unit structure
   - Store in unit registry with ID as key

### 5.5 Fact Extraction
1. Identify all fact elements (non-context, non-unit, non-footnote elements)
2. For each fact:
   - Extract element name and namespace
   - Extract context reference
   - Extract value
   - For numeric facts:
     - Extract unit reference
     - Extract decimals or precision attribute
     - Convert string value to numeric type
   - Handle nil facts (xsi:nil="true")
   - Store fact in fact collection
   - Index fact by element name and context for efficient lookup

### 5.6 Footnote Extraction
1. Locate footnote link elements (`<link:footnoteLink>`)
2. For each footnote link:
   - Extract footnote arcs (`<link:footnoteArc>`)
   - Extract footnotes (`<link:footnote>`)
   - Map footnotes to facts using the arcs
   - Store footnotes and their relationships to facts

### 5.7 Dimension Handling
1. Process segment and scenario dimension information
2. Extract explicit dimension members
3. Extract typed dimension values
4. Normalize dimension references
5. Create dimensional context index for efficient fact lookup

## 6. Algorithms

### 6.1 Context Period Normalization
```python
def normalize_context_period(context_element):
    """Extract and normalize the period information from a context element."""
    period_element = context_element.find('.//{http://www.xbrl.org/2003/instance}period')
    
    if period_element.find('.//{http://www.xbrl.org/2003/instance}forever') is not None:
        return {
            'type': 'forever',
            'start_date': None,
            'end_date': None,
            'instant': None
        }
    
    instant_element = period_element.find('.//{http://www.xbrl.org/2003/instance}instant')
    if instant_element is not None:
        instant_text = instant_element.text
        return {
            'type': 'instant',
            'start_date': None,
            'end_date': None,
            'instant': parse_xbrl_date(instant_text)
        }
    
    start_date_element = period_element.find('.//{http://www.xbrl.org/2003/instance}startDate')
    end_date_element = period_element.find('.//{http://www.xbrl.org/2003/instance}endDate')
    
    start_date_text = start_date_element.text
    end_date_text = end_date_element.text
    
    return {
        'type': 'duration',
        'start_date': parse_xbrl_date(start_date_text),
        'end_date': parse_xbrl_date(end_date_text),
        'instant': None
    }
```

### 6.2 Numeric Value Processing
```python
def process_numeric_value(fact):
    """Process and convert numeric values."""
    if fact.value is None or fact.is_nil:
        fact.numeric_value = None
        return
    
    # Remove commas, currency symbols, percent signs, etc.
    import re
    clean_value = re.sub(r'[$,€£%]', '', fact.value).strip()
    
    # Convert to float
    try:
        fact.numeric_value = float(clean_value)
        
        # If decimals attribute is present, round to specified precision
        if fact.decimals is not None and fact.decimals != 'INF':
            decimals = int(fact.decimals)
            multiplier = 10 ** decimals
            fact.numeric_value = round(fact.numeric_value * multiplier) / multiplier
    except ValueError:
        fact.numeric_value = None
        logging.warning(f"Could not convert {fact.value} to numeric value")
```

### 6.3 Dimensional Context Processing
```python
def process_dimensional_context(context):
    """Process dimensional information from a context."""
    dimensions = {}
    
    # Process segment dimensions
    if context.entity.segment:
        for item in context.entity.segment:
            if hasattr(item, 'dimension_name'):
                dimensions[item.dimension_name] = item.member_name
    
    # Process scenario dimensions
    if context.scenario:
        for item in context.scenario:
            if hasattr(item, 'dimension_name'):
                dimensions[item.dimension_name] = item.member_name
    
    return dimensions
```

## 7. Performance Considerations

### 7.1 Memory Optimization
- Use streaming XML parser (like lxml.etree.iterparse) for very large instance documents
- Consider lazy loading of fact values for large documents
- Implement indexing for efficient fact lookup by concept and context

### 7.2 Parsing Efficiency
- Pre-compile namespace and element name lookups
- Cache context and unit references
- Batch process facts to improve overall throughput

### 7.3 Scalability
- Implement chunking for processing very large instance documents
- Consider multiprocessing for independent sections
- Use memory-efficient data structures for large fact collections

## 8. Error Handling

### 8.1 Error Types
- XML parsing errors
- XBRL specification violations
- Missing required attributes
- Invalid context references
- Invalid unit references
- Inconsistent numeric values

### 8.2 Error Handling Strategy
- Implement hierarchical error classification
- Distinguish between fatal and non-fatal errors
- Provide clear error messages with line numbers and context
- Implement recovery strategies for non-fatal errors
- Log warnings for potential issues

### 8.3 Validation
- Validate against XBRL 2.1 specification
- Check for consistency between facts and referenced contexts/units
- Verify that required elements are present
- Check decimal precision against reported values

## 9. Extension Points

### 9.1 Custom Fact Processors
- Allow registration of custom processors for specific elements
- Support specialized handling for industry-specific facts
- Enable post-processing of extracted facts

### 9.2 Pluggable Validators
- Support additional validation rules
- Enable integration with external validation services
- Allow custom business rules validation

### 9.3 Output Formatters
- Implement adapters for different output formats
- Support serialization to JSON, CSV, pandas DataFrame, etc.
- Enable custom output transformation

## 10. Implementation Example

### 10.1 Basic Parser Implementation
```python
import xml.etree.ElementTree as ET
from datetime import datetime
import logging
import re

class XBRLInstanceParser:
    def __init__(self, options=None):
        self.options = options or {}
        self.contexts = {}
        self.units = {}
        self.facts = []
        self.footnotes = {}
        self.entity_info = None
        
        # Define namespaces
        self.ns = {
            'xbrli': 'http://www.xbrl.org/2003/instance',
            'link': 'http://www.xbrl.org/2003/linkbase',
            'xlink': 'http://www.w3.org/1999/xlink'
        }
    
    def parse(self, instance_document_path):
        """Parse an XBRL instance document from a file path."""
        try:
            # Parse XML
            tree = ET.parse(instance_document_path)
            root = tree.getroot()
            
            # Extract namespaces
            self._extract_namespaces(root)
            
            # Extract entity information
            self.entity_info = self._extract_entity_info(root)
            
            # Extract contexts
            self.contexts = self._extract_contexts(root)
            
            # Extract units
            self.units = self._extract_units(root)
            
            # Extract facts
            self.facts = self._extract_facts(root)
            
            # Extract footnotes
            self.footnotes = self._extract_footnotes(root)
            
            # Process dimensions
            self._process_dimensions()
            
            # Index facts for efficient lookup
            self._index_facts()
            
            return {
                'entity_info': self.entity_info,
                'contexts': self.contexts,
                'units': self.units,
                'facts': self.facts,
                'footnotes': self.footnotes
            }
            
        except Exception as e:
            logging.error(f"Error parsing XBRL instance: {str(e)}")
            raise
    
    def _extract_namespaces(self, root):
        """Extract and register all namespaces from the document."""
        # Add all namespaces from root to our namespace dictionary
        for prefix, uri in root.nsmap.items() if hasattr(root, 'nsmap') else []:
            if prefix is not None:  # lxml uses None for the default namespace
                self.ns[prefix] = uri
    
    def _extract_entity_info(self, root):
        """Extract entity information from the document."""
        entity_info = EntityInfo()
        
        # For simplicity, extract from the first context
        context_element = root.find(f'.//{{{self.ns["xbrli"]}}}context')
        if context_element is not None:
            entity_element = context_element.find(f'.//{{{self.ns["xbrli"]}}}entity')
            if entity_element is not None:
                identifier_element = entity_element.find(f'.//{{{self.ns["xbrli"]}}}identifier')
                if identifier_element is not None:
                    entity_info.identifier = identifier_element.text.strip()
                    entity_info.identifier_scheme = identifier_element.get('scheme')
        
        # Find the end date of the reporting period
        # For simplicity, look for the context with the latest instant date
        latest_date = None
        for context_element in root.findall(f'.//{{{self.ns["xbrli"]}}}context'):
            period_element = context_element.find(f'.//{{{self.ns["xbrli"]}}}period')
            if period_element is not None:
                instant_element = period_element.find(f'.//{{{self.ns["xbrli"]}}}instant')
                if instant_element is not None:
                    date_str = instant_element.text.strip()
                    try:
                        date = datetime.strptime(date_str, '%Y-%m-%d').date()
                        if latest_date is None or date > latest_date:
                            latest_date = date
                    except ValueError:
                        continue
        
        entity_info.reporting_period_end_date = latest_date
        
        # Try to infer fiscal year and period from the contexts
        if latest_date is not None:
            entity_info.fiscal_year = latest_date.year
            
            # Very simplified logic - could be improved
            if latest_date.month == 3:
                entity_info.fiscal_period = "Q1"
            elif latest_date.month == 6:
                entity_info.fiscal_period = "Q2"
            elif latest_date.month == 9:
                entity_info.fiscal_period = "Q3"
            elif latest_date.month == 12:
                entity_info.fiscal_period = "FY"
        
        return entity_info
    
    # Implementation of all the extraction methods would follow...
```

### 10.2 Context Extraction Example
```python
def _extract_contexts(self, root):
    """Extract all contexts from the XBRL instance."""
    contexts = {}
    context_elements = root.findall(f'.//{{{self.ns["xbrli"]}}}context')
    
    for context_element in context_elements:
        context_id = context_element.get('id')
        context = Context()
        context.id = context_id
        
        # Extract entity information
        entity_element = context_element.find(f'.//{{{self.ns["xbrli"]}}}entity')
        if entity_element is not None:
            identifier_element = entity_element.find(f'.//{{{self.ns["xbrli"]}}}identifier')
            if identifier_element is not None:
                context.entity.identifier = identifier_element.text.strip()
                context.entity.identifier_scheme = identifier_element.get('scheme')
            
            # Extract segment information
            segment_element = entity_element.find(f'.//{{{self.ns["xbrli"]}}}segment')
            if segment_element is not None:
                context.entity.segment = self._extract_dimensional_info(segment_element)
        
        # Extract period information
        period_info = self._normalize_context_period(context_element)
        context.period.type = period_info['type']
        context.period.start_date = period_info['start_date']
        context.period.end_date = period_info['end_date']
        context.period.instant = period_info['instant']
        
        # Extract scenario information
        scenario_element = context_element.find(f'.//{{{self.ns["xbrli"]}}}scenario')
        if scenario_element is not None:
            context.scenario = self._extract_dimensional_info(scenario_element)
        
        contexts[context_id] = context
    
    return contexts
```

### 10.3 Fact Extraction Example
```python
def _extract_facts(self, root):
    """Extract all facts from the XBRL instance."""
    facts = []
    
    # Get all child elements that are not contexts, units, footnotes, etc.
    exclude_names = ['context', 'unit', 'footnote', 'schemaRef', 'roleRef', 'arcroleRef']
    
    for child in root:
        # Skip if it's in the exclude list
        if any(exclude_name in child.tag for exclude_name in exclude_names):
            continue
        
        # Skip if it's a tuple (not supported in this example)
        if self._is_tuple(child):
            continue
        
        fact = self._process_fact_element(child)
        if fact:
            facts.append(fact)
    
    return facts

def _process_fact_element(self, element):
    """Process a fact element and return a Fact object."""
    # Extract namespace and local name
    match = re.match(r'\{(.*)\}(.*)', element.tag)
    if not match:
        return None
    
    namespace_uri, local_name = match.groups()
    
    # Skip non-fact elements
    exclude_names = ['context', 'unit', 'footnote', 'schemaRef', 'roleRef', 'arcroleRef']
    if local_name in exclude_names:
        return None
    
    # Get context reference
    context_ref = element.get('contextRef')
    if not context_ref:
        logging.warning(f"Missing contextRef for element {local_name}")
        return None
    
    fact = Fact()
    fact.concept = element.tag
    fact.concept_ns = namespace_uri
    fact.concept_local_name = local_name
    fact.context_ref = context_ref
    fact.value = element.text.strip() if element.text else ""
    fact.decimals = element.get('decimals')
    fact.unit_ref = element.get('unitRef')
    fact.id = element.get('id')
    fact.is_nil = element.get('{http://www.w3.org/2001/XMLSchema-instance}nil') == 'true'
    
    # Process numeric value if applicable
    if fact.unit_ref and not fact.is_nil:
        self._process_numeric_value(fact)
    
    return fact
```

## 11. Testing Strategy

### 11.1 Unit Tests
- Test each parser component in isolation
- Validate extraction of specific XBRL elements
- Test handling of different data types
- Verify error detection and handling
- Use pytest for test organization and execution

### 11.2 Integration Tests
- Test end-to-end parsing of sample instance documents
- Verify correct extraction of complete fact sets
- Test interaction between different parser components

### 11.3 Performance Tests
- Measure parsing time for documents of varying sizes
- Test memory consumption patterns
- Verify scalability with large instance documents

### 11.4 Regression Tests
- Maintain a suite of real-world XBRL instances
- Compare parsing results against known-good baselines
- Verify backwards compatibility with older XBRL versions

## 12. Usage Example

### 12.1 Basic Usage
```python
# Create parser instance
parser = XBRLInstanceParser()

# Parse instance document
parsed_data = parser.parse('company-20231231.xml')

# Access parsed data
print(f"Entity: {parsed_data['entity_info'].identifier}")
print(f"Reporting period: {parsed_data['entity_info'].reporting_period_end_date}")
print(f"Total facts: {len(parsed_data['facts'])}")

# Get a specific fact by concept and context
assets_fact = next((f for f in parsed_data['facts'] 
                    if f.concept_local_name == 'Assets' and 
                    parsed_data['contexts'][f.context_ref].period.instant == datetime(2023, 12, 31).date()), None)
if assets_fact:
    print(f"Assets as of 2023-12-31: {assets_fact.numeric_value}")
```

### 12.2 Finding Balance Sheet Elements
```python
# Find all facts for the balance sheet as of a specific date
def get_balance_sheet_facts(parsed_data, date_str):
    """
    Get balance sheet facts for a specific date.
    
    Args:
        parsed_data: The parsed XBRL data
        date_str: Date string in format 'YYYY-MM-DD'
    
    Returns:
        List of facts for the balance sheet
    """
    from datetime import datetime
    
    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    # Find context for the specified date
    context_id = None
    for ctx_id, ctx in parsed_data['contexts'].items():
        if (ctx.period.type == 'instant' and 
                ctx.period.instant == target_date and 
                not ctx.scenario and 
                not ctx.entity.segment):
            context_id = ctx_id
            break
    
    if not context_id:
        raise ValueError(f"No context found for date {date_str}")
    
    # Get all facts with this context
    return [fact for fact in parsed_data['facts'] if fact.context_ref == context_id]

# Example usage
balance_sheet_facts = get_balance_sheet_facts(parsed_data, '2023-12-31')
assets_fact = next((f for f in balance_sheet_facts if f.concept_local_name == 'Assets'), None)
liabilities_fact = next((f for f in balance_sheet_facts if f.concept_local_name == 'Liabilities'), None)

if assets_fact:
    print(f"Assets: {assets_fact.numeric_value}")
if liabilities_fact:
    print(f"Liabilities: {liabilities_fact.numeric_value}")
```

### 12.3 Exporting to pandas DataFrame
```python
def facts_to_dataframe(parsed_data):
    """Convert XBRL facts to a pandas DataFrame."""
    import pandas as pd
    
    # Prepare data for DataFrame
    data = []
    for fact in parsed_data['facts']:
        context = parsed_data['contexts'].get(fact.context_ref)
        if not context:
            continue
            
        # Get period information
        if context.period.type == 'instant':
            period_end = context.period.instant
            period_start = None
        elif context.period.type == 'duration':
            period_end = context.period.end_date
            period_start = context.period.start_date
        else:
            period_end = None
            period_start = None
            
        # Get unit information
        unit = None
        if fact.unit_ref:
            unit_obj = parsed_data['units'].get(fact.unit_ref)
            if unit_obj:
                unit = unit_obj.measure if unit_obj.is_simple else "complex"
                
        # Create row
        row = {
            'concept': fact.concept_local_name,
            'namespace': fact.concept_ns,
            'period_start': period_start,
            'period_end': period_end,
            'value': fact.value,
            'numeric_value': fact.numeric_value,
            'unit': unit,
            'decimals': fact.decimals,
            'context_id': fact.context_ref,
            'dimensions': str(context.dimensions) if hasattr(context, 'dimensions') else ""
        }
        data.append(row)
        
    return pd.DataFrame(data)

# Example usage
import pandas as pd
df = facts_to_dataframe(parsed_data)
print(df.head())

# Filter to balance sheet items
balance_sheet_df = df[df['period_end'] == pd.Timestamp('2023-12-31')].copy()
```

## 13. Conclusion

The XBRL Instance Document Parser is designed to efficiently extract structured financial data from XBRL instance files, with a focus on SEC filings. The parser handles the complexities of XBRL syntax, including contexts, units, dimensions, and footnotes, to provide a clean, accessible data model for further processing and analysis.

By implementing this design in Python, you'll have a robust foundation for building XBRL-based financial analysis tools that can extract, validate, and process financial data from SEC filings. The Python implementation allows for easy integration with data science tools such as pandas for further analysis and visualization.
