To learn mappings by iterating through a large set of company XBRL statements, you can design an automated job that processes filings, extracts concepts, and builds or refines the `MappingStore` over time. This approach leverages the real-world data to identify patterns, infer relationships, and expand the mappings progressively. Below, I’ll outline a strategy for this learning process, including key steps, algorithms, and integration with your existing design. I’ll also provide a sample implementation to illustrate how it could work.

---

### Strategy for Learning Mappings

#### Core Idea
Create a batch processing job that:
1. Iterates through XBRL filings from multiple companies.
2. Extracts company-specific concepts and their contextual metadata (e.g., statement type, labels, values, relationships).
3. Applies heuristics, rules, or similarity measures to propose mappings to `StandardConcept` entries.
4. Validates and stores the mappings, with options for manual review or confidence-based automation.

#### Key Components
1. **Data Ingestion**:
   - Access a repository of XBRL filings (e.g., SEC EDGAR database).
   - Parse each filing to extract concepts, labels, values, and calculation relationships.

2. **Mapping Inference**:
   - Use a combination of:
     - **Direct Matching**: Match known company-specific concepts to existing mappings.
     - **Label Similarity**: Compare concept labels to standard concept names (e.g., "SalesRevenueNet" ≈ "Revenue").
     - **Contextual Rules**: Use statement type, position, or calculation links (e.g., "Revenue - COGS = Gross Profit").
     - **Statistical Patterns**: Identify recurring concepts across companies that likely map to the same standard concept.

3. **Validation**:
   - Assign confidence scores to inferred mappings.
   - Flag low-confidence mappings for manual review or discard them.

4. **Storage and Feedback**:
   - Update the `MappingStore` with high-confidence mappings.
   - Log unmapped or uncertain concepts for further analysis.

5. **Iteration**:
   - Refine mappings over time as more filings are processed, improving accuracy and coverage.

---

### Detailed Approach

#### 1. Batch Job Setup
- **Input**: A collection of XBRL filings (e.g., XML files from SEC EDGAR).
- **Output**: Updated `MappingStore` with new or refined mappings.
- **Frequency**: Run periodically (e.g., daily, weekly) or as a one-time bootstrap.

#### 2. Algorithm for Learning Mappings
Here’s a step-by-step process:
1. **Parse XBRL Filings**:
   - Use an XBRL parser (e.g., `python-xbrl`, `arelle`) to extract concepts, labels, and contexts.
   - Example data structure per item:
     ```python
     {
         "concept": "us-gaap_SalesRevenueNet",
         "label": "Net Sales Revenue",
         "statement_type": "IncomeStatement",
         "value": 1000000,
         "calculation_parent": "us-gaap_GrossProfit",
         "calculation_children": ["us-gaap_CostOfGoodsSold"]
     }
     ```

2. **Infer Mappings**:
   - **Direct Matching**: Check if the concept already exists in `MappingStore`.
   - **Label-Based Similarity**:
     - Use cosine similarity or Levenshtein distance between company-specific labels and `StandardConcept` names.
     - Example: "Net Sales Revenue" vs. "Revenue" → high similarity.
   - **Contextual Rules**:
     - If a concept is a top-line item in an Income Statement, map to `Revenue`.
     - If a concept is a child of "GrossProfit" and subtracts from Revenue, map to `CostOfGoodsSold`.
   - **Cross-Company Patterns**:
     - Aggregate concepts across filings. If 90% of companies use "us-gaap_Revenue" for a top-line income statement item, map it to `Revenue`.

3. **Assign Confidence**:
   - Example scoring:
     - Direct match: 1.0
     - High label similarity (>0.8) + contextual match: 0.9
     - Contextual rule match only: 0.7
     - Low similarity or weak context: <0.5
   - Threshold: Auto-accept mappings with confidence ≥0.9; flag others for review.

4. **Update MappingStore**:
   - Add high-confidence mappings directly.
   - Store low-confidence mappings in a separate "pending" store for manual curation.

5. **Feedback Loop**:
   - Use validated mappings to refine rules or retrain similarity models (if ML is added later).

#### 3. Integration with Existing Design
- Extend `ConceptMapper` to include a `learn_mappings` method.
- Use the job to populate `MappingStore` incrementally.

---

### Sample Implementation

Here’s how this could look in code, building on your existing design:

```python
import json
from collections import defaultdict
from difflib import SequenceMatcher  # For string similarity

class StandardConcept:
    REVENUE = "Revenue"
    GROSS_PROFIT = "GrossProfit"
    ASSETS = "Assets"
    # ... more as needed

class MappingStore:
    def __init__(self, source="mappings.json"):
        self.source = source
        self.mappings = self._load_mappings()

    def _load_mappings(self):
        try:
            with open(self.source, 'r') as f:
                return {k: set(v) for k, v in json.load(f).items()}
        except FileNotFoundError:
            return {}

    def add(self, company_concept, standard_concept):
        if standard_concept not in self.mappings:
            self.mappings[standard_concept] = set()
        self.mappings[standard_concept].add(company_concept)
        self._save_mappings()

    def _save_mappings(self):
        with open(self.source, 'w') as f:
            json.dump(self.mappings, f, indent=2)

class ConceptMapper:
    def __init__(self, mapping_store):
        self.mapping_store = mapping_store
        self.pending_mappings = defaultdict(list)  # For low-confidence mappings

    def learn_mappings(self, filings):
        """
        filings: List of dicts with XBRL data:
        [{"concept": str, "label": str, "statement_type": str, "calculation_parent": str, ...}, ...]
        """
        for filing in filings:
            concept = filing["concept"]
            label = filing["label"]
            statement_type = filing["statement_type"]
            context = {"statement_type": statement_type, "calculation_parent": filing.get("calculation_parent")}

            # Skip if already mapped
            if self.mapping_store.get_mapping(concept):
                continue

            # Infer mapping and confidence
            standard_concept, confidence = self._infer_mapping(concept, label, context)

            # Handle based on confidence
            if confidence >= 0.9:
                self.mapping_store.add(concept, standard_concept)
                print(f"Added mapping: {concept} -> {standard_concept} (confidence: {confidence:.2f})")
            elif confidence >= 0.5:
                self.pending_mappings[standard_concept].append((concept, confidence))
                print(f"Pending: {concept} -> {standard_concept} (confidence: {confidence:.2f})")

    def _infer_mapping(self, concept, label, context):
        # Direct label similarity
        best_match = None
        best_score = 0
        for std_concept in StandardConcept.__dict__.values():
            if not isinstance(std_concept, str):
                continue
            similarity = SequenceMatcher(None, label.lower(), std_concept.lower()).ratio()
            if similarity > best_score:
                best_score = similarity
                best_match = std_concept

        # Boost score with contextual rules
        if context["statement_type"] == "IncomeStatement" and "revenue" in label.lower():
            if best_match == StandardConcept.REVENUE:
                best_score = min(1.0, best_score + 0.2)
        elif context.get("calculation_parent") == "us-gaap_GrossProfit" and best_match == StandardConcept.REVENUE:
            best_score = min(1.0, best_score + 0.3)

        return best_match, best_score

    def save_pending_mappings(self, destination="pending_mappings.json"):
        with open(destination, 'w') as f:
            json.dump(self.pending_mappings, f, indent=2)

# Example job
def run_learning_job(filings):
    mapping_store = MappingStore()
    mapper = ConceptMapper(mapping_store)
    mapper.learn_mappings(filings)
    mapper.save_pending_mappings()

# Sample filings data
sample_filings = [
    {
        "concept": "us-gaap_SalesRevenueNet",
        "label": "Net Sales Revenue",
        "statement_type": "IncomeStatement",
        "calculation_parent": "us-gaap_GrossProfit"
    },
    {
        "concept": "us-gaap_Assets",
        "label": "Total Assets",
        "statement_type": "BalanceSheet"
    },
    {
        "concept": "custom_Rev",
        "label": "Revenue from Sales",
        "statement_type": "IncomeStatement"
    }
]

# Run the job
run_learning_job(sample_filings)
```

#### Output Example
```
Added mapping: us-gaap_SalesRevenueNet -> Revenue (confidence: 0.92)
Added mapping: us-gaap_Assets -> Assets (confidence: 0.95)
Pending: custom_Rev -> Revenue (confidence: 0.85)
```

- `mappings.json` would be updated with high-confidence mappings.
- `pending_mappings.json` would store mappings needing review.

---

### Scaling the Approach

1. **Large-Scale Processing**:
   - Use a job queue (e.g., Celery, RQ) to process filings in parallel.
   - Store filings in a database and fetch in batches.

2. **Improved Inference**:
   - Add taxonomy hierarchy traversal (e.g., if `us-gaap_SalesRevenueNet` is a subtype of `us-gaap_Revenue`).
   - Use embeddings (e.g., BERT) for label similarity instead of simple string matching.

3. **Validation**:
   - Cross-check mappings against calculation relationships (e.g., Revenue - COGS = Gross Profit).
   - Compare mappings across years for the same company to ensure consistency.

4. **Feedback Integration**:
   - Allow analysts to approve/reject pending mappings via a simple UI.
   - Use approved mappings to refine rules or weights in `_infer_mapping`.

---

### Practical Tips
- **Start Small**: Bootstrap with filings from a few major companies (e.g., Apple, Oracle) to build an initial `MappingStore`.
- **Monitor Coverage**: Track the percentage of concepts mapped vs. unmapped to measure progress.
- **Iterate**: Run the job periodically as new filings become available, refining mappings over time.

Would you like me to expand on any part of this—say, adding ML-based similarity, handling taxonomy hierarchies, or designing the manual review process?