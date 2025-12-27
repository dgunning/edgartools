# Chunking-Ready Markdown Format Proposal

## Goal
Prepare SEC filing markdown for cleaning, chunking, and embedding pipelines.

## Current Issues

### 1. Flat Heading Structure
**Current:**
```markdown
## SECTION: part_i_item_1
Item 1. Business.

Overview
Snapchat
Our Partner Ecosystem
```

**Problem:** All subsections at same level, hard to chunk hierarchically.

### 2. No Section Metadata
**Current:**
```markdown
## SECTION: Description of Business and Summary of Significant Accounting Policies
```

**Problem:** No IDs, depth info, or parent references.

### 3. Inconsistent Subsection Detection
- Items have implicit subsections (detected from bold text)
- Notes have implicit subsections (accounting topics)
- No consistent heading hierarchy

---

## Proposed Format

### 1. Hierarchical Headings

```markdown
# Item 1: Business
<!-- section-id: item-1 | type: item | depth: 0 -->

## Overview
<!-- section-id: item-1-overview | type: subsection | depth: 1 | parent: item-1 -->

Snap Inc. is a technology company...

### Snapchat
<!-- section-id: item-1-overview-snapchat | type: subsection | depth: 2 | parent: item-1-overview -->

Snapchat is our core mobile device application...

#### Camera
<!-- section-id: item-1-overview-snapchat-camera | type: subsection | depth: 3 | parent: item-1-overview-snapchat -->

The Camera is a powerful tool...
```

### 2. Section Metadata Format

Each section should have metadata in HTML comment:
```markdown
<!-- section-id: unique-id | type: item|note|subsection|table | depth: 0-5 | parent: parent-id | source: xbrl|html -->
```

**Fields:**
- `section-id`: Unique identifier (slug format)
- `type`: Section type (item, note, subsection, table)
- `depth`: Nesting level (0 = top level)
- `parent`: Parent section ID (for hierarchy)
- `source`: Data source (xbrl, html, toc)

### 3. Table Formatting

```markdown
#### Table: Consolidated Balance Sheet
<!-- section-id: item-8-table-1 | type: table | table-type: financial | depth: 4 | parent: item-8 -->

| Assets | 2024 | 2023 |
|--------|------|------|
| ...    | ...  | ...  |

<!-- end-section: item-8-table-1 -->
```

### 4. Note Structure

```markdown
# Note 1: Description of Business and Summary of Significant Accounting Policies
<!-- section-id: note-1 | type: note | depth: 0 | source: xbrl -->

## Basis of Presentation
<!-- section-id: note-1-basis-presentation | type: subsection | depth: 1 | parent: note-1 -->

Our consolidated financial statements are prepared...

## Use of Estimates
<!-- section-id: note-1-use-estimates | type: subsection | depth: 1 | parent: note-1 -->

The preparation of our consolidated financial statements...

### Key Estimates
<!-- section-id: note-1-use-estimates-key | type: subsection | depth: 2 | parent: note-1-use-estimates -->

Key estimates relate primarily to...
```

---

## Implementation Strategy

### Phase 1: Heading Detection & Hierarchy

**For Items (HTML-based):**
1. Detect main item heading (e.g., "Item 1. Business")
2. Detect subsections from:
   - Bold text patterns ("Overview", "Technology", etc.)
   - HTML `<h1>` to `<h6>` tags
   - All-caps section headers
3. Build hierarchy based on:
   - Heading tag level
   - Text formatting (bold weight, font size)
   - Position in document

**For Notes (XBRL-based):**
1. Use XBRL note titles as main headings
2. Detect subsections from:
   - Bold paragraph headers
   - Accounting topic patterns ("Basis of", "Use of", "Revenue Recognition")
   - Table titles within notes
3. Build hierarchy based on semantic patterns

### Phase 2: Section ID Generation

```python
def generate_section_id(section_title: str, parent_id: Optional[str] = None) -> str:
    """
    Generate unique section ID.

    Examples:
        "Item 1. Business" -> "item-1"
        "Overview" (parent: "item-1") -> "item-1-overview"
        "Snapchat" (parent: "item-1-overview") -> "item-1-overview-snapchat"
    """
    # Slugify title
    slug = re.sub(r'[^\w\s-]', '', section_title.lower())
    slug = re.sub(r'[-\s]+', '-', slug).strip('-')

    # Combine with parent
    if parent_id:
        return f"{parent_id}-{slug}"
    return slug
```

### Phase 3: Metadata Injection

Add metadata comments after each heading:
```python
def add_section_metadata(
    section_id: str,
    section_type: str,
    depth: int,
    parent_id: Optional[str] = None,
    source: str = "html"
) -> str:
    """Generate metadata comment."""
    metadata = [
        f"section-id: {section_id}",
        f"type: {section_type}",
        f"depth: {depth}",
    ]
    if parent_id:
        metadata.append(f"parent: {parent_id}")
    metadata.append(f"source: {source}")

    return f"<!-- {' | '.join(metadata)} -->"
```

### Phase 4: Chunk Boundary Markers

Add end markers for clarity:
```markdown
## Overview
<!-- section-id: item-1-overview | type: subsection | depth: 1 | parent: item-1 -->

Content here...

<!-- end-section: item-1-overview -->
```

---

## Chunking Strategy

### Recommended Chunk Sizes

For embedding pipelines (e.g., OpenAI, Anthropic):
- **Small chunks**: 512 tokens (good for precise retrieval)
- **Medium chunks**: 1024 tokens (balance)
- **Large chunks**: 2048 tokens (more context)

### Chunking Rules

1. **Never split mid-heading**: Always chunk at heading boundaries
2. **Preserve hierarchy**: Include parent headings in chunk context
3. **Keep tables intact**: Don't split tables across chunks
4. **Overlap chunks**: Use 20% overlap for context preservation

### Example Chunking

```python
chunks = [
    {
        "id": "item-1-overview",
        "hierarchy": ["Item 1: Business", "Overview"],
        "depth": 1,
        "content": "...",
        "metadata": {
            "section_id": "item-1-overview",
            "parent": "item-1",
            "type": "subsection",
            "source": "html"
        }
    },
    {
        "id": "item-1-overview-snapchat",
        "hierarchy": ["Item 1: Business", "Overview", "Snapchat"],
        "depth": 2,
        "content": "...",
        "metadata": {
            "section_id": "item-1-overview-snapchat",
            "parent": "item-1-overview",
            "type": "subsection",
            "source": "html"
        }
    }
]
```

---

## Benefits for RAG/Embedding

1. **Precise Retrieval**: Section IDs allow exact chunk referencing
2. **Hierarchical Context**: Parent IDs enable context reconstruction
3. **Semantic Chunking**: Natural section boundaries = better chunks
4. **Metadata Filtering**: Filter by type, depth, source during retrieval
5. **Citation Generation**: Easy to cite specific sections with IDs

---

## Example: Before vs After

### Before (Current)
```markdown
## SECTION: part_i_item_1
Item 1. Business.

Overview

Snap Inc. is a technology company...

Snapchat

Snapchat is our core mobile device application...
```

**Problems:**
- Flat structure
- No IDs
- Can't determine hierarchy
- Hard to chunk semantically

### After (Proposed)
```markdown
# Item 1: Business
<!-- section-id: item-1 | type: item | depth: 0 | source: html -->

## Overview
<!-- section-id: item-1-overview | type: subsection | depth: 1 | parent: item-1 -->

Snap Inc. is a technology company...

<!-- end-section: item-1-overview -->

### Snapchat
<!-- section-id: item-1-overview-snapchat | type: subsection | depth: 2 | parent: item-1-overview -->

Snapchat is our core mobile device application...

<!-- end-section: item-1-overview-snapchat -->
```

**Benefits:**
- Clear hierarchy (# → ## → ###)
- Unique IDs for each section
- Parent references for context
- Easy to chunk at any depth level
- Metadata for filtering

---

## Questions for Approval

1. **Heading Levels**: Should we limit depth to 4 levels (# → #### ) or support deeper?

2. **Section IDs**: Use slugified titles or numeric IDs (item-1-1-1)?

3. **Metadata Format**: HTML comments or YAML frontmatter?
   ```markdown
   <!-- Current: HTML comments -->

   ---
   section-id: item-1
   type: item
   depth: 0
   ---
   # Alternative: YAML frontmatter
   ```

4. **Page Numbers**: Remove entirely or mark as metadata?
   ```markdown
   <!-- page: 6 -->
   ```

5. **Chunk Markers**: Add `<!-- chunk-boundary -->` hints for optimal splitting points?

6. **Table Context**: Should tables include parent section context in metadata?

7. **Subsection Detection**: How aggressive should automatic subsection detection be?
   - Conservative: Only detect clear headings
   - Aggressive: Detect bold text, topic changes, etc.

---

## Implementation Plan

1. **Research subsection patterns** in items and notes
2. **Create heading hierarchy builder**
3. **Implement section ID generator**
4. **Add metadata injection**
5. **Test with SNAP filing**
6. **Iterate based on chunking results**
