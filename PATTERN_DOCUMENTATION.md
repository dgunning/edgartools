# EdgarTools Financial Statement Rendering Patterns

This document catalogs existing patterns in EdgarTools for financial statement rendering, processing, section identification, and hierarchy management.

---

## Pattern 1: Line Item Ordering and Processing

### Pattern Overview
Line items in financial statements are processed in a depth-first traversal of the presentation tree. The traversal follows parent-child relationships defined in the XBRL presentation linkbase, with children sorted by their order attribute.

### Examples Found

#### Example 1: Recursive Tree Traversal with Ordering
**File**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/xbrl.py:662-1003`

```python
def _generate_line_items(self, element_id: str, nodes: Dict[str, PresentationNode],
                         result: List[Dict[str, Any]], period_filter: Optional[str] = None,
                         path: List[str] = None, should_display_dimensions: bool = False) -> None:
    """
    Recursively generate line items for a statement.
    """
    if element_id not in nodes:
        return

    # ... build current line item ...
    result.append(line_item)

    # Process children in order (KEY PATTERN)
    for child_id in node.children:
        self._generate_line_items(child_id, nodes, result, period_filter, current_path, should_display_dimensions)
```

**Location**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/xbrl.py:1001-1002`

#### Example 2: Presentation Tree Building with Ordering
**File**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/parsers/presentation.py:139-250`

```python
def _build_presentation_subtree(self, element_id: str, parent_id: Optional[str], depth: int,
                               from_map: Dict[str, List[Dict[str, Any]]],
                               all_nodes: Dict[str, PresentationNode]) -> None:
    """
    Recursively build a presentation subtree.
    """
    # Create node with depth tracking
    node = PresentationNode(
        element_id=element_id,
        parent=parent_id,
        children=[],
        depth=depth  # ORDERING BY HIERARCHY DEPTH
    )

    # Process children
    if element_id in from_map:
        # Sort children by order (EXPLICIT ORDERING)
        children = sorted(from_map[element_id], key=lambda r: r['order'])

        for rel in children:
            child_id = rel['to_element']

            # Add child to parent's children list
            node.children.append(child_id)

            # Recursively build child subtree with incremented depth
            self._build_presentation_subtree(
                child_id, element_id, depth + 1, from_map, all_nodes
            )
```

**Location**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/parsers/presentation.py:184-243`

#### Example 3: Statement Data Structure with Ordering Info
**File**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/xbrl.py:854-892`

```python
line_item = {
    'concept': element_id,
    'name': node.element_name,
    'label': label,
    'values': values,
    'level': node.depth,  # HIERARCHY LEVEL STORED HERE
    'preferred_label': node.preferred_label,
    'is_abstract': node.is_abstract,
    'children': node.children,  # CHILD ORDERING PRESERVED
    'has_values': len(values) > 0
}
```

**Location**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/xbrl.py:874-892`

### Pattern Variations
- **Depth-First Traversal**: Used in `_generate_line_items()` - processes parent, then all children recursively
- **Order-Based Sorting**: Applied in presentation tree building - sorts children by 'order' attribute before recursion
- **Depth Tracking**: Each node stores `depth` (hierarchy level) which increments as traversal goes deeper
- **Dimension Handling**: Dimensional items get `level: node.depth + 1` to nest them under parent (line 988)

### Usage Locations
- `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/xbrl.py:1001-1002` - Recursive iteration through children
- `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/parsers/presentation.py:229` - Sorting children by order
- `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/models.py` - PresentationNode definition
- `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:1528-1641` - Rendering loop through items

### Pattern Context
- **Typically used when**: Building financial statement line item lists from presentation tree structure
- **Often combined with**: Abstract item detection, dimension filtering, fact value lookups
- **Common parameters**: `element_id`, `node.children`, `depth`, `level`, `order` attribute

---

## Pattern 2: Section Identification and Hierarchy Levels

### Pattern Overview
Sections in financial statements are identified by their hierarchy level (depth in presentation tree). Top-level sections (like ASSETS, LIABILITIES) are at level 0, subsections (like Current Assets) are at level 1, and line items are at level 2+.

### Examples Found

#### Example 1: Section Styling by Level in Rendering
**File**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:273-290`

```python
for row in self.rows:
    # Format the label based on level and properties with professional colors
    indent = "  " * row.level

    if row.is_abstract:
        if row.level == 0:
            # Top-level header - major sections like ASSETS, LIABILITIES
            label_text = row.label.upper()
            style = styles['header']['top_level']
            styled_label = Text(label_text, style=style) if style else Text(label_text)
        elif row.level == 1:
            # Section header - subtotals like Current assets
            label_text = row.label
            style = styles['header']['section']
            styled_label = Text(label_text, style=style) if style else Text(label_text)
        else:
            # Sub-section header - indented, bold
            sub_indent = "  " * (row.level - 1)
            label_text = f"{sub_indent}{row.label}"
            style = styles['header']['subsection']
            styled_label = Text(label_text, style=style) if style else Text(label_text)
```

**Location**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:273-290`

#### Example 2: Hierarchy Structure Definitions
**File**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:54-85`

```python
def get_xbrl_styles():
    """Get XBRL rendering styles based on current color scheme."""
    colors = get_xbrl_color_scheme()

    return {
        'header': {
            'company_name': colors['company_name'],
            'statement_title': colors['statement_type'],
            'top_level': colors['abstract_item'],  # Major sections like ASSETS, LIABILITIES
            'section': colors['total_item'],       # Subtotals like Current assets
            'subsection': colors['regular_item']   # Regular line items
        },
        # ... more styles ...
    }
```

**Location**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:54-85`

#### Example 3: Presentation Tree Depth Tracking
**File**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/parsers/presentation.py:177-179`

```python
# Build tree recursively
for root_id in root_elements:
    self._build_presentation_subtree(root_id, None, 0, from_map, tree.all_nodes)
```

Starting from depth 0, each recursive call increments: `depth + 1` at line 242.

**Location**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/parsers/presentation.py:177-243`

### Pattern Variations
- **Level 0**: Top-level abstract items (ASSETS, LIABILITIES, STOCKHOLDERS' EQUITY)
- **Level 1**: Section subtotals (Current Assets, Noncurrent Assets, Current Liabilities, etc.)
- **Level 2+**: Line items and sub-items
- **Dimension Items**: Get `level: node.depth + 1` to nest under parent (line 988 in xbrl.py)

### Usage Locations
- `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:274-290` - Level-based styling logic
- `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:62-64` - Style category definitions
- `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/xbrl.py:866-887` - Level storage in line items
- `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/parsers/presentation.py:242` - Depth incrementation
- Total: 10+ files reference hierarchy levels

### Pattern Context
- **Typically used when**: Rendering statements with proper indentation and styling
- **Often combined with**: Abstract item detection, styling application, indentation calculation
- **Common parameters**: `row.level`, `row.is_abstract`, `indent = "  " * row.level`

---

## Pattern 3: Abstract Item Detection and Section Headers

### Pattern Overview
Abstract items (section headers) are identified through multiple mechanisms: a `is_abstract` flag on nodes, the presence of children without values, and pattern-based concept name detection. Abstract items at different hierarchy levels are treated differently.

### Examples Found

#### Example 1: Abstract Detection in Presentation Parser
**File**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/parsers/presentation.py:211-219`

```python
# Add element information if available
if element_id in self.element_catalog:
    elem_info = self.element_catalog[element_id]
    node.element_name = elem_info.name
    node.standard_label = elem_info.labels.get('http://www.xbrl.org/2003/role/label', elem_info.name)

    # Use enhanced abstract detection (Issue #450 fix)
    # The element catalog may not have correct abstract info for standard taxonomy concepts
    from edgar.xbrl.abstract_detection import is_abstract_concept
    node.is_abstract = is_abstract_concept(
        concept_name=elem_info.name,
        schema_abstract=elem_info.abstract,
        has_children=False,  # Will be updated after children are processed
        has_values=False     # Will be determined later when facts are loaded
    )
```

**Location**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/parsers/presentation.py:211-219`

#### Example 2: Abstract Item Filtering in Statement Rendering
**File**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:1528-1548`

```python
# Process and add rows
for _index, item in enumerate(statement_data):
    # Skip rows with no values if they're abstract (headers without data)
    # But keep abstract items with children (section headers)
    has_children = len(item.get('children', [])) > 0 or item.get('has_dimension_children', False)
    if not item.get('has_values', False) and item.get('is_abstract') and not has_children:
        continue  # Skip truly empty abstract items

    # Skip axis/dimension items (they contain brackets in their labels OR concept ends with these suffixes)
    # Issue #450: Also filter based on concept name to catch dimensional members without bracket labels
    concept = item.get('concept', '')
    if any(bracket in item['label'] for bracket in ['[Axis]', '[Domain]', '[Member]', '[Line Items]', '[Table]', '[Abstract]']):
        continue
    if any(concept.endswith(suffix) for suffix in ['Axis', 'Domain', 'Member', 'LineItems', 'Table']):
        # Issue #450: For Statement of Equity, Members are always structural (column headers), never data
        if statement_type == 'StatementOfEquity':
            continue
        # Issue #416: For dimensional displays, keep Members even without values (they're category headers)
        # For non-dimensional displays, only filter if no values
        if not has_dimensional_display and not item.get('has_values', False):
            continue
```

**Location**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:1528-1548`

#### Example 3: Line Item Structure with Abstract Flag
**File**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/xbrl.py:874-892`

```python
line_item = {
    'concept': element_id,
    'name': node.element_name,
    'label': label,
    'values': values,
    'level': node.depth,
    'preferred_label': node.preferred_label,
    'is_abstract': node.is_abstract,  # ABSTRACT FLAG SET HERE
    'children': node.children,
    'has_values': len(values) > 0,  # Flag to indicate if we found values
    'has_dimension_children': item.get('has_dimension_children', False)
}
```

**Location**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/xbrl.py:889`

#### Example 4: Abstract Item Rendering Logic
**File**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:1582-1585`

```python
row = StatementRow(
    label=label,
    level=level,
    cells=[],
    metadata={...},
    is_abstract=item.get('is_abstract', False),  # PASS TO RENDERING ROW
    is_dimension=item.get('is_dimension', False),
    has_dimension_children=item.get('has_dimension_children', False)
)
```

**Location**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:1582`

### Pattern Variations
- **Schema-Based Detection**: Uses element catalog's `abstract` attribute
- **Enhanced Detection**: Uses `is_abstract_concept()` function that combines schema info with hierarchy analysis
- **Content-Based Filtering**: Skips abstract items with no children and no values (section headers without data)
- **Bracket-Based Filtering**: Skips items with `[Axis]`, `[Domain]`, `[Member]` in label or concept name
- **Dimensional Handling**: For dimensional displays, keeps Member items even without values (they're category headers)

### Usage Locations
- `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/abstract_detection.py` - Abstract detection logic
- `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/parsers/presentation.py:211-219` - Detection during parsing
- `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/xbrl.py:889` - Storage in line items
- `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:1528-1548` - Filtering during rendering
- `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:1582` - Passing to rendering rows
- `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:273-302` - Styling based on abstract flag
- Total: 8+ files reference abstract detection

### Pattern Context
- **Typically used when**: Identifying section headers vs. line items in financial statements
- **Often combined with**: Hierarchy level detection, children/parent relationships, value existence checks
- **Common parameters**: `is_abstract`, `has_children`, `has_values`, `label` patterns

---

## Pattern 4: Backwards/Reverse Iteration and State of Equity

### Pattern Overview
For Statement of Equity specifically, backwards iteration is used to match instant facts at appropriate dates. When duration periods have facts at both beginning and ending balance positions, the code tries to find matching instant facts by:
1. For beginning balance (first occurrence): try instant at day before period start
2. For ending balance (later occurrences): try instant at period end date

### Examples Found

#### Example 1: Concept Occurrence Tracking
**File**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:1514-1521`

```python
# Issue #450: For Statement of Equity, track concept occurrences to determine beginning vs ending balances
concept_occurrence_count = {}
if statement_type == 'StatementOfEquity':
    for item in statement_data:
        concept = item.get('concept', '')
        if concept:
            concept_occurrence_count[concept] = concept_occurrence_count.get(concept, 0) + 1
```

**Location**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:1514-1521`

#### Example 2: Tracking Current Occurrence Index
**File**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:1522-1551`

```python
concept_current_index = {}

# ... later in loop ...

# Track which occurrence of this concept we're on
if concept:
    concept_current_index[concept] = concept_current_index.get(concept, 0) + 1

# Issue #450: For Statement of Equity, add "Beginning balance" / "Ending balance"
# to labels when concept appears multiple times (e.g., Total Stockholders' Equity)
if statement_type == 'StatementOfEquity' and concept:
    total_occurrences = concept_occurrence_count.get(concept, 1)
    current_occurrence = concept_current_index.get(concept, 1)

    if total_occurrences > 1:
        if current_occurrence == 1:
            label = f"{label} - Beginning balance"
        elif current_occurrence == total_occurrences:
            label = f"{label} - Ending balance"
```

**Location**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:1549-1568`

#### Example 3: Backwards Date Matching for Instant Facts
**File**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:1592-1613`

```python
# Issue #450: For Statement of Equity with duration periods, match instant facts
# at the appropriate date based on position in roll-forward structure
if value == "" and period.end_date and statement_type == 'StatementOfEquity':
    # Determine if this is beginning balance (first occurrence) or ending balance (later occurrences)
    is_first_occurrence = concept_current_index.get(concept, 1) == 1

    if is_first_occurrence and hasattr(period, 'start_date') and period.start_date:
        # Beginning balance: Try instant at day before start_date (BACKWARDS LOOKUP)
        from datetime import datetime, timedelta
        try:
            start_dt = datetime.strptime(period.start_date, '%Y-%m-%d')
            beginning_date = (start_dt - timedelta(days=1)).strftime('%Y-%m-%d')
            instant_key = f"instant_{beginning_date}"
            value = item['values'].get(instant_key, "")
        except (ValueError, AttributeError):
            pass  # Fall through to try end_date

    # If still no value, try instant at end_date (FORWARD LOOKUP)
    if value == "":
        instant_key = f"instant_{period.end_date}"
        value = item['values'].get(instant_key, "")
```

**Location**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:1592-1613`

### Pattern Variations
- **Occurrence Counting**: Uses dictionary `concept_occurrence_count` to track how many times each concept appears
- **Index Tracking**: Uses `concept_current_index` to track which occurrence we're processing
- **Date Math**: Subtracts one day from period start for beginning balance (backwards in time)
- **Fallback Logic**: Falls back to period end date if beginning date lookup fails
- **Period Type Specific**: Only applies to Statement of Equity (hardcoded check at line 1516)

### Usage Locations
- `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:1514-1613` - Complete backwards iteration logic for Statement of Equity
- Related issue: Issue #450 (multiple occurrences of same concept in Statement of Equity)

### Pattern Context
- **Typically used when**: Processing Statement of Equity with duration periods and multiple occurrences of same concept
- **Often combined with**: Concept counting, occurrence tracking, date parsing, period matching
- **Common parameters**: `concept_occurrence_count`, `concept_current_index`, `period.start_date`, `period.end_date`, `timedelta(days=1)`

---

## Pattern 5: Period Selection and Data Density

### Pattern Overview
Periods are filtered and selected based on data availability and density. The code checks which periods have meaningful financial data before including them in rendered statements, using both fact counts and density scores.

### Examples Found

#### Example 1: Empty Period Filtering
**File**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:1176-1225`

```python
def _filter_empty_string_periods(statement_data: List[Dict[str, Any]],
                                 periods_to_display: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """
    Filter out periods that contain only empty strings in their values.

    This addresses Issue #408 specifically - periods that have facts but only empty string values.
    """
    if not statement_data or not periods_to_display:
        return periods_to_display

    filtered_periods = []

    for period_key, period_label in periods_to_display:
        has_meaningful_value = False

        # Check all statement items for this period
        for item in statement_data:
            values = item.get('values', {})
            value = values.get(period_key)

            if value is not None:
                # Convert to string and check if it's meaningful
                str_value = str(value).strip()
                # Check for actual content (not just empty strings)
                if str_value and str_value.lower() not in ['', 'nan', 'none']:
                    # Try to parse as numeric - if successful, it's meaningful
                    try:
                        numeric_value = pd.to_numeric(str_value, errors='coerce')
                        if not pd.isna(numeric_value):
                            has_meaningful_value = True
                            break
                    except Exception:
                        # If not numeric but has content, still count as meaningful
                        if len(str_value) > 0:
                            has_meaningful_value = True
                            break

        # Only include periods that have at least some meaningful values
        if has_meaningful_value:
            filtered_periods.append((period_key, period_label))

    return filtered_periods
```

**Location**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:1176-1225`

#### Example 2: Period Data Density Calculation
**File**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:1431-1462`

```python
# Count non-empty values for each period
for item in statement_data:
    # Skip abstract items as they typically don't have values
    if item.get('is_abstract', False):
        continue

    # Skip items with brackets in labels (usually axis/dimension items)
    if any(bracket in item['label'] for bracket in ['[Axis]', '[Domain]', '[Member]', '[Line Items]', '[Table]', '[Abstract]']):
        continue

    for period_key, _ in formatted_periods:
        # Count this item for the period
        period_item_counts[period_key] += 1

        # Check if it has a value
        value = item['values'].get(period_key)
        if value not in (None, "", 0):  # Consider 0 as a value for financial statements
            period_value_counts[period_key] += 1

# Calculate percentage of non-empty values for each period
for metadata in period_metadatas:
    period_key = metadata['key']
    count = period_item_counts.get(period_key, 0)
    if count > 0:
        data_density = period_value_counts.get(period_key, 0) / count
    else:
        data_density = 0

    metadata['data_density'] = data_density
    metadata['num_values'] = period_value_counts.get(period_key, 0)
    metadata['total_items'] = count
```

**Location**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:1431-1462`

### Pattern Variations
- **Empty Value Filtering**: Filters out periods with only empty strings (Issue #408)
- **Numeric Parsing**: Uses `pd.to_numeric()` to identify meaningful numeric values
- **Density Scoring**: Calculates `data_density = non_empty_values / total_items`
- **Abstract Item Skipping**: Skips abstract items when counting values (they don't have values)
- **Bracket-Based Filtering**: Skips dimensional axis items when counting

### Usage Locations
- `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:1176-1225` - Empty period filtering
- `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:1258-1261` - Application to all major statement types
- `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:1431-1462` - Period density calculation
- Related issue: Issue #408 (empty periods)

### Pattern Context
- **Typically used when**: Rendering financial statements with multiple periods
- **Often combined with**: Period selection logic, fact counting, rendering pipeline
- **Common parameters**: `period_key`, `period_label`, `data_density`, `num_values`, `total_items`

---

## Pattern 6: Statement Type Determination and Canonical Types

### Pattern Overview
Statement types are resolved using a multi-layered approach in statement_resolver.py. Standard statement types (BalanceSheet, IncomeStatement, etc.) are mapped to their registry entries which contain primary concepts, alternative concepts, role patterns, and key concepts for matching.

### Examples Found

#### Example 1: Statement Registry with Sections Mapped
**File**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/statement_resolver.py:90-117`

```python
statement_registry = {
    "BalanceSheet": StatementType(
        name="BalanceSheet",
        category=StatementCategory.FINANCIAL_STATEMENT,
        primary_concepts=["us-gaap_StatementOfFinancialPositionAbstract"],
        alternative_concepts=[
            "us-gaap_BalanceSheetAbstract",
            "ifrs-full_StatementOfFinancialPositionAbstract"
        ],
        concept_patterns=[
            r".*_StatementOfFinancialPositionAbstract$",
            r".*_BalanceSheetAbstract$",
            r".*_ConsolidatedBalanceSheetsAbstract$",
            r".*_CondensedConsolidatedBalanceSheetsUnauditedAbstract$"
        ],
        key_concepts=[
            "us-gaap_Assets", "us-gaap_Liabilities", "us-gaap_StockholdersEquity",
            "ifrs-full_Assets", "ifrs-full_Liabilities", "ifrs-full_Equity"
        ],
        role_patterns=[
            r".*[Bb]alance[Ss]heet.*",
            r".*[Ss]tatement[Oo]f[Ff]inancial[Pp]osition.*",
            r".*StatementConsolidatedBalanceSheets.*"
        ],
        title="Consolidated Balance Sheets",
        supports_parenthetical=True,
        weight_map={"assets": 0.3, "liabilities": 0.3, "equity": 0.4}
    ),
    # ... more statement types ...
}
```

**Location**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/statement_resolver.py:90-117`

#### Example 2: Statement Type Matching by Primary Concepts
**File**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/statement_resolver.py:395-441`

```python
def _match_by_primary_concept(self, statement_type: str, is_parenthetical: bool = False) -> Tuple[List[Dict[str, Any]], Optional[str], float]:
    """
    Match statements using primary concept names.
    """
    # Check if this is a known statement type
    if registry_type not in statement_registry:
        return [], None, 0.0

    # Get registry information
    registry_entry = statement_registry[registry_type]

    # Try to match by primary concepts
    matched_statements = []

    for concept in registry_entry.primary_concepts + registry_entry.alternative_concepts:
        if concept in self._statement_by_primary_concept:
            for stmt in self._statement_by_primary_concept[concept]:
                # Handle parenthetical check
                if registry_entry.supports_parenthetical:
                    role_def = stmt.get('definition', '').lower()
                    is_role_parenthetical = 'parenthetical' in role_def

                    # Skip if parenthetical status doesn't match
                    if is_parenthetical != is_role_parenthetical:
                        continue

                matched_statements.append(stmt)

    # If we found matching statements, return with high confidence
    if matched_statements:
        return matched_statements, matched_statements[0]['role'], 0.9

    return [], None, 0.0
```

**Location**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/statement_resolver.py:395-441`

### Pattern Variations
- **Primary Concept Matching**: Looks for exact primary concepts first (high confidence: 0.9)
- **Alternative Concepts**: Falls back to alternative concepts if primary not found
- **Pattern Matching**: Uses regex patterns on concept names for custom namespaces (confidence: 0.85)
- **Role Pattern Matching**: Matches role URIs and role names against patterns (confidence: 0.75)
- **Content-Based Analysis**: Scores statements by presence of key concepts (confidence: 0.6-0.85)
- **Parenthetical Filtering**: Filters for/against parenthetical versions based on role definition

### Usage Locations
- `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/statement_resolver.py:90-303` - Statement registry definition
- `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/statement_resolver.py:395-441` - Primary concept matching
- `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/statement_resolver.py:725-876` - Multi-layered find_statement logic
- `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/statements.py:574-594` - get_raw_data usage
- Total: 5+ files implement statement type resolution

### Pattern Context
- **Typically used when**: Resolving a statement type to an actual XBRL role
- **Often combined with**: Canonical type preservation, statement rendering
- **Common parameters**: `statement_type`, `is_parenthetical`, `registry_entry`, confidence scores

---

## Pattern 7: Standardized Label Mapping

### Pattern Overview
Financial statement concepts are mapped to standardized labels using a ConceptMapper. This allows consistent labeling across different companies that use different XBRL taxonomies. Standardized concepts like "Total Current Assets" are predefined and applied during rendering.

### Examples Found

#### Example 1: Standardized Concept Names
**File**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/standardization/core.py:25-50`

```python
@dataclass
class StandardizedConcepts:
    """Standard concept labels for balance sheet items"""

    # Section headers
    TOTAL_ASSETS = "Total Assets"
    CURRENT_ASSETS = "Current Assets"
    TOTAL_CURRENT_ASSETS = "Total Current Assets"
    NONCURRENT_ASSETS = "Noncurrent Assets"

    TOTAL_LIABILITIES = "Total Liabilities"
    CURRENT_LIABILITIES = "Current Liabilities"
    TOTAL_CURRENT_LIABILITIES = "Total Current Liabilities"
    NONCURRENT_LIABILITIES = "Noncurrent Liabilities"

    STOCKHOLDERS_EQUITY = "Stockholders' Equity"
```

**Location**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/standardization/core.py:25-50`

#### Example 2: Standardization Application During Rendering
**File**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:1263-1310`

```python
# Apply standardization if requested
if standard:
    # Create a concept mapper with default mappings
    mapper = standardization.ConceptMapper(standardization.initialize_default_mappings())

    # Add statement type to context for better mapping
    for item in statement_data:
        item['statement_type'] = statement_type

    # Standardize the statement data
    statement_data = standardization.standardize_statement(statement_data, mapper)

    # Update facts with standardized labels if XBRL instance is available
    entity_xbrl_instance = entity_info.get('xbrl_instance')
    # Use passed xbrl_instance or fall back to entity info
    facts_xbrl_instance = xbrl_instance or entity_xbrl_instance
    if facts_xbrl_instance and hasattr(facts_xbrl_instance, 'facts_view'):
        facts_view = facts_xbrl_instance.facts_view
        facts = facts_view.get_facts()

        # Create a mapping of concept -> standardized label from statement data
        standardization_map = {}
        for item in statement_data:
            if 'concept' in item and 'label' in item and 'original_label' in item:
                if item.get('is_dimension', False):
                    continue
                standardization_map[item['concept']] = {
                    'label': item['label'],
                    'original_label': item['original_label']
                }

    # Indicate that standardization is being used in the title
    statement_title = f"{statement_title} (Standardized)"
```

**Location**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:1263-1310`

### Pattern Variations
- **Predefined Mappings**: Uses `initialize_default_mappings()` to load standard concept mappings
- **Statement Type Aware**: Adds `statement_type` to items for context-specific mapping
- **Dimension Skipping**: Skips dimension items when applying standardization
- **Title Marking**: Appends "(Standardized)" to statement title when applied

### Usage Locations
- `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/standardization/core.py:25-50` - Standardized concept definitions
- `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:1263-1310` - Standardization application
- `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/standardization/` - Full standardization module

### Pattern Context
- **Typically used when**: Rendering statements with `standard=True` parameter
- **Often combined with**: Statement rendering, concept mapping, label updates
- **Common parameters**: `mapper`, `ConceptMapper`, `standardize_statement()`, `statement_type`

---

## Summary of Key Patterns

### Data Flow Pattern
```
Presentation Tree (ordered by hierarchy)
    ↓ (traverse depth-first with order sorting)
Line Items List (with level, abstract flag, children)
    ↓ (apply filtering, abstract detection, period filtering)
Rendered Statement Data
    ↓ (apply styling based on level, apply standardization)
Rich Table Output
```

### Section Identification Pattern
```
Level 0: Top-level abstract (ASSETS, LIABILITIES, EQUITY)
    ↓
Level 1: Section headers (Current Assets, Noncurrent Assets)
    ↓
Level 2+: Line items (Cash, Accounts Receivable)
    ↓
Level n+1: Dimension items (if dimensional display enabled)
```

### Processing Pattern
```
For each role (presentation tree):
    1. Build tree recursively with depth tracking
    2. Find root elements (appear as 'from' but not 'to')
    3. Sort children by 'order' attribute
    4. Generate line items depth-first
    5. Track concept occurrences (for Statement of Equity)
    6. Filter empty periods
    7. Apply standardization
    8. Render with level-based styling
```

### Statement Type Resolution Pattern
```
1. Try standard name matching (confidence: 0.95)
    ↓
2. Try primary concept matching (confidence: 0.9)
    ↓
3. Try custom namespace pattern matching (confidence: 0.85)
    ↓
4. Try role pattern matching (confidence: 0.75)
    ↓
5. Try content-based analysis (confidence: 0.6-0.85)
    ↓
6. Try role definition matching (confidence: 0.5-0.65)
    ↓
7. Make best guess or raise StatementNotFound
```

---

## File References

### Core Implementation Files
- **Presentation Tree Building**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/parsers/presentation.py:139-250`
- **Line Item Generation**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/xbrl.py:612-1003`
- **Statement Rendering**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:1227-1643`
- **Statement Resolution**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/statement_resolver.py:89-876`
- **Standardization**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/standardization/core.py`

### Related Files
- **Models**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/models.py` (PresentationNode, PresentationTree definitions)
- **Statements**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/statements.py` (Statement class)
- **Abstract Detection**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/abstract_detection.py`
- **Rendering Dataclasses**: `/Users/dwight/PycharmProjects/edgartools/edgar/xbrl/rendering.py:162-220` (StatementCell, StatementRow, etc.)

---

## Key Design Decisions

1. **Recursive Depth-First Traversal**: Line items are processed recursively following the presentation tree structure, preserving parent-child relationships and order
2. **Level-Based Hierarchy**: Depth in tree determines styling and indentation; level 0 = top sections, level 1 = subsections
3. **Abstract Item Distinction**: Section headers are marked with `is_abstract=True` flag and distinguished from regular line items
4. **Statement of Equity Special Handling**: Uses occurrence counting and date math for beginning/ending balance matching
5. **Multi-Layered Type Resolution**: Flexible statement type matching using concepts, patterns, roles, and content analysis
6. **Standardization Layer**: Optional concept label standardization applied after rendering pipeline
7. **Period Filtering**: Empty periods are removed; data density is calculated per period

