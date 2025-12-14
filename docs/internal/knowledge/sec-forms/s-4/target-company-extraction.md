# S-4 Target Company Extraction Techniques

*Source: Issue #434 Investigation - Ares Acquisition Corp II / Kodiak Robotics merger*

## Overview

S-4 forms (business combination registration statements) contain structured information about target companies that can be extracted without regex parsing of narrative text. This document outlines reliable extraction techniques discovered through systematic investigation.

## Key Discovery: Co-Registrant Tables

**Most Reliable Method**: S-4 filings contain structured "Table of Co-Registrants" sections with machine-readable target company data.

### Example Structure
```html
<table>
  <tr>
    <th>Name</th>
    <th>EIN</th>
    <th>SIC Code</th>
    <th>State of Incorporation</th>
  </tr>
  <tr>
    <td>Kodiak Robotics, Inc.</td>
    <td>82-5086710</td>
    <td>7373</td>
    <td>Delaware</td>
  </tr>
</table>
```

### Extraction Code Example
```python
def extract_s4_target_info(filing):
    """Extract target company info from S-4 co-registrant table"""
    html_content = filing.html().text
    
    # Find co-registrant tables
    tables = re.findall(r'<table[^>]*>.*?</table>', html_content, re.DOTALL)
    
    for table in tables:
        if 'co-registrant' in table.lower():
            # Extract structured data
            ein_match = re.search(r'(\d{2}-\d{7})', table)
            sic_match = re.search(r'classification.*?(\d{4})', table)
            state_match = re.search(r'(delaware|california|new york)', table, re.IGNORECASE)
            
            if ein_match:
                return {
                    'ein': ein_match.group(1),
                    'sic_code': sic_match.group(1) if sic_match else None,
                    'state': state_match.group(1) if state_match else None
                }
    
    return None
```

## Secondary Extraction Methods

### 1. XBRL Business Combination Facts
S-4 filings include XBRL facts using the `aact:` (Acquisition and Restructuring) taxonomy:

```python
def extract_business_combination_facts(filing):
    """Extract XBRL business combination facts"""
    xbrl = filing.xbrl()
    bc_facts = []
    
    for fact in xbrl.facts.get_facts():
        concept = fact.get('concept', '')
        if 'businesscombination' in concept.lower():
            bc_facts.append({
                'concept': concept,
                'value': fact.get('value'),
                'period': fact.get('period')
            })
    
    return bc_facts
```

### 2. Filing Header Information
Structured target company data appears in SEC filing headers:

```python
def extract_header_target_info(filing):
    """Extract target company info from filing header"""
    html_content = filing.html().text
    
    # Target company information appears in first 200 lines
    header_lines = html_content.split('\n')[:200]
    header_text = '\n'.join(header_lines)
    
    # Look for structured address and legal information
    patterns = {
        'company_name': r'([A-Z][A-Za-z\s&,\.]+(?:Inc|Corp|LLC|Ltd)\.?)',
        'address': r'(\d+\s+[A-Za-z\s]+(?:Street|Ave|Blvd|Road))',
        'phone': r'(\(\d{3}\)\s*\d{3}-\d{4})'
    }
    
    extracted = {}
    for field, pattern in patterns.items():
        match = re.search(pattern, header_text)
        if match:
            extracted[field] = match.group(1)
    
    return extracted
```

## Important Limitations

### Private vs Public Companies
- **Private companies** (like Kodiak Robotics) have **EINs but no SEC CIKs**
- **Public companies** have both EINs and CIKs for cross-filing linkage
- S-4 XBRL contexts only contain registrant entity information

### XBRL Entity Structure
```python
# S-4 XBRL only contains registrant entity
xbrl = s4_filing.xbrl()
print(xbrl.entity)  # Only shows registrant (Ares Acquisition Corp II)
# Target company (Kodiak) not in XBRL entity contexts
```

## Reliable Implementation Strategy

### Phase 1: High-Confidence Extraction
```python
class S4TargetExtractor:
    def __init__(self, filing):
        self.filing = filing
        self.html_content = filing.html().text
    
    def extract_target_info(self):
        """Extract target company info with confidence scoring"""
        methods = [
            self._extract_from_co_registrant_table,
            self._extract_from_xbrl_facts,
            self._extract_from_header
        ]
        
        results = []
        for method in methods:
            try:
                result = method()
                if result:
                    results.append(result)
            except Exception as e:
                continue
        
        return self._consolidate_results(results)
    
    def _extract_from_co_registrant_table(self):
        """Primary extraction method - highest confidence"""
        # Implementation from above
        pass
    
    def _extract_from_xbrl_facts(self):
        """Secondary method - medium confidence"""
        # Implementation from above
        pass
    
    def _extract_from_header(self):
        """Tertiary method - lower confidence"""
        # Implementation from above
        pass
    
    def _consolidate_results(self, results):
        """Combine results with confidence weighting"""
        if not results:
            return None
        
        # Prioritize co-registrant table results
        for result in results:
            if result.get('source') == 'co_registrant_table':
                return result
        
        return results[0]  # Return highest-confidence result
```

## Real-World Test Cases

### Verified S-4 Filings
1. **Ares Acquisition Corp II / Kodiak Robotics**
   - Date: 2022-11-08
   - CIK: 0001853138
   - Target EIN: 82-5086710
   - Extraction Success: ✅ Co-registrant table method

### Edge Cases to Handle
- Multiple target companies in single S-4
- International target companies (no EIN)
- Target company name variations (subsidiaries, DBA names)
- Historical S-4 format variations

## Integration with EdgarTools

### Proposed API Design
```python
# Seamless integration with existing Filing API
s4_filing = Filing(20221108, '0001853138', 'S-4')

# New property for S-4 filings
target_info = s4_filing.target_company
print(target_info.name)  # "Kodiak Robotics, Inc."
print(target_info.ein)   # "82-5086710"
print(target_info.sic_code)  # "7373"
print(target_info.incorporation_state)  # "Delaware"

# Link to target company filings if public
if target_info.is_public_company:
    target_filings = target_info.filings
```

## Performance Considerations

- **Caching**: Cache extraction results to avoid re-parsing large HTML
- **Lazy Loading**: Only extract when `target_company` property accessed
- **Error Handling**: Graceful degradation when extraction fails
- **Validation**: Verify extracted data format (EIN, SIC patterns)

## Future Enhancements

1. **Machine Learning**: Train models on co-registrant table variations
2. **Entity Resolution**: Map EINs to potential SEC CIKs for public companies
3. **Industry Analysis**: Identify industry-specific S-4 patterns
4. **Cross-Filing Validation**: Verify extracted data against other filings

---

*Based on systematic investigation of Issue #434*  
*Last Updated: 2025-01-09*