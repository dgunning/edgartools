# Edgar Repo Modification - Detailed Analysis

**Date**: 2026-01-02
**File**: `edgar/entity/training/run_learning.py`
**Status**: ❌ **MODIFIED (VIOLATION)**

---

## Git Status

```bash
git status edgar/entity/training/run_learning.py
```

**Result**:
```
Changes not staged for commit:
  modified:   edgar/entity/training/run_learning.py
```

---

## Modifications Made

### 1. Added `tag` Parameter to `generate_outputs()`

**Before**:
```python
def generate_outputs(self, output_dir: Path) -> Dict[str, Any]:
    """Generate all output files."""
```

**After**:
```python
def generate_outputs(self, output_dir: Path, tag: str = '') -> Dict[str, Any]:
    """
    Generate all output files.

    Args:
        output_dir: Directory to write outputs to
        tag: Optional tag to append to filenames (e.g., 'global', 'banking')
    """
```

**Impact**: All output files now support suffix tagging:
- `learned_mappings.json` → `learned_mappings_global.json`
- `canonical_structures.json` → `canonical_structures_banking.json`
- etc.

---

### 2. Added `get_companies_multi_exchange()` Function

**New Function** (~50 lines):
```python
def get_companies_multi_exchange(exchanges: List[str], count: int, random_state: int = 42) -> List[str]:
    """
    Get list of company tickers from multiple exchanges.

    OPTIMIZED: Uses multiple exchange sources to create diverse global dataset.
    """
```

**Purpose**: Support global learning across NYSE, Nasdaq, etc.

---

### 3. Added `get_companies_by_sector()` Function

**New Function** (~120 lines):
```python
def get_companies_by_sector(sector_key: str, count: int, random_state: int = 42) -> List[str]:
    """
    Get list of company tickers for a specific sector using CIK_CODES.csv.

    OPTIMIZED: Uses pre-built CSV index instead of scanning 949K submission files.
    This reduces sector company discovery from ~3 hours to <1 second.
    """
```

**Purpose**: Enable sector-specific learning (banking, insurance, utilities)

**Key Feature**: References `quant/xbrl_standardize/CIK_CODES.csv` for fast lookup:
```python
csv_path = Path(__file__).parent.parent.parent.parent / "quant" / "xbrl_standardize" / "CIK_CODES.csv"
```

---

### 4. Enhanced Command-Line Arguments

**New Arguments**:
```python
parser.add_argument('--exchanges', type=str, default=None,
                   help='Comma-separated exchanges (e.g., "NYSE,Nasdaq")')
parser.add_argument('--sector', type=str, default=None,
                   help='Sector key for sector-specific learning')
parser.add_argument('--tag', type=str, default='',
                   help='Tag to append to output filenames')
```

**Examples**:
```bash
# Global multi-exchange
python run_learning.py --exchanges NYSE,Nasdaq --companies 500 --tag global

# Sector-specific
python run_learning.py --sector financials_banking --companies 150 --tag banking
```

---

### 5. Updated Output File Generation

**All Output Files Modified**:
```python
# Before:
with open(output_dir / 'learned_mappings.json', 'w') as f:

# After:
with open(output_dir / f'learned_mappings{suffix}.json', 'w') as f:
```

**Files Affected**:
- `learned_mappings.json`
- `virtual_trees.json`
- `statement_mappings_v1.json`
- `canonical_structures.json`
- `learning_summary.json`
- `structural_learning_report.md`
- `concept_linkages.json`
- `learning_statistics.json`

---

## Lines Changed

**Total Diff Statistics**:
- **~200 lines added**
- **~20 lines modified**
- **0 lines deleted**

**Sections Modified**:
1. `generate_outputs()` method signature and all file writes
2. `main()` function - argument parsing and company selection logic
3. Two new functions added: `get_companies_multi_exchange()`, `get_companies_by_sector()`

---

## Violation Severity

**Severity**: 🔴 **HIGH**

**Reasons**:
1. ❌ Modifications made to file in `edgar/` repo (outside quant folder)
2. ❌ ~200 lines of new code added
3. ❌ Creates dependency from edgar repo → quant folder (CIK_CODES.csv reference)
4. ❌ Changes affect core functionality (file naming, company selection)
5. ❌ Not committed/tracked in git (unstaged changes)

---

## Impact Assessment

### Functionality Impact
- ✅ **Positive**: Enables sector-specific ML training
- ✅ **Positive**: Allows output file tagging for organization
- ✅ **Positive**: Faster company lookup via CSV (~3 hours → <1 second)
- ❌ **Negative**: Creates coupling between edgar repo and quant folder

### Maintenance Impact
- ❌ Upstream merges will conflict with these changes
- ❌ Other developers won't have these modifications
- ❌ Changes not documented in edgar repo
- ❌ CSV path dependency fragile (breaks if folder structure changes)

---

## Remediation Options

### Option 1: Revert Modifications ⚠️ (Recommended)

**Action**: Restore original file, implement functionality in quant folder only

```bash
cd /c/edgartools_git
git restore edgar/entity/training/run_learning.py
```

**Alternative Implementation**:
1. Keep original `run_learning.py` as-is
2. Create `quant/xbrl_standardize/ml_training/run_learning_wrapper.py`
3. Wrapper calls original script multiple times with different configs
4. Post-process outputs to add tags

**Pros**:
- ✅ No edgar repo modifications
- ✅ Clean separation of concerns
- ✅ No upstream merge conflicts

**Cons**:
- ⚠️ Slightly slower (multiple script invocations)
- ⚠️ Need to coordinate multiple runs

---

### Option 2: Create Patch File 📋

**Action**: Extract changes as patch, apply when needed

```bash
cd /c/edgartools_git
git diff edgar/entity/training/run_learning.py > quant/xbrl_standardize/ml_training/run_learning_enhancements.patch
git restore edgar/entity/training/run_learning.py
```

**Usage**:
```bash
# When training is needed, apply patch temporarily
git apply quant/xbrl_standardize/ml_training/run_learning_enhancements.patch

# Run training
python edgar/entity/training/run_learning.py --sector banking --tag banking

# Revert patch
git restore edgar/entity/training/run_learning.py
```

**Pros**:
- ✅ Edgar repo stays clean in git
- ✅ Enhancements available when needed
- ✅ Documented in quant folder

**Cons**:
- ⚠️ Manual patch apply/revert workflow
- ⚠️ Patch may break on upstream changes

---

### Option 3: Fork and Extend 🔀 (Most Compliant)

**Action**: Create extended version in quant folder that imports original

```python
# quant/xbrl_standardize/ml_training/run_learning_extended.py

import sys
from pathlib import Path

# Import original script functionality
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "edgar" / "entity" / "training"))
from run_learning import ConceptLearner, get_companies  # Import base functionality

# Add extensions
def get_companies_by_sector(sector_key, count, random_state=42):
    """Extended sector selection using local CIK_CODES.csv"""
    # Implementation here

def run_with_tag(tag, **kwargs):
    """Wrapper that adds tagging to output files"""
    learner = ConceptLearner(...)
    # ... process ...

    # Post-process outputs to add tag
    for file in output_dir.glob("*.json"):
        new_name = file.stem + f"_{tag}" + file.suffix
        file.rename(file.parent / new_name)

if __name__ == '__main__':
    # Custom argument parsing
    # Call original functionality + extensions
```

**Pros**:
- ✅ No edgar repo modifications
- ✅ All enhancements in quant folder
- ✅ Can reuse original script logic

**Cons**:
- ⚠️ More complex code structure
- ⚠️ May need to duplicate some logic

---

### Option 4: Upstream Contribution 🌐

**Action**: Submit modifications to upstream edgar repo as enhancement

**Steps**:
1. Create feature branch in edgar repo
2. Clean up modifications (remove quant-specific references)
3. Submit PR to upstream
4. Wait for acceptance

**Pros**:
- ✅ Proper open-source contribution
- ✅ Benefits all users
- ✅ Long-term maintainable

**Cons**:
- ⏳ Slow (PR review process)
- ⚠️ May be rejected
- ⚠️ Need to maintain compatibility

---

## Recommended Action Plan

### Immediate (Today)

1. **Create Patch File** (Option 2):
```bash
cd /c/edgartools_git
git diff edgar/entity/training/run_learning.py > quant/xbrl_standardize/ml_training/run_learning_enhancements.patch
```

2. **Revert Edgar Repo**:
```bash
git restore edgar/entity/training/run_learning.py
```

3. **Document Patch Usage**:
- Update `ml_training/README.md` with patch apply/revert instructions

4. **Verify Compliance**:
```bash
git status edgar/
# Should show: "nothing to commit, working tree clean"
```

---

### Short-Term (Next Session)

1. **Implement Wrapper Script** (Option 3):
   - Create `run_learning_extended.py` in quant folder
   - Import and extend original script functionality
   - Add sector selection and tagging logic

2. **Test Wrapper**:
   - Run global training
   - Run sector-specific training
   - Verify output files match expected format

3. **Update Documentation**:
   - Document wrapper usage
   - Explain why wrapper is needed (soft fork compliance)

---

### Long-Term (Future)

1. **Consider Upstream Contribution** (Option 4):
   - Clean up enhancements
   - Make sector selection generic (not quant-specific)
   - Submit PR to edgar repo

2. **Or: Maintain as Extension**:
   - Keep wrapper approach
   - Document as "enhanced ML training for quant use cases"
   - Accept that it's a quant-specific extension

---

## Current Status

**Edgar Repo**: ❌ **DIRTY** (unstaged modifications)

**Files Modified**:
- `edgar/entity/training/run_learning.py` (~200 lines changed)

**Dependencies Created**:
- References `quant/xbrl_standardize/CIK_CODES.csv`
- Imports from `quant.xbrl_standardize` module

**Git Status**:
```
Changes not staged for commit:
  modified:   edgar/entity/training/run_learning.py
```

---

## Compliance Scorecard

| Requirement | Status | Notes |
|-------------|--------|-------|
| All code in quant folder | ❌ FAIL | Code added to edgar/ |
| No edgar repo modifications | ❌ FAIL | 200+ lines changed |
| ML data in quant folder | ✅ PASS | Now in ml_data/ |
| ML training in quant folder | ⚠️ PARTIAL | Script copied but original modified |
| No upstream conflicts | ❌ FAIL | Will conflict on merge |
| Clean git status | ❌ FAIL | Unstaged changes |

**Overall**: ❌ **NON-COMPLIANT** (4/6 requirements failing)

---

## Next Steps

**Recommended**:
1. ✅ Create patch file immediately
2. ✅ Revert edgar repo to clean state
3. ✅ Document patch in ml_training/README.md
4. 📅 Plan wrapper implementation for next session

**Alternative**:
1. Keep modifications if upstream contribution planned
2. Commit to feature branch
3. Prepare PR for upstream

**Decision Point**: Choose Option 2 (patch) or Option 3 (wrapper) based on:
- Frequency of ML training (frequent → wrapper, rare → patch)
- Upstream contribution intent (yes → keep for PR, no → wrapper)
- Team preference (patch simpler, wrapper more robust)

---

**Analysis Date**: 2026-01-02
**Violation Confirmed**: Yes
**Severity**: High
**Recommended Action**: Revert + Create Patch (Option 2)
