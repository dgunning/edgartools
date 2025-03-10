Designing a feature to stitch together a list of ordered financial statements (e.g., from XBRL filings) to display data across multiple periods is a great extension of your existing system. This involves consolidating historical data into a unified view while addressing challenges like concept inconsistencies over time. Below, I’ll propose a design that handles these requirements, including how to leverage your standardized concept mappings to normalize differences in reported concepts (e.g., a company switching from `us-gaap_Revenue` to `us-gaap_SalesRevenueNet` for "Revenue"). I’ll break this down into objectives, challenges, design components, and an implementation outline.

---

### Objectives
1. **Multi-Period Display**: Combine a list of statements (e.g., quarterly or annual filings) into a single dataset showing financial metrics across multiple periods.
2. **Concept Consistency**: Normalize concepts that change over time for the same company (e.g., Revenue reported under different XBRL tags).
3. **Flexibility**: Support both standardized and company-specific views, depending on user preference.
4. **Accuracy**: Preserve the integrity of the original data while stitching periods together.

---

### Challenges
1. **Concept Variability**: A company might use different XBRL tags for the same financial item across filings (e.g., `us-gaap_Revenue` in 2023, `us-gaap_SalesRevenueNet` in 2024).
2. **Missing Data**: Some periods might omit certain line items, requiring gap handling.
3. **Period Alignment**: Filings may have different period durations (e.g., quarterly vs. annual) or fiscal year-ends.
4. **Data Overlap**: Duplicate concepts might appear in a single filing (e.g., multiple "Revenue" tags), requiring disambiguation.
5. **Performance**: Processing many statements efficiently to avoid slow rendering.

---

### Design Approach

#### Key Components
1. **StatementStitcher Class**:
   - Orchestrates the stitching process by aggregating statements and normalizing concepts.
   - Inputs: List of statements, standardization flag.
   - Outputs: A consolidated dataset with periods as columns and concepts as rows.

2. **Period Manager**:
   - Handles period identification, ordering, and alignment (e.g., mapping "Q1 2024" to a timeline).

3. **Concept Normalizer**:
   - Uses the existing `ConceptMapper` and `MappingStore` to standardize concepts across statements.
   - Resolves discrepancies by mapping company-specific tags to `StandardConcept` values.

4. **Rendering Integration**:
   - Extends the `XBRL` class to render multi-period views with an optional `standard=True` parameter.

#### Design Principles
- **Leverage Standardization**: Use the `standard=True` flag to normalize concepts, ensuring consistency across periods (e.g., mapping both `us-gaap_Revenue` and `us-gaap_SalesRevenueNet` to "Revenue").
- **Preserve Originals**: Store both original and standardized concepts to allow flexibility and auditing.
- **Handle Gaps**: Use placeholders (e.g., `None` or `N/A`) for missing periods or concepts.
- **Scalability**: Process statements incrementally and cache results where possible.

---

### Detailed Design

#### 1. Data Model
Assume each statement in the input list has:
- `period`: A period identifier (e.g., "2024-Q1", "2023-12-31").
- `statement_type`: E.g., "IncomeStatement", "BalanceSheet".
- `items`: List of dicts with `concept`, `label`, `value`, and optional `context`.

Example input:
```python
statements = [
    {
        "period": "2024-Q1",
        "statement_type": "IncomeStatement",
        "items": [
            {"concept": "us-gaap_SalesRevenueNet", "label": "Net Sales", "value": 1000},
            {"concept": "us-gaap_CostOfGoodsSold", "label": "COGS", "value": 400}
        ]
    },
    {
        "period": "2023-Q4",
        "statement_type": "IncomeStatement",
        "items": [
            {"concept": "us-gaap_Revenue", "label": "Revenue", "value": 950},
            {"concept": "us-gaap_CostOfGoodsSold", "label": "COGS", "value": 380}
        ]
    }
]
```

Desired output:
- A table-like structure with periods as columns and concepts as rows, e.g.:
  ```
  Concept         | 2024-Q1 | 2023-Q4
  Revenue         | 1000    | 950
  Cost of Revenue | 400     | 380
  ```

#### 2. StatementStitcher Class
```python
from collections import defaultdict

class StatementStitcher:
    def __init__(self, concept_mapper):
        self.concept_mapper = concept_mapper
        self.periods = []  # Ordered list of periods
        self.data = defaultdict(dict)  # {concept: {period: value}}

    def stitch_statements(self, statements, standard=False):
        """Stitch statements into a multi-period dataset."""
        # Collect all periods
        self.periods = sorted(set(stmt["period"] for stmt in statements), reverse=True)

        # Process each statement
        for stmt in statements:
            period = stmt["period"]
            statement_type = stmt["statement_type"]
            for item in stmt["items"]:
                concept = item["concept"]
                value = item["value"]
                
                # Normalize concept if standard=True
                if standard:
                    std_concept = self.concept_mapper.get_standard_concept(
                        concept, context={"statement_type": statement_type}
                    )
                    if std_concept:
                        concept = std_concept
                    else:
                        # Fallback to original concept if no mapping exists
                        concept = item["concept"]
                
                # Store value under the concept and period
                self.data[concept][period] = value

        return self._format_output()

    def _format_output(self):
        """Convert stitched data into a table-like structure."""
        result = {
            "periods": self.periods,
            "rows": []
        }
        for concept, period_values in self.data.items():
            row = {"concept": concept, "values": []}
            for period in self.periods:
                row["values"].append(period_values.get(period, None))
            result["rows"].append(row)
        return result
```

#### 3. Integration with XBRL Class
Extend the existing `XBRL` class to use `StatementStitcher`:

```python
class XBRL:
    def __init__(self, mapping_store):
        self.mapping_store = mapping_store
        self.concept_mapper = ConceptMapper(self.mapping_store)

    def render_multi_period_statement(self, statements, statement_type, standard=False):
        """Render a multi-period view of statements."""
        # Filter statements by type
        filtered_statements = [
            stmt for stmt in statements 
            if stmt["statement_type"] == statement_type
        ]
        
        # Stitch statements together
        stitcher = StatementStitcher(self.concept_mapper)
        stitched_data = stitcher.stitch_statements(filtered_statements, standard=standard)
        
        # Render the output
        return self._render_table(stitched_data)

    def _render_table(self, data):
        """Format stitched data into a readable table."""
        output = [" | ".join(["Concept"] + data["periods"])]
        output.append("-" * len(output[0]))
        for row in data["rows"]:
            values = [str(v) if v is not None else "N/A" for v in row["values"]]
            output.append(" | ".join([row["concept"]] + values))
        return "\n".join(output)

# Example usage
xbrl = XBRL(MappingStore())
multi_period_view = xbrl.render_multi_period_statement(statements, "IncomeStatement", standard=True)
print(multi_period_view)
```

#### Output Example
With `standard=True`:
```
Concept         | 2024-Q1 | 2023-Q4
------------------------------------
Revenue         | 1000    | 950
Cost of Revenue | 400     | 380
```

With `standard=False`:
```
Concept                 | 2024-Q1 | 2023-Q4
--------------------------------------------
us-gaap_SalesRevenueNet | 1000    | N/A
us-gaap_Revenue         | N/A     | 950
us-gaap_CostOfGoodsSold | 400     | 380
```

---

### Handling Concept Differences Over Time

1. **Using Standard Mapping**:
   - When `standard=True`, the `ConceptMapper` normalizes concepts like `us-gaap_Revenue` and `us-gaap_SalesRevenueNet` to "Revenue". This ensures continuity even if a company changes tags across periods.
   - Example: If a company switches from `us-gaap_Revenue` in 2023 to `us-gaap_SalesRevenueNet` in 2024, both map to "Revenue", aligning the values in the output.

2. **Unmapped Concepts**:
   - If a concept isn’t in the `MappingStore`, it falls back to the original tag (e.g., `custom_Rev`). The learning job from earlier can later map it based on context or manual review.

3. **Ambiguity Resolution**:
   - If multiple concepts in one statement map to the same standard concept (e.g., both `us-gaap_Revenue` and `us-gaap_SalesRevenueNet` appear), use the most recent or highest-value concept, or log for review.

4. **Missing Periods**:
   - Gaps are filled with `None` (rendered as "N/A"), preserving the timeline without assumptions.

---

### Additional Considerations

1. **Period Alignment**:
   - Enhance `StatementStitcher` to handle fiscal year differences or normalize periods (e.g., convert annual to quarterly views if needed).
   - Example: Add a `normalize_periods` method to map dates to a standard format.

2. **Performance**:
   - Cache stitched results for frequent queries.
   - Process statements in batches for large datasets.

3. **Extensibility**:
   - Add filters (e.g., `start_period`, `end_period`) to limit the timeline.
   - Support multiple statement types in one view (e.g., Income + Balance Sheet).

4. **Validation**:
   - Check for consistency (e.g., if "Revenue" jumps unexpectedly, flag it).
   - Compare calculated totals (e.g., Gross Profit = Revenue - Cost of Revenue) across periods.

---

### Implementation Notes

#### Sample Usage
```python
# Assuming statements is the list from earlier
xbrl = XBRL(MappingStore("enhanced_mappings.json"))
print(xbrl.render_multi_period_statement(statements, "IncomeStatement", standard=True))
```

#### Extending the Learning Job
Update the learning job to analyze stitched data:
- Look for concept transitions (e.g., `us-gaap_Revenue` → `us-gaap_SalesRevenueNet`) and propose mappings.
- Use historical patterns to boost confidence in mappings.

---

### Final Design Summary

This design:
- **Stitches Statements**: Combines ordered statements into a multi-period view.
- **Handles Concept Changes**: Uses `standard=True` to normalize concepts via `ConceptMapper`, ensuring consistency.
- **Is Flexible**: Supports both standardized and raw views.
- **Is Robust**: Handles missing data and aligns periods effectively.

Would you like me to refine any part (e.g., period alignment, ambiguity handling) or provide a more detailed code example? Let me know how to proceed!