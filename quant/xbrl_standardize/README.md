# XBRL Standardization System

**Production-ready XBRL concept mapping system with machine learning-based canonical concept discovery.**

## Overview

This system automatically learns and applies standardized XBRL concept mappings to extract financial statement data consistently across different companies, industries, and reporting formats.

### Key Features

- **Machine Learning-Based**: Learns canonical concepts from 500+ companies across multiple sectors
- **Sector-Specific**: Automatically adapts to industry-specific reporting patterns (banking, insurance, utilities)
- **High Coverage**: 100% coverage of required income statement fields
- **Robust Fallbacks**: Multiple fallback concepts per field for maximum extraction reliability
- **Auto-Detection**: Automatically detects company sector from SIC code or XBRL fact patterns

### Quality Metrics

- **Coverage Rate**: 100% (16/16 required fields mapped)
- **High Confidence**: 11/16 fields (68.8%)
- **Conflict Rate**: 0 (no concept conflicts)
- **Ready for Production**: ✅

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Phase 1: Field Specs                     │
│              (field_specs.py, get_sector.py)                │
│  - Define standard fields (revenue, netIncome, etc.)        │
│  - Define sector classification rules                        │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    Phase 2: Learning                         │
│                (run_learning.py @ training/)                 │
│  - Process 500 companies (global)                            │
│  - Process 150 companies per sector (banking/insurance/etc)  │
│  - Build virtual trees with occurrence rates                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                Phase 3: Integration & Deployment             │
│                                                               │
│  Task 1: Merge Trees (merge_virtual_trees.py)               │
│    - Merge global + sector trees                            │
│    - Output: virtual_trees_merged.json                       │
│                                                               │
│  Task 2: Build Mappings (build_map_schema.py)               │
│    - Generate core mappings (map_core.json)                  │
│    - Generate sector overlays (map_overlays/*.json)          │
│                                                               │
│  Task 3: Analyze Quality (analyze_mappings.py)              │
│    - Validate coverage and confidence                        │
│    - Output: MAPPING_QUALITY_REPORT.md                       │
│                                                               │
│  Task 4: Production API (apply_mappings.py)                  │
│    - Extract income statement fields                         │
│    - Auto-detect sector                                      │
│    - Validate extraction                                     │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Installation

```python
# The system is part of quant.xbrl_standardize package
from quant.xbrl_standardize.apply_mappings import extract_income_statement
```

### Basic Usage

```python
from quant.xbrl_standardize.apply_mappings import extract_income_statement

# Extract with core mappings (works for all companies)
facts = {
    'us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax': 100000000,
    'us-gaap_NetIncomeLoss': 20000000,
    'us-gaap_EarningsPerShareBasic': 2.50
}

result = extract_income_statement(facts)

print(result['data'])
# {
#   'revenue': 100000000,
#   'netIncome': 20000000,
#   'earningsPerShareBasic': 2.50
# }
```

### Sector-Specific Extraction

```python
# Extract with sector overlay (for banks, insurance, utilities)
result = extract_income_statement(facts, sector='banking')

# Auto-detect sector and extract
from quant.xbrl_standardize.apply_mappings import extract_with_auto_sector

result = extract_with_auto_sector(facts, sic=6021)  # Commercial bank SIC
# Automatically detects banking sector and applies appropriate mappings
```

### Validation

```python
from quant.xbrl_standardize.apply_mappings import validate_extraction

result = extract_income_statement(facts)
validation = validate_extraction(result, required_fields=['revenue', 'netIncome'])

print(validation)
# {
#   'valid': True,
#   'missing_required': [],
#   'has_all_required': True,
#   'low_confidence_fields': [],
#   'extraction_rate': 0.562
# }
```

## API Reference

### `extract_income_statement(facts, sector=None, config=None)`

Extract standardized income statement fields from XBRL facts.

**Parameters:**
- `facts` (Dict[str, Any]): Dictionary of XBRL facts {concept_name: value}
- `sector` (Optional[str]): Sector for sector-specific mappings ('banking', 'insurance', 'utilities')
- `config` (Optional[MappingConfig]): Custom mapping configuration

**Returns:**
- Dict containing:
  - `data`: Extracted fields {field_name: value}
  - `metadata`: Field metadata (concept used, confidence, label)
  - `sector`: Sector used (if any)
  - `fields_extracted`: Number of fields successfully extracted
  - `fields_total`: Total number of fields in mapping

**Example:**
```python
result = extract_income_statement(facts, sector='banking')
revenue = result['data']['revenue']
concept_used = result['metadata']['revenue']['concept']
```

### `detect_sector(facts, sic=None)`

Auto-detect company sector from SIC code or XBRL fact patterns.

**Parameters:**
- `facts` (Dict[str, Any]): XBRL facts dictionary
- `sic` (Optional[int]): SIC code for SIC-based detection

**Returns:**
- str: Detected sector name ('banking', 'insurance', 'utilities') or None

**Example:**
```python
sector = detect_sector(facts, sic=6021)
# Returns: 'banking'
```

### `extract_with_auto_sector(facts, sic=None)`

Extract income statement with automatic sector detection.

**Parameters:**
- `facts` (Dict[str, Any]): XBRL facts dictionary
- `sic` (Optional[int]): SIC code for sector detection

**Returns:**
- Dict: Extraction result with auto-detected sector

**Example:**
```python
result = extract_with_auto_sector(facts, sic=6021)
print(result['sector'])  # 'banking'
print(result['sector_auto_detected'])  # True
```

### `validate_extraction(result, required_fields=None)`

Validate extraction results.

**Parameters:**
- `result` (Dict[str, Any]): Extraction result from extract_income_statement()
- `required_fields` (Optional[List[str]]): Required field names (defaults to ['revenue', 'netIncome'])

**Returns:**
- Dict containing:
  - `valid`: True if all required fields extracted
  - `missing_required`: List of missing required fields
  - `has_all_required`: True if has all required fields
  - `low_confidence_fields`: List of low confidence fields
  - `extraction_rate`: Percentage of fields extracted

## Mapping Schema

### Core Mapping (`map/map_core.json`)

The core mapping contains global concept mappings that work across all industries:

```json
{
  "_meta": {
    "version": "1.0.0",
    "generated_from": "merged_virtual_trees",
    "min_occurrence_threshold": 0.10,
    "description": "Core XBRL concept mappings for income statement fields"
  },
  "fields": {
    "revenue": {
      "primary": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
      "confidence": "high",
      "occurrence_rate": 0.482,
      "label": "Revenue from Contract with Customer",
      "fallbacks": ["us-gaap:Revenues"],
      "metadata": {
        "occurrence_global": 0.482,
        "is_total": true
      }
    }
  }
}
```

**Field Structure:**
- `primary`: Primary XBRL concept to use
- `confidence`: Confidence level ('high', 'medium', 'low') based on occurrence rate
- `occurrence_rate`: Global occurrence rate (0-1)
- `label`: Human-readable label
- `fallbacks`: List of fallback concepts to try if primary not found
- `metadata`: Additional concept metadata

### Sector Overlays (`map/map_overlays/{sector}.json`)

Sector overlays override core mappings with sector-specific concepts:

```json
{
  "_meta": {
    "version": "1.0.0",
    "sector": "banking",
    "description": "Sector-specific XBRL concept mappings for banking"
  },
  "fields": {
    "revenue": {
      "primary": "us-gaap:Revenues",
      "confidence": "high",
      "occurrence_rate_sector": 0.523,
      "occurrence_rate_global": 0.241,
      "label": "Revenues",
      "sector_specific": false
    }
  }
}
```

**Supported Sectors:**
- `banking`: Commercial banks (SIC 6020-6099)
- `insurance`: Insurance carriers (SIC 6300-6399)
- `utilities`: Electric/gas/water utilities (SIC 4900-4999)

## Maintenance

### Updating Mappings

To update mappings with new data:

1. **Add new companies to learning set**:
   ```bash
   # Edit training/run_learning.py
   # Modify company selection or add new sectors
   ```

2. **Re-run learning pipeline**:
   ```bash
   cd training
   python run_learning.py --global --companies 500
   python run_learning.py --sector banking --companies 150
   ```

3. **Rebuild mappings**:
   ```bash
   cd quant/xbrl_standardize
   python merge_virtual_trees.py --input-dir ../../training/output
   python build_map_schema.py --trees map/virtual_trees_merged.json
   ```

4. **Analyze quality**:
   ```bash
   python analyze_mappings.py --core map/map_core.json --overlays map/map_overlays/*.json
   # Review MAPPING_QUALITY_REPORT.md
   ```

5. **Test updated mappings**:
   ```bash
   python test_apply_mappings.py
   # All tests should pass before deploying
   ```

### Adding New Sectors

To add a new sector (e.g., 'retail'):

1. **Define sector in `get_sector.py`**:
   ```python
   INDUSTRY_SECTOR_MAP = {
       # ... existing mappings ...
       'retail': (5200, 5999),  # SIC range
   }
   ```

2. **Add sector rules in `field_specs.py`** (if needed):
   ```python
   INCOME_STATEMENT_FIELDS = {
       'revenue': {
           # ... existing spec ...
           'sectorRules': {
               'retail': {
                   'candidateConcepts': [
                       'us-gaap:RetailSales',
                       'us-gaap:SalesRevenueNet'
                   ]
               }
           }
       }
   }
   ```

3. **Run sector-specific learning**:
   ```bash
   cd training
   python run_learning.py --sector retail --companies 150
   ```

4. **Rebuild mappings including new sector**:
   ```bash
   cd quant/xbrl_standardize
   python build_map_schema.py --trees map/virtual_trees_merged.json --sectors banking insurance utilities retail
   ```

### Quality Thresholds

Recommended thresholds for production:

- **Coverage Rate**: ≥90% (percentage of required fields mapped)
- **High Confidence**: ≥50% (fields with >30% occurrence rate)
- **Conflicts**: 0 (no multiple fields mapping to same concept)
- **Mean Occurrence**: ≥40% (average occurrence rate across fields)

If metrics fall below thresholds:
1. Review `MAPPING_QUALITY_REPORT.md` for details
2. Lower occurrence thresholds in `build_map_schema.py`
3. Add manual mappings for missing fields
4. Increase training company count

## File Structure

```
quant/xbrl_standardize/
│
├── README.md                          # This file
├── field_specs.py                     # Phase 1: Standard field definitions
├── get_sector.py                      # Phase 1: Sector classification
│
├── apply_mappings.py                  # Phase 3: Production API
├── test_apply_mappings.py             # Phase 3: Integration tests
├── test_real_companies.py             # Phase 3: Real data validation
│
├── merge_virtual_trees.py             # Phase 3: Task 1 - Merge trees
├── build_map_schema.py                # Phase 3: Task 2 - Build mappings
├── analyze_mappings.py                # Phase 3: Task 3 - Quality analysis
│
└── map/                               # Generated mapping files
    ├── virtual_trees_merged.json      # Merged virtual trees (165 KB)
    ├── map_core.json                  # Core global mappings (10.1 KB)
    ├── MAPPING_QUALITY_REPORT.md      # Quality analysis report
    │
    └── map_overlays/                  # Sector-specific overlays
        ├── banking.json               # Banking overlay (2.4 KB)
        ├── insurance.json             # Insurance overlay (2.9 KB)
        └── utilities.json             # Utilities overlay (2.9 KB)
```

## Testing

### Unit Tests

Run integration tests:
```bash
cd quant/xbrl_standardize
python test_apply_mappings.py
```

Expected output:
```
TOTAL: 7/7 tests passed
✅ All tests passed! Mappings are production-ready.
```

### Real Company Validation

Test with real Edgar data:
```bash
python test_real_companies.py
```

**Note**: Requires network access and is subject to SEC rate limiting.

## Performance

- **Mapping Load Time**: <10ms (cached after first load)
- **Extraction Time**: <1ms per company
- **Memory Footprint**: ~20MB (all mappings loaded)

## Troubleshooting

### Low Extraction Rate

**Problem**: `extraction_rate` consistently <30%

**Solutions**:
1. Check if facts are using correct namespace format (`us-gaap_` vs `us-gaap:`)
2. Try normalizing concept names before extraction
3. Review `metadata` to see which concepts were attempted
4. Add more fallback concepts to mapping

### Sector Not Detected

**Problem**: `detect_sector()` returns None

**Solutions**:
1. Verify SIC code is correct and in range
2. Check if company uses sector-specific concepts
3. Review fact patterns in `apply_mappings.py` `detect_sector()`
4. Add custom sector detection logic

### Missing Required Fields

**Problem**: Validation fails with missing required fields

**Solutions**:
1. Check if concepts exist in facts dictionary
2. Try using fallback concepts manually
3. Review field spec in `field_specs.py`
4. Add company-specific manual mappings

## Contributing

To contribute new features or improvements:

1. Add new field definitions in `field_specs.py`
2. Re-run learning pipeline with updated specs
3. Rebuild mappings
4. Add tests in `test_apply_mappings.py`
5. Update documentation

## License

Part of the EdgarTools project.

## Support

For issues or questions:
- Review `MAPPING_QUALITY_REPORT.md` for mapping quality metrics
- Check `test_apply_mappings.py` for usage examples
- See `PHASE_3_PLAN.md` for system architecture details
