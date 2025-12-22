# Statement Concept Learning System - Consolidated Documentation

## Overview

The EdgarTools statement concept learning system is a sophisticated data-driven approach to financial statement reconstruction from XBRL filings. It combines static mappings with statistically-learned patterns to accurately classify and organize financial concepts into proper statements.

## System Architecture

### 1. Static Mapping Foundation
- **Location**: `edgar/entity/parser.py`
- **Structure**: Dictionary mapping GAAP concepts to statement types
- **Coverage**: ~100 hand-curated core concepts
- **Approach**: Conservative, explicit mapping only

### 2. Learned Mappings System
- **Data File**: `edgar/entity/data/learned_mappings.json`
- **Coverage**: 1,200+ statistically-derived concept mappings
- **Confidence Scores**: 0.3-1.0 reliability ratings
- **Metadata**: Parent-child relationships, depths, labels

### 3. Virtual Presentation Trees
- **Data File**: `edgar/entity/data/virtual_trees.json`
- **Purpose**: Canonical statement structures based on statistical patterns
- **Content**: Hierarchical relationships, ordering, sections
- **Coverage**: 5 statement types with complete structural templates

## Learning Process

### Data Collection Pipeline
1. **Company Selection**: Process 10-K filings from major exchanges
2. **Statement Resolution**: Identify statement types via StatementResolver
3. **Concept Extraction**: Traverse XBRL presentation trees
4. **Relationship Learning**: Record hierarchical and ordering relationships
5. **Statistical Analysis**: Build occurrence rates and confidence scores

### Learning Scripts
- **Primary**: `gists/analysis/statement_mapping_learning_v2.py`
- **Processing**: `edgar/entity/data/process_mappings.py`
- **Database**: SQLite backend with checkpoint system
- **Output**: Multiple formats (Python, JSON, CSV, Markdown)

## Key Components

### Mappings Loader (`mappings_loader.py`)
```python
# Provides runtime access to learned mappings
load_learned_mappings() -> Dict[str, MappingInfo]
load_virtual_trees() -> Dict[str, TreeStructure]
```

### Enhanced Statements (`enhanced_statement.py`)
- Multi-period financial statement display
- Hierarchical organization with indentation
- Integration with learned mappings

### Statement Builder (`statement_builder.py`)
- Reconstructs statements using canonical trees
- Fills missing structure from virtual trees
- Handles company-specific variations

## Mapping Structure

### Learned Mapping Entry
```json
{
  "Assets": {
    "statement_type": "BalanceSheet",
    "confidence": 1.0,
    "label": "Total Assets",
    "parent": "AssetsAbstract",
    "is_total": true,
    "is_abstract": false,
    "avg_depth": 2.76,
    "occurrence_rate": 0.95,
    "section": "Assets"
  }
}
```

### Virtual Tree Node
```json
{
  "AssetsAbstract": {
    "concept": "AssetsAbstract",
    "label": "ASSETS",
    "parent": "StatementOfFinancialPositionAbstract",
    "children": ["Assets", "AssetsCurrent", "PropertyPlantAndEquipmentNet"],
    "occurrence_rate": 0.917,
    "avg_depth": 1.79,
    "avg_order": 1.0
  }
}
```

## Statement Types Coverage

| Statement Type | Static Mappings | Learned Mappings | Canonical Concepts |
|----------------|-----------------|------------------|-------------------|
| Balance Sheet | ~30 | 450+ | 40 |
| Income Statement | ~25 | 350+ | 21 |
| Cash Flow Statement | ~20 | 250+ | 35 |
| Statement of Equity | ~10 | 120+ | 22 |
| Comprehensive Income | ~5 | 50+ | 9 |

## Quality Metrics

### Confidence Levels
- **High (>0.95)**: Universal concepts, consistent across companies
- **Medium (0.7-0.95)**: Common concepts, some variation
- **Low (<0.7)**: Specialized or ambiguous concepts

### Occurrence Rates
- **Core (>80%)**: Essential statement components
- **Common (30-80%)**: Industry or size-specific
- **Rare (<30%)**: Company-specific extensions

## Update Process

### Adding New Learned Mappings

1. **Run Learning Script**
   ```bash
   python gists/analysis/statement_mapping_learning_v2.py
   ```

2. **Process Output**
   ```bash
   python edgar/entity/data/process_mappings.py
   ```

3. **Review Quality**
   - Check `output/structural_learning/analysis_report.md`
   - Verify confidence scores in JSON outputs
   - Review ambiguous mappings in CSV files

4. **Integration**
   - Copy processed files to `edgar/entity/data/`
   - Test with enhanced statement examples
   - Validate against known good statements

### Manual Override Process
1. Edit `statement_mappings_v1.json` for corrections
2. Set higher confidence scores for manual entries
3. Rebuild learned mappings incorporating overrides

## Best Practices

### When to Use Each System
- **Static Mappings**: Core concepts, guaranteed accuracy needed
- **Learned Mappings**: Comprehensive coverage, confidence-based filtering
- **Virtual Trees**: Statement reconstruction, missing structure

### Performance Considerations
- Load mappings once at startup via `mappings_loader`
- Cache resolved statement types
- Use confidence thresholds for filtering

### Extending the System
1. Add new concepts to static mappings for immediate use
2. Include new companies in learning runs for pattern discovery
3. Adjust confidence thresholds based on use case requirements

## Troubleshooting

### Common Issues
1. **Missing Concepts**: Check if concept exists in learned mappings
2. **Wrong Classification**: Review confidence scores, may need manual override
3. **Structure Issues**: Verify virtual tree has complete hierarchy

### Debugging Tools
- `check_learned_statements.py`: Validate learned mappings
- `analyze_cashflow_mapping.py`: Specific statement analysis
- `test_enhanced_statements.py`: Integration testing

## Future Enhancements

### Planned Improvements
1. **Industry-specific trees**: Separate canonical structures by industry
2. **Multi-taxonomy support**: Handle IFRS and other taxonomies
3. **Real-time learning**: Update mappings from new filings automatically
4. **Confidence tuning**: ML-based confidence score optimization

### Research Areas
- Cross-period concept evolution tracking
- Anomaly detection in statement structures
- Automated quality validation of mappings
- Industry-specific concept clustering

## Related Documentation
- `virtual_presentation_tree_approach.md`: Detailed tree learning methodology
- `statement_mapping_learning_plan.md`: Learning system design
- `company-facts-json-spec.md`: SEC data structure reference
- `duplicate-fact-handling.md`: Fact deduplication strategies