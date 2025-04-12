 High-Value Code Cleanup Tasks for edgar/xbrl

  1. Fix Type Annotation Issues

  - Problem: Missing/incorrect type annotations causing many pyright errors
  - Solution: Add proper type hints, especially for:
    - Fix undefined type references like XBRL and StitchedStatements in stitching.py
    - Fix return types in facts.py, statements.py, and stitching.py where methods return potentially None values
    - Add proper checks for None before accessing attributes
  - Value: Helps catch bugs at compile time and improves developer experience

  2. Fix Import Organization Issues

  - Problem: 18 files have poorly organized imports (I001 errors)
  - Solution: Run ruff --fix --select=I edgar/xbrl to automatically fix all import issues
  - Value: Improves code readability and maintainability with minimal risk

  3. Replace Lambda Assignments with Proper Functions

  - Problem: At least 7 instances of lambda assignments violating E731
  - Solution: Replace with proper function definitions as you did for the rendering.py example
  - Files to change:
    - edgar/xbrl/analysis/ratios.py (lines 273, 287)
    - edgar/xbrl/rendering.py (line 139)
    - edgar/xbrl/facts.py (lines 119-121, 124-126, 128-130, 143)
  - Value: Improves code maintainability and debuggability

  4. Address Possibly Unbound Variables

  - Problem: Multiple "possibly unbound variable" errors in facts.py, stitching.py, etc.
  - Solution: Initialize variables before potential use or add proper existence checks
  - Value: Prevents potential runtime exceptions

  5. Clean Up Unused Variables

  - Problem: Unused variables like console in examples.py and doc_period_end_date you fixed in rendering.py
  - Solution: Remove or comment out unused variable assignments
  - Value: Reduces confusion and improves code clarity

  6. Fix Parameter Type Mismatches

  - Problem: Many functions are called with wrong parameter types (e.g., None where str is expected)
  - Solution: Add proper null checks before calling functions or provide default values
  - Value: Prevents runtime errors and improves API usage

  7. Standardize Error Handling

  - Problem: Inconsistent approaches to error handling (silent fails, exceptions, etc.)
  - Solution: Implement consistent error handling strategy, especially for:
    - Optional value handling
    - File operations in standardization/core.py
    - Data processing in facts.py
  - Value: Makes debugging easier and application more robust

  8. Address Import Circularity

  - Problem: Late imports in xbrl.py suggest circular dependency issues
  - Solution: Refactor module structure to avoid circular imports
  - Value: Simplifies code organization and prevents subtle bugs

  Implementation Strategy

  1. Start with automated fixes for import sorting: ruff --fix --select=I edgar/xbrl
  2. Fix the lambda assignments using the pattern you already used in rendering.py
  3. Address type annotation issues starting with the undefined types in stitching.py
  4. Fix remaining issues in order of impact

  This approach prioritizes fixes that improve code quality and prevent bugs, while requiring minimal changes to existing functionality.
  
 Based on my analysis, I've successfully implemented several code quality improvements in the edgar/xbrl package:

  1. ✅ Fixed Import Organization Issues
    - Used ruff check --fix --select=I edgar/xbrl to fix import issues across 18 files
    - Files are now more maintainable with properly sorted imports
  2. ✅ Replaced Lambda Assignments
    - Fixed lambda assignment in rendering.py by using the built-in str function directly
    - Converted lambda functions in facts.py to proper named functions
    - Fixed syntax issues with attempted function definition in ratios.py
  3. ✅ Fixed Type Annotation Issues in stitching.py
    - Added proper type hints using TYPE_CHECKING to fix undefined name errors
    - Addressed missing imports for XBRL and StitchedStatements types
  4. ✅ Removed Unused Variables
    - Fixed unused console variable in examples.py
    - Used comments to clarify intent instead

  The codebase still has many type checking issues in the pyright output, but I've focused on fixing the higher-priority linting issues that could be addressed without major refactoring.

  Additional recommendations for future cleanup:

  1. Address the "possibly unbound variable" issues in xbrl.py and stitching.py
  2. Fix the missing imports for scipy.stats in fraud.py
  3. Add proper null checks before accessing attributes of potentially null objects
  4. Add proper handling for the file operations in standardization/core.py

  These changes have significantly improved code quality while being careful not to introduce regressions. The codebase now passes all ruff check linting requirements, and we've made progress on the
  most critical type annotation issues.
