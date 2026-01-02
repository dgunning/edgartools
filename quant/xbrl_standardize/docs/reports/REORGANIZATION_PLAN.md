# XBRL Standardize Reorganization Plan

**Date**: 2026-01-02
**Purpose**: Organize file structure and correct soft fork protocol violations

---

## Current Issues

1. ❌ Files scattered in root directory (no clear structure)
2. ❌ Documentation mixed with code
3. ❌ ML data located outside quant folder (`training/output/`)
4. ❌ ML training script in edgar repo (`edgar/entity/training/run_learning.py`)

---

## Proposed Directory Structure

```
quant/xbrl_standardize/
├── README.md                          # Main documentation
├── __init__.py                        # Package init
│
├── schemas/                           # ✅ JSON mapping schemas
│   ├── income-statement.json
│   ├── balance-sheet.json
│   └── cash-flow.json
│
├── extractors/                        # ✅ Python extraction scripts
│   ├── is.py                         # Income statement extractor
│   ├── bs.py                         # Balance sheet extractor
│   └── cf.py                         # Cash flow extractor
│
├── overlays/                          # ✅ Industry-specific overlays
│   ├── banking.json
│   ├── insurance.json
│   └── utilities.json
│
├── tools/                             # ✅ Utilities and automation
│   ├── audit_mapping_with_ml.py      # ML audit tool
│   ├── build_map_schema.py           # Schema builder
│   ├── analyze_mappings.py           # Quality analyzer
│   ├── apply_mappings.py             # Production API
│   ├── merge_virtual_trees.py        # Tree merger
│   └── validate_config.py            # Config validator
│
├── ml_data/                           # ✅ ML-learned data (RELOCATED)
│   ├── canonical_structures_global.json
│   ├── canonical_structures_banking.json
│   ├── canonical_structures_insurance.json
│   ├── canonical_structures_utilities.json
│   ├── learned_mappings_global.json
│   ├── learned_mappings_banking.json
│   ├── learned_mappings_insurance.json
│   ├── learned_mappings_utilities.json
│   ├── learning_statistics_global.json
│   ├── learning_statistics_banking.json
│   ├── learning_statistics_insurance.json
│   ├── learning_statistics_utilities.json
│   ├── concept_linkages_global.json
│   ├── concept_linkages_banking.json
│   ├── concept_linkages_insurance.json
│   ├── concept_linkages_utilities.json
│   ├── statement_mappings_v1_global.json
│   ├── statement_mappings_v1_banking.json
│   ├── statement_mappings_v1_insurance.json
│   ├── statement_mappings_v1_utilities.json
│   ├── learning_summary_global.json
│   ├── learning_summary_banking.json
│   ├── learning_summary_insurance.json
│   ├── learning_summary_utilities.json
│   └── virtual_trees_merged.json
│
├── ml_training/                       # ✅ ML training scripts (COPIED)
│   ├── run_learning.py               # Copy from edgar/entity/training/
│   ├── README.md                     # How to run ML training
│   └── requirements.txt              # Training dependencies
│
├── tests/                             # ✅ Test scripts
│   ├── test_apply_mappings.py
│   ├── test_real_companies.py
│   ├── test_real_quick.py
│   ├── debug_aapl_revenue.py
│   └── debug_bank_nulls.py
│
├── docs/                              # ✅ Documentation
│   ├── design/                       # Design docs
│   │   ├── MAP_JSON_ENHANCEMENTS.md
│   │   ├── LEVERAGING_ML_LEARNINGS.md
│   │   └── standardization_plan.md
│   ├── fixes/                        # Bug fix docs
│   │   ├── BUGFIX_PRIORITY_OVERLAP.md
│   │   ├── BALANCE_SHEET_SEMANTIC_FIXES.md
│   │   └── ISSUE_5_COMPONENT_VS_TOTAL.md
│   ├── reports/                      # Analysis reports
│   │   ├── MAPPING_QUALITY_REPORT.md
│   │   ├── AUDIT_REPORT_BALANCE_SHEET.md
│   │   ├── REAL_COMPANY_VALIDATION_RESULTS.md
│   │   ├── TECHNICAL_REPORT_RESPONSE.md
│   │   └── SESSION_ACCOMPLISHMENTS.md
│   └── guides/                       # User guides
│       ├── BANK_NULL_FIELDS_EXPLAINED.md
│       └── README.md (sector templates)
│
└── archive/                           # ✅ Deprecated/old files
    ├── field_specs.py                # Old field specs
    ├── is.py (root)                  # Old income statement extractor
    └── ...
```

---

## File Moves

### Schemas
- ✅ `map/income-statement.json` → `schemas/income-statement.json`
- ✅ `map/balance-sheet.json` → `schemas/balance-sheet.json`
- ✅ `map/cash-flow.json` → `schemas/cash-flow.json`

### Extractors
- ✅ `map/is.py` → `extractors/is.py`
- ✅ `map/bs.py` → `extractors/bs.py`
- ✅ `map/cf.py` → `extractors/cf.py`

### Overlays
- ✅ `map/map_overlays/banking.json` → `overlays/banking.json`
- ✅ `map/map_overlays/insurance.json` → `overlays/insurance.json`
- ✅ `map/map_overlays/utilities.json` → `overlays/utilities.json`

### Tools
- ✅ `tools/audit_mapping_with_ml.py` → `tools/audit_mapping_with_ml.py` (already good)
- ✅ `build_map_schema.py` → `tools/build_map_schema.py`
- ✅ `analyze_mappings.py` → `tools/analyze_mappings.py`
- ✅ `apply_mappings.py` → `tools/apply_mappings.py`
- ✅ `merge_virtual_trees.py` → `tools/merge_virtual_trees.py`
- ✅ `validate_config.py` → `tools/validate_config.py`

### ML Data (RELOCATE from `training/output/`)
- ✅ `training/output/*.json` → `ml_data/*.json`

### ML Training (COPY from `edgar/entity/training/`)
- ✅ `edgar/entity/training/run_learning.py` → `ml_training/run_learning.py`

### Tests
- ✅ `test_apply_mappings.py` → `tests/test_apply_mappings.py`
- ✅ `test_real_companies.py` → `tests/test_real_companies.py`
- ✅ `test_real_quick.py` → `tests/test_real_quick.py`
- ✅ `debug_aapl_revenue.py` → `tests/debug_aapl_revenue.py`
- ✅ `debug_bank_nulls.py` → `tests/debug_bank_nulls.py`

### Documentation
- ✅ Design docs → `docs/design/`
- ✅ Fix docs → `docs/fixes/`
- ✅ Reports → `docs/reports/`
- ✅ Guides → `docs/guides/`

### Archive
- ✅ `field_specs.py` → `archive/field_specs.py` (old/unused)
- ✅ `is.py` (root) → `archive/is_old.py` (old version)
- ✅ `map/virtual_trees_merged.json` → `ml_data/virtual_trees_merged.json`
- ✅ `map/standardization_plan.md` → `docs/design/standardization_plan.md`
- ✅ `map/MAPPING_QUALITY_REPORT.md` → `docs/reports/MAPPING_QUALITY_REPORT.md`

---

## Soft Fork Violation Corrections

### Issue #1: ML Data Outside Quant Folder

**Current**: `training/output/` (OUTSIDE quant folder)
**Fix**: Move to `quant/xbrl_standardize/ml_data/`

```bash
mv training/output/* quant/xbrl_standardize/ml_data/
```

### Issue #2: ML Training Script in Edgar Repo

**Current**: `edgar/entity/training/run_learning.py` (IN edgar repo)
**Fix**: Copy to `quant/xbrl_standardize/ml_training/run_learning.py`

**Strategy**:
1. Copy `run_learning.py` to quant folder
2. Update import paths to reference edgar as external dependency
3. Create README in `ml_training/` explaining usage
4. DO NOT modify original in edgar repo (read-only reference)

```python
# ml_training/run_learning.py
# Updated imports to treat edgar as external package
from edgar import Company, set_identity  # External dependency
# No need to modify edgar repo files
```

### Issue #3: Reference to External Files

**Strategy**: Update all scripts to reference new locations:
- `tools/audit_mapping_with_ml.py`: Update `--ml-data` default to `../ml_data/`
- `extractors/*.py`: Update mapping paths to `../schemas/`
- `tools/*.py`: Update paths to reference new structure

---

## Implementation Steps

### Step 1: Create Directory Structure
```bash
mkdir -p schemas extractors overlays tools ml_data ml_training tests docs/{design,fixes,reports,guides} archive
```

### Step 2: Move Schemas
```bash
mv map/income-statement.json schemas/
mv map/balance-sheet.json schemas/
mv map/cash-flow.json schemas/
```

### Step 3: Move Extractors
```bash
mv map/is.py extractors/
mv map/bs.py extractors/
mv map/cf.py extractors/
```

### Step 4: Move Overlays
```bash
mv map/map_overlays/banking.json overlays/
mv map/map_overlays/insurance.json overlays/
mv map/map_overlays/utilities.json overlays/
```

### Step 5: Move Tools
```bash
mv build_map_schema.py tools/
mv analyze_mappings.py tools/
mv apply_mappings.py tools/
mv merge_virtual_trees.py tools/
mv validate_config.py tools/
```

### Step 6: Relocate ML Data
```bash
cp -r /c/edgartools_git/training/output/* ml_data/
```

### Step 7: Copy ML Training Script
```bash
cp /c/edgartools_git/edgar/entity/training/run_learning.py ml_training/
```

### Step 8: Move Tests
```bash
mv test_*.py tests/
mv debug_*.py tests/
```

### Step 9: Organize Documentation
```bash
mv MAP_JSON_ENHANCEMENTS.md docs/design/
mv LEVERAGING_ML_LEARNINGS.md docs/design/
mv BUGFIX_PRIORITY_OVERLAP.md docs/fixes/
mv BALANCE_SHEET_SEMANTIC_FIXES.md docs/fixes/
mv ISSUE_5_COMPONENT_VS_TOTAL.md docs/fixes/
mv MAPPING_QUALITY_REPORT.md docs/reports/  # if exists in root
mv AUDIT_REPORT_BALANCE_SHEET.md docs/reports/
mv REAL_COMPANY_VALIDATION_RESULTS.md docs/reports/
mv TECHNICAL_REPORT_RESPONSE.md docs/reports/
mv SESSION_ACCOMPLISHMENTS.md docs/reports/
mv BANK_NULL_FIELDS_EXPLAINED.md docs/guides/
```

### Step 10: Archive Old Files
```bash
mv field_specs.py archive/ # if unused
mv is.py archive/is_old.py # if old version exists in root
```

### Step 11: Update Import Paths

See next section for path updates.

---

## Path Updates Required

### `extractors/is.py`, `extractors/bs.py`, `extractors/cf.py`
```python
# OLD:
with open("map.json", "r") as f: mapping = json.load(f)

# NEW:
from pathlib import Path
schema_path = Path(__file__).parent.parent / "schemas" / "income-statement.json"
with open(schema_path, "r") as f: mapping = json.load(f)
```

### `tools/audit_mapping_with_ml.py`
```python
# Update default ML data path
parser.add_argument('--ml-data', default='../ml_data',
                   help='Path to ML data directory')
```

### `tools/build_map_schema.py`
```python
# Update output paths
parser.add_argument('--output-dir', default='../schemas',
                   help='Output directory for schemas')
```

---

## Validation Checklist

After reorganization:

- [ ] All schemas in `schemas/` directory
- [ ] All extractors in `extractors/` directory
- [ ] All ML data in `ml_data/` (inside quant folder)
- [ ] ML training script in `ml_training/` (inside quant folder)
- [ ] All tools in `tools/` directory
- [ ] All tests in `tests/` directory
- [ ] All docs in `docs/{design,fixes,reports,guides}/`
- [ ] No files in root except README.md and __init__.py
- [ ] Import paths updated and working
- [ ] Tests pass with new structure
- [ ] ML audit tool works with new paths

---

## Benefits

1. ✅ **Clear organization**: Schemas, extractors, tools, tests separated
2. ✅ **Soft fork compliance**: All ML data and training inside quant folder
3. ✅ **Maintainability**: Easy to find files by purpose
4. ✅ **Documentation**: Organized by type (design, fixes, reports, guides)
5. ✅ **Scalability**: Easy to add new schemas, extractors, or sectors

---

**Status**: READY TO EXECUTE
