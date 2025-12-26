# Chunking-Ready Markdown: Real SNAP Example

## Current Format (Flat Structure)

```markdown
START_DOCUMENT: 10-K 0001564408-25-000019 2025-02-05
FORMAT: Text is plain paragraphs. Tables are Markdown.

## SECTION: part_i_item_1
Item 1. Business.

Overview

Snap Inc. is a technology company. We believe the camera presents the greatest opportunity...

Snapchat

Snapchat is our core mobile device application and contains five distinct tabs...

Camera: The Camera is a powerful tool for communication...

Visual Messaging: Visual Messaging is a fast, fun way to communicate...

Snap Map: Snap Map is a live and highly personalized map...

Stories: Stories are a fun way to stay connected...

page 6

Spotlight: Spotlight showcases the best of Snapchat...

Our Partner Ecosystem

Many elements and features of Snapchat are enhanced by our expansive partner ecosystem...

Developers are able to integrate with Snapchat...

page 7

Our Advertising Products

We connect both brand and direct response advertisers to Snapchatters globally...
```

**Problems:**
- All subsections at same level
- "Camera", "Visual Messaging", etc. should be nested under "Snapchat"
- Page numbers mixed in
- No hierarchy
- Can't determine parent/child relationships
- Hard to chunk semantically

---

## Proposed Format (Hierarchical Structure)

```markdown
---
document:
  accession: 0001564408-25-000019
  form: 10-K
  date: 2025-02-05
  company: Snap Inc
  cik: '0001564408'
---

# Item 1: Business
<!-- section-id: item-1 | type: item | depth: 0 | source: html -->

## Overview
<!-- section-id: item-1-overview | type: subsection | depth: 1 | parent: item-1 -->

Snap Inc. is a technology company. We believe the camera presents the greatest opportunity to improve the way people live and communicate. We contribute to human progress by empowering people to express themselves, live in the moment, learn about the world, and have fun together.

Our flagship product, Snapchat, is a visual messaging application that enhances your relationships with friends, family, and the world. Visual messaging is a fast, fun way to communicate with friends and family using augmented reality, video, voice, messaging, and creative tools.

<!-- end-section: item-1-overview -->

## Product Description
<!-- section-id: item-1-product | type: subsection | depth: 1 | parent: item-1 -->

### Snapchat
<!-- section-id: item-1-product-snapchat | type: subsection | depth: 2 | parent: item-1-product -->

Snapchat is our core mobile device application and contains five distinct tabs, complemented by additional tools that function outside of the application.

<!-- end-section: item-1-product-snapchat -->

#### Camera
<!-- section-id: item-1-product-snapchat-camera | type: feature | depth: 3 | parent: item-1-product-snapchat -->

The Camera is a powerful tool for communication and the entry point for augmented reality experiences in Snapchat. Snapchat opens directly to the Camera, making it easy to create a Snap and send it to friends.

<!-- end-section: item-1-product-snapchat-camera -->

#### Visual Messaging
<!-- section-id: item-1-product-snapchat-messaging | type: feature | depth: 3 | parent: item-1-product-snapchat -->

Visual Messaging is a fast, fun way to communicate with friends and family using AR, video, voice, messaging, and creative tools.

<!-- end-section: item-1-product-snapchat-messaging -->

#### Snap Map
<!-- section-id: item-1-product-snapchat-map | type: feature | depth: 3 | parent: item-1-product-snapchat -->

Snap Map is a live and highly personalized map that allows Snapchatters to connect with friends and explore what is going on in their local area.

<!-- end-section: item-1-product-snapchat-map -->

#### Stories
<!-- section-id: item-1-product-snapchat-stories | type: feature | depth: 3 | parent: item-1-product-snapchat -->

Stories are a fun way to stay connected, and feature content from friends, our community, and our content partners.

<!-- end-section: item-1-product-snapchat-stories -->

#### Spotlight
<!-- section-id: item-1-product-snapchat-spotlight | type: feature | depth: 3 | parent: item-1-product-snapchat -->

Spotlight showcases the best of Snapchat, helping people discover new creators and content in a personalized way.

<!-- end-section: item-1-product-snapchat-spotlight -->

<!-- end-section: item-1-product -->

## Partner Ecosystem
<!-- section-id: item-1-partners | type: subsection | depth: 1 | parent: item-1 -->

Many elements and features of Snapchat are enhanced by our expansive partner ecosystem that includes developers, creators, publishers, and advertisers.

### Developers
<!-- section-id: item-1-partners-developers | type: subsection | depth: 2 | parent: item-1-partners -->

Developers are able to integrate with Snapchat and its core technologies, like Snap's AR Camera and Bitmoji, through a variety of tools.

<!-- end-section: item-1-partners-developers -->

<!-- end-section: item-1-partners -->

## Advertising Products
<!-- section-id: item-1-advertising | type: subsection | depth: 1 | parent: item-1 -->

We connect both brand and direct response advertisers to Snapchatters globally.

<!-- end-section: item-1-advertising -->

<!-- end-section: item-1 -->
```

---

## Chunking This Content

### Chunk 1: Item Overview
```json
{
  "id": "chunk-001",
  "section_id": "item-1-overview",
  "hierarchy": ["Item 1: Business", "Overview"],
  "depth": 1,
  "parent": "item-1",
  "type": "subsection",
  "content": "Snap Inc. is a technology company...",
  "metadata": {
    "form": "10-K",
    "item": "1",
    "company": "Snap Inc",
    "date": "2025-02-05"
  },
  "token_count": 156
}
```

### Chunk 2: Snapchat Description
```json
{
  "id": "chunk-002",
  "section_id": "item-1-product-snapchat",
  "hierarchy": ["Item 1: Business", "Product Description", "Snapchat"],
  "depth": 2,
  "parent": "item-1-product",
  "type": "subsection",
  "content": "Snapchat is our core mobile device application...",
  "metadata": {
    "form": "10-K",
    "item": "1",
    "company": "Snap Inc",
    "date": "2025-02-05"
  },
  "token_count": 87
}
```

### Chunk 3: Camera Feature
```json
{
  "id": "chunk-003",
  "section_id": "item-1-product-snapchat-camera",
  "hierarchy": ["Item 1: Business", "Product Description", "Snapchat", "Camera"],
  "depth": 3,
  "parent": "item-1-product-snapchat",
  "type": "feature",
  "content": "The Camera is a powerful tool...",
  "metadata": {
    "form": "10-K",
    "item": "1",
    "product": "Snapchat",
    "feature": "Camera",
    "company": "Snap Inc",
    "date": "2025-02-05"
  },
  "token_count": 145
}
```

---

## Notes Example

### Current Format
```markdown
## SECTION: Description of Business and Summary of Significant Accounting Policies
<!-- Source: XBRL -->
Dec. 31, 2024

Snap Inc. is a technology company.

Basis of Presentation

Our consolidated financial statements are prepared...

Use of Estimates

The preparation of our consolidated financial statements...

Revenue Recognition

Revenue is recognized when control...
```

### Proposed Format
```markdown
# Note 1: Description of Business and Summary of Significant Accounting Policies
<!-- section-id: note-1 | type: note | depth: 0 | source: xbrl | date: 2024-12-31 -->

Snap Inc. is a technology company.

Snap Inc. ("we," "our," "us"), a Delaware corporation, is headquartered in Santa Monica, California.

## Basis of Presentation
<!-- section-id: note-1-basis-presentation | type: accounting-policy | depth: 1 | parent: note-1 -->

Our consolidated financial statements are prepared in accordance with U.S. generally accepted accounting principles ("GAAP"). Our consolidated financial statements include the accounts of Snap Inc. and our wholly owned subsidiaries. All intercompany transactions and balances have been eliminated in consolidation.

<!-- end-section: note-1-basis-presentation -->

## Use of Estimates
<!-- section-id: note-1-use-estimates | type: accounting-policy | depth: 1 | parent: note-1 -->

The preparation of our consolidated financial statements in conformity with GAAP requires management to make estimates and assumptions that affect the reported amounts in the consolidated financial statements.

### Key Estimates
<!-- section-id: note-1-use-estimates-key | type: subsection | depth: 2 | parent: note-1-use-estimates -->

Key estimates relate primarily to determining the fair value of assets and liabilities assumed in business combinations, evaluation of contingencies, uncertain tax positions, and the fair value of strategic investments.

<!-- end-section: note-1-use-estimates-key -->
<!-- end-section: note-1-use-estimates -->

## Revenue Recognition
<!-- section-id: note-1-revenue-recognition | type: accounting-policy | depth: 1 | parent: note-1 -->

Revenue is recognized when control of the promised goods or services is transferred to our customers, in an amount that reflects the consideration we expect to receive in exchange for those goods or services. See Note 2 for additional information.

<!-- end-section: note-1-revenue-recognition -->

<!-- end-section: note-1 -->
```

---

## Query Examples with Hierarchical Structure

### Query 1: "How does Snapchat's camera work?"

**Retrieval:**
- Direct match: `section-id: item-1-product-snapchat-camera`
- Context from hierarchy: `["Item 1: Business", "Product Description", "Snapchat", "Camera"]`

**Result:**
```
Found in: Item 1 > Product Description > Snapchat > Camera

The Camera is a powerful tool for communication and the entry point for augmented reality experiences in Snapchat. Snapchat opens directly to the Camera, making it easy to create a Snap and send it to friends...
```

### Query 2: "What are Snap's revenue recognition policies?"

**Retrieval:**
- Direct match: `section-id: note-1-revenue-recognition`
- Context from parent: `note-1` (full accounting policies note)

**Result:**
```
Found in: Note 1 > Revenue Recognition

Revenue is recognized when control of the promised goods or services is transferred to our customers...
```

### Query 3: "Tell me about all Snapchat features"

**Retrieval:**
- Parent match: `section-id: item-1-product-snapchat`
- Get all children: `depth: 3, parent: item-1-product-snapchat`

**Result:**
```
Found 5 features under Snapchat:
- Camera
- Visual Messaging
- Snap Map
- Stories
- Spotlight
```

---

## Benefits Summary

1. **Semantic Chunking**: Chunks align with natural section boundaries
2. **Hierarchical Context**: Always know parent/child relationships
3. **Precise Retrieval**: Section IDs enable exact referencing
4. **Metadata Filtering**: Filter by type, depth, source during search
5. **Citation**: Easy to cite specific sections with full hierarchy
6. **Overlap Control**: Can retrieve parent context automatically
7. **Dynamic Chunking**: Can chunk at any depth level (1, 2, 3, 4)
