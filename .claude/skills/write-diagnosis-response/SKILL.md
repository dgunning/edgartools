---
name: write-diagnosis-response
description: >
  Generates comprehensive 'Diagnosis Response' documents for system architects investigating
  EDGAR/XBRL processing issues. Performs deep code analysis, traces data flows, compares
  implementations across archetypes, and validates against source documents. Use when
  responding to architectural questions about extraction logic, validation failures,
  classification decisions, or systemic design concerns.
context: fork
agent: general-purpose
allowed-tools: Read, Write, Bash(ls:*), Bash(find:*), Bash(git log:*), Bash(git diff:*), Bash(git show:*), Bash(git blame:*), Bash(cat:*), Bash(head:*), Bash(tail:*), Bash(grep:*), Bash(wc:*), Glob, Grep
---

# Diagnosis Response Skill

Generate rigorous, evidence-based responses to system architect inquiries about the EDGAR/XBRL financial data extraction system.

## Purpose

This skill produces **Diagnosis Response** documents that answer architectural questions with:
- Direct code evidence (file paths, line numbers, function signatures)
- Data flow traces showing how values propagate through the system
- Comparative analysis across different entity archetypes
- Root cause identification with supporting artifacts
- Actionable recommendations backed by implementation details

## When to Use

Use this skill when a system architect asks questions about:
- **Data Integrity**: Why a specific entity (e.g., WFC, STT) fails validation
- **Classification Logic**: How archetypes are assigned and why entities differ
- **Strategy Implementation**: How extraction strategies work internally
- **Validation Discrepancies**: Mismatches between extracted data and reference sources
- **Systemic Design**: Architectural decisions, technical debt, or missing infrastructure

Trigger phrases: "diagnostic questions", "architecture review", "why does X fail", "how does Y work internally"

---

## Pre-computed Context

**Timestamp:** !`date +%Y-%m-%d-%H-%M`
**Project Root:** !`pwd`
**Git Branch:** !`git branch --show-current`
**Recent Commits (Standardization):**
!`git log --oneline -5 -- edgar/xbrl/standardization/ 2>/dev/null || echo "No recent changes"`

---

## Usage

```
/write-diagnosis-response <path_to_evolution_report> <path_to_diagnosis_questions>
```

**Arguments via $ARGUMENTS:**
- First argument: Path to the most recent evolution/status report (provides context on current state)
- Second argument: Path to the architect's diagnosis questions file

If arguments are missing, prompt the user for the required inputs.

---

## Investigation Methodology

For each question in the diagnosis request, follow this systematic approach:

### Phase 1: Question Classification

Categorize each question into one of these types:

| Type | Description | Primary Investigation Method |
|------|-------------|------------------------------|
| **Data Integrity** | Raw data presence/absence, XBRL fact availability | Inspect XBRL instance documents, trace concept mappings |
| **Classification** | Archetype assignment, entity categorization | Compare entity configurations, analyze decision logic |
| **Strategy Logic** | How extraction/calculation strategies work | Code walkthrough, trace execution paths |
| **Validation** | Discrepancies with reference data | Cross-reference source documents, verify calculations |
| **Systemic** | Architectural decisions, infrastructure gaps | Review ADRs, assess technical debt |

### Phase 2: Evidence Collection

For each question, gather these artifacts:

#### Code Evidence
```bash
# Find relevant implementation files
find . -type f -name "*.py" | xargs grep -l "<concept_or_function>"

# Trace function definitions
grep -rn "def <function_name>" --include="*.py"

# Check git history for context
git log --oneline -10 -- <relevant_file>
git blame <file> | grep -A5 -B5 "<relevant_line>"
```

#### Data Evidence
```bash
# Locate entity-specific configurations
find . -path "*/configs/*" -name "*.json" | xargs grep -l "<ticker>"

# Find test fixtures and golden masters
find . -path "*/tests/*" -o -path "*/fixtures/*" | xargs grep -l "<ticker>"
```

#### Documentation Evidence
```bash
# Check for ADRs (Architecture Decision Records)
find . -path "*/adr/*" -o -name "ADR-*.md"

# Find related documentation
grep -rn "<concept>" --include="*.md"
```

### Phase 3: Analysis Framework

Structure your analysis for each question:

1. **Restate the Question** - Ensure you understood what's being asked
2. **Provide Direct Answer** - Lead with the conclusion
3. **Show Evidence** - Code snippets, file paths, line numbers
4. **Explain the Mechanism** - How the code actually works
5. **Identify Gaps** - What's missing or problematic
6. **Recommend Action** - Specific next steps if applicable

---

## Response Template

Use this structure for the diagnosis response document:

```markdown
# Diagnosis Response

**Date:** [timestamp]
**In Response To:** [link to architect's questions]
**Based On:** [link to evolution report]
**Prepared By:** Claude (AI Assistant)

---

## Executive Summary

[2-3 sentence overview of key findings across all questions]

---

## Detailed Responses

### Question 1: [Topic]

**Architect's Question:**
> [Quote the original question]

**Short Answer:**
[1-2 sentence direct answer]

**Evidence:**

*Code Location:*
- File: `path/to/file.py`
- Lines: XX-YY
- Function: `function_name()`

*Relevant Code:*
```python
[extracted code snippet with context]
```

*Data Artifacts:*
- [List any relevant configs, fixtures, or test data]

**Analysis:**
[Detailed explanation of what the code does and why]

**Implications:**
[What this means for the system/question at hand]

**Recommendation:**
[Specific action items if applicable]

---

[Repeat for each question]

---

## Cross-Cutting Concerns

[Any themes or issues that span multiple questions]

## Appendix

### A. File References
[Complete list of files examined]

### B. Git History Context
[Relevant commits and their purposes]

### C. Glossary
[Define any domain-specific terms used]
```

---

## Domain Knowledge

### EDGAR/XBRL Context

This system extracts financial data from SEC EDGAR filings. Key concepts:

- **XBRL Instance Documents**: XML files containing tagged financial facts
- **Concepts**: Standardized tags (e.g., `us-gaap:ShortTermBorrowings`)
- **Extensions**: Company-specific concepts (e.g., `wfc:CustomDebtItem`)
- **Calculation Linkbase**: Defines mathematical relationships between concepts
- **Presentation Linkbase**: Defines display hierarchy

### Archetype System

Entities are classified into archetypes based on their financial structure:

| Archetype | Characteristic | Example Entities |
|-----------|----------------|------------------|
| **Commercial** | Traditional lending operations | Regional banks |
| **Custodial** | Asset custody, securities services | BK, STT |
| **Dealer** | Trading, market making | Investment banks |
| **Hybrid** | Multiple business lines | Large diversified banks |

### Common Failure Patterns

1. **Concept Mapping Failures**: Standard concept absent, extension used instead
2. **Hierarchy Mismatches**: Values nested differently than expected
3. **Aggregation Ambiguity**: Multiple valid ways to sum components
4. **Temporal Misalignment**: Point-in-time vs. period values mixed
5. **Reference Data Discrepancies**: External sources (yfinance) disagree

---

## Quality Checklist

Before finalizing the response, verify:

- [ ] Every claim has a file path and line number reference
- [ ] Code snippets are actual extracts, not paraphrased
- [ ] Git history provides context for design decisions
- [ ] Recommendations are specific and actionable
- [ ] Technical terms are defined or linked to glossary
- [ ] Cross-references between related questions are noted
- [ ] Limitations of the analysis are acknowledged

---

## Output Location

Write the completed diagnosis response to:
```
sandbox/notes/008_bank_sector_expansion/diagnosis-response_[TIMESTAMP].md
```

Use the pre-computed timestamp from the context section above. Do not generate a new timestamp.

---

## Common Pitfalls to Avoid

1. **Speculation without evidence** - If you cannot find code proof, say so explicitly
2. **Incomplete traces** - Follow the data flow end-to-end, not just the entry point
3. **Ignoring test fixtures** - Golden masters and test data reveal expected behavior
4. **Missing git context** - Recent changes often explain current state
5. **Overly generic recommendations** - Be specific about files, functions, and changes needed