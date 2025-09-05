# XBRL Parser Logic (`edgar.xbrl.parser`)

This document describes the logic behind key methods in the `XBRLParser` class, specifically focusing on instance document parsing and fact counting.

## `parse_instance_content(content)`

This method is responsible for parsing the entire XBRL instance document and extracting its core components.

1.  **Initialization:** Accepts the raw XBRL instance document content as a string or bytes.
2.  **Parser Setup:** Configures an `lxml.etree.XMLParser` optimized for:
    *   Removing insignificant whitespace (`remove_blank_text=True`).
    *   Attempting recovery from XML errors (`recover=True`).
    *   Handling potentially very large XML files (`huge_tree=True`).
3.  **Content Preparation:** Ensures the input content is in `bytes` format (UTF-8 encoding is assumed if a string is provided).
4.  **Parsing:** Uses the configured parser to parse the byte content into an `lxml` element tree (`root`).
5.  **Sequential Extraction:** Extracts data by calling internal helper methods in a specific order to handle dependencies:
    *   `_extract_contexts(root)`: Parses all `<context>` elements, capturing period, entity, and segment information.
    *   `_extract_units(root)`: Parses all `<unit>` elements, defining measures for numeric facts.
    *   `_extract_facts(root)`: Parses all fact elements (e.g., `<us-gaap:Assets>`), linking them to their corresponding contexts and units. **(See detailed section below)**
6.  **Post-processing:** Performs additional steps after the main extraction:
    *   `_extract_entity_info()`: Consolidates information about the reporting entity (CIK, name, etc.) likely derived from context elements.
    *   `_build_reporting_periods()`: Creates structured representations of the reporting periods found in the contexts.
7.  **Error Handling:** Includes a `try...except` block to catch parsing or processing errors, raising a specific `XBRLProcessingError` if issues occur.

## `_extract_facts(root)` - Fact Extraction and Storage (Current Behavior)

This method iterates through the parsed XML tree to identify and extract XBRL facts.

1.  **Namespace Handling:** Efficiently maps XML namespace URIs to prefixes (e.g., `http://fasb.org/us-gaap/2023` -> `us-gaap`).
2.  **Fact Identification:** Identifies potential fact elements by checking for a `contextRef` attribute and excluding known non-fact elements (like `<context>`, `<unit>`).
3.  **Attribute Extraction:** For each fact element, it extracts key attributes like `contextRef`, `unitRef`, `decimals`, `id`, and the element's text `value`.
4.  **Element ID Construction:** Creates a prefixed `element_id` (e.g., `us-gaap:Assets`).
5.  **Fact Storage:** Creates a `Fact` object for each identified fact element.
6.  **Key Generation:** Generates a normalized key based *only* on the fact's `element_id` (e.g., `us-gaap:Assets`) and its `contextRef`.
7.  **Overwriting Issue:** Stores the `Fact` object in the `parser.facts` dictionary using the generated key. **Crucially, if multiple fact elements share the same `element_id` and `contextRef`, subsequent facts overwrite earlier ones in the dictionary.** This means only the *last encountered* instance for a given element/context combination is retained. Attributes like `id`, `decimals`, and the specific `value` of overwritten facts are lost.
8.  **Calculation Weights:** After extracting all facts, it calls `_apply_calculation_weights` to adjust the signs of certain numeric facts based on calculation linkbase relationships.

## Duplicate Facts and Discrepancy with HTML/iXBRL Presentation

### The Issue
Filings sometimes contain multiple instances of the same conceptual fact (identical `element_id`, `contextRef`, and often `unitRef`) that differ primarily in their `decimals` attribute (specifying rounding for presentation) and their `id` attribute. The standalone XBRL instance XML file captures all these variations.

However, the HTML version of the filing (using Inline XBRL or iXBRL) often uses the `id` attribute to link a specific fact instance (with a particular `decimals` value and numeric `value`) to a specific location (e.g., a cell in a table) for display.

Because the current `_extract_facts` logic overwrites duplicates based on the `element_id`/`contextRef` key, the parser might discard the specific fact instance (and its `value`/`decimals`) that is actually displayed in the primary HTML tables, retaining a different instance instead. This can lead to `edgartools` reporting values that don't match the visual presentation of the filing.

### Proposed Solution: Store All Facts, Select by Precision

To mitigate this discrepancy without implementing a full iXBRL HTML parser, the proposed approach is:

1.  **Store All Fact Instances:** Modify `_extract_facts` to store *all* encountered `Fact` objects. Instead of `parser.facts` mapping `normalized_key` -> `Fact`, it will map `normalized_key` -> `list[Fact]`. Each fact instance found will be appended to the list associated with its key. This ensures all reported data, including differing `id` and `decimals`, is captured (the `id` should also be stored on the `Fact` object).
2.  **Select Based on Precision:** Modify the fact retrieval logic (likely in `edgar.xbrl.xbrl.py`) so that when multiple facts exist for a requested key, it selects the one with the **highest precision**. This typically corresponds to the fact with the numerically largest `decimals` value (e.g., prefer `-3` over `-5`, prefer `INF` over any finite value). If ties occur, a consistent tie-breaking rule (e.g., first encountered) will be needed.

### Concerns and Tradeoffs

*   **Pros:**
    *   Retains all reported fact data from the XML, including the `id` for potential future use.
    *   Provides the most precise reported value according to XBRL metadata.
    *   Significantly simpler than full iXBRL parsing.
*   **Cons:**
    *   **Heuristic:** This selection logic is a heuristic. It *does not guarantee* that the selected highest-precision fact is the one visually displayed in the primary HTML tables. The filer's presentation choice might prioritize a more rounded value.
    *   **Ignores `id` for Selection:** It doesn't use the `id` attribute *for selecting* the value, which is the iXBRL mechanism for linking presentation to specific facts.
*   **Outcome:** This approach aims to provide the most accurate value *based on the XML data's precision metadata*, accepting that it might still differ from the filer's chosen *presentation* value in the HTML in some cases.

## `count_facts(content)` - (Potential Redundancy)

This method efficiently counts the number of unique facts and total fact instances within an XBRL instance document without performing a full parse and object creation.

1.  **Initialization & Parsing:** Sets up an `lxml` parser and parses the content.
2.  **Counters & Filtering:** Initializes counters for unique/total facts and uses a skip list for non-fact elements.
3.  **Element Counting:** Defines an inner function to process elements:
    *   Filters non-facts and elements without `contextRef`.
    *   Generates a normalized key based on `element_id` and `contextRef`.
    *   Adds the key to a set (for unique count) and increments the total instance count.
4.  **Tree Traversal:** Iterates through the element tree, applying the counting function.
5.  **Return Value:** Returns `(unique_fact_count, total_fact_instances)`.

**Note:** With the proposed change to store all facts as lists in `_extract_facts`, the primary purpose of `count_facts` (getting unique and total counts without full parsing) becomes less critical. The total number of fact instances can be derived by summing the lengths of the lists in the modified `parser.facts` dictionary, and the unique fact count (by element/context) is simply the number of keys in that dictionary. This method might become redundant or could be repurposed.

## Fact Storage Structure (Current Implementation)

The current fact storage mechanism in the `XBRLParser` class uses a dictionary-based approach with normalized keys:

### Key Generation

Fact keys are generated in the `_create_normalized_fact_key` method using a combination of:

1. **Element ID**: The concept identifier (e.g., `us-gaap:Assets` or `dei:EntityRegistrantName`)
   - Normalized to use underscores instead of colons (e.g., `us-gaap_Assets`)  
2. **Context Reference**: The ID of the context element (e.g., `AsOf2023-12-31`)

The resulting key format is: `normalized_element_id_context_ref`

Example: `us-gaap_Assets_AsOf2023-12-31`

### Fact Storage

The facts are stored in the `self.facts` dictionary:

```python
self.facts[normalized_key] = Fact(
    element_id=element_id,
    context_ref=context_ref,
    value=value,
    unit_ref=unit_ref,
    decimals=decimals,
    numeric_value=numeric_value
)
```

### Duplicate Handling (Current Limitation)

When multiple facts share the same element ID and context reference (creating identical keys), the current implementation overwrites previous facts. Only the last encountered fact is preserved in the dictionary, as shown in the code:

```python
facts_dict[normalized_key] = Fact(...)
```

This means that if a filing contains multiple instances of the same fact with different `decimals` attributes or `id` attributes, only one will be stored, and information about the others is lost.

### Fact Retrieval

Facts are retrieved using the `get_fact` method, which creates the normalized key and performs a dictionary lookup:

```python
def get_fact(self, element_id: str, context_ref: str) -> Optional[Fact]:
    normalized_key = self._create_normalized_fact_key(element_id, context_ref)
    return self.facts.get(normalized_key)
```

### Fact Counting

The current implementation counts facts in two ways:
1. **Unique Facts**: The number of keys in the `self.facts` dictionary
2. **Total Fact Instances**: Calculated by the `count_facts` method, which may not account for overwritten duplicates

## Alternative Approaches for Handling Duplicates

Two main approaches are being considered to address the duplicate facts issue:

### 1. List-Based Approach

Store all fact instances in lists under the same key:

```python
# Key structure remains: element_id_context_ref
self.facts[normalized_key] = [fact1, fact2, ...]
```

### 2. Instance ID Approach

Incorporate the fact's instance ID into the key:

```python
# Key structure becomes: element_id_context_ref_instance_id
self.facts[f"{normalized_key}_{fact.id}"] = fact
```

### 3. Hybrid Approach (Optimized)

Optimize for the common case where there's only a single fact per element/context:

```python
# For the first fact with a given element/context
self.facts[normalized_key] = fact

# If a duplicate is encountered, convert to a dictionary
if normalized_key in self.facts:
    existing_fact = self.facts[normalized_key]
    self.facts[normalized_key] = {
        existing_fact.id: existing_fact,
        fact.id: fact
    }
```

Each approach has different implications for storage efficiency, retrieval complexity, and backward compatibility, as discussed in the proposed solutions section.
