# Implementation Plan: Markdown Output for Drill-Down Objects

**Date Created**: 2026-03-25
**Planning Phase**: 2 of 3 (FIC Workflow)
**Based on Research**: Comparative analysis of 5.25.0 drill-down vs `extract_markdown()`
**Next Phase**: Implementation (`/implement`)

## Overview

Add `.to_markdown()` methods to the drill-down objects (`Note`, `Notes`, `Statement`, `StatementLineItem`) so users get LLM-optimized markdown output directly from the interactive API — without needing the `extract_markdown()` pipeline. The formatting logic is ported from `quant/markdown/helpers.py` (standalone, zero EdgarTools coupling) into a new `edgar/markdown.py` module.

## Current State Analysis

### What exists on main (5.25.0)

| Object | Current output methods | Markdown? |
|---|---|---|
| `RenderedStatement` | `to_markdown()`, `__rich__()`, `to_dataframe()` | Yes, but basic — no company header, broken indentation, Rich tag leakage |
| `Statement` | `to_context()`, `__rich__()`, `to_dataframe()`, `text()` | No |
| `StatementLineItem` | `__repr__()`, `__str__()` (label only) | No |
| `Note` | `to_context()`, `text`, `html`, `__rich__()` | No |
| `Notes` | `to_context()`, `__rich__()` | No |

### What exists on `notes-llm` branch

`quant/markdown/helpers.py` contains fully standalone formatting utilities:
- `process_content(html_str)` — HTML to LLM-optimized markdown (tables, headings, dedup, noise removal)
- `html_to_json(table_soup)` — HTML table to structured records
- `list_of_dicts_to_table(data_list)` — records to markdown table
- `create_markdown_table(headers, rows, alignments)` — lowest-level table serializer
- `clean_text()`, `postprocess_text()`, `extract_table_title()`, etc.

All helpers depend only on `bs4` + stdlib. Zero EdgarTools coupling.

### Key gap

The drill-down objects have rich structured data (tables, policies, narrative, line items with values) but no way to produce quality markdown. `to_context()` returns plain-text KV format. Users wanting markdown must use the full `extract_markdown()` pipeline, which requires a `Filing` object and can't target individual notes or line items.

## Desired End State

```python
# Statement → markdown table with proper formatting
stmt = financials.income_statement
print(stmt.to_markdown())
# ## Income Statement
# **Apple Inc. (AAPL) · FY 2024**
# | | 2024-09-28 | 2023-09-30 |
# | --- | ---: | ---: |
# | **Net sales** | **391,035** | **383,285** |
# |   Products | 224,578 | 220,272 |
# ...

# StatementLineItem → markdown with values + linked note
item = stmt['Goodwill']
print(item.to_markdown())
# **Goodwill**: $67.9B (2024-09-28)
# > Related: Note 7 — Goodwill and Intangible Assets

# Note → full markdown with tables rendered as pipe tables
note = tenk.notes['Debt']
print(note.to_markdown())
# ## Note 9: Debt
# **Expands:** Commercial paper, Long-term debt (current), Long-term debt (non-current)
# **From:** BalanceSheet
# ### Debt Maturity Schedule
# | | 2025 | 2026 | 2027 | ... |
# | --- | ---: | ---: | ---: | ---: |
# | Term debt | 10,500 | 9,750 | ... |
# ...
# ### Narrative
# The Company issues unsecured short-term promissory notes...

# Notes collection → full markdown document
notes = tenk.notes
print(notes.to_markdown())
# # Notes to Financial Statements
# **Apple Inc. · 10-K · Period ending 2024-09-28**
# ---
# ## Note 1: ...
# ## Note 2: ...
```

## Out of Scope

- Changing `extract_markdown()` itself — it will benefit from `to_markdown()` internally later
- Adding markdown to `Statements` collection, `Financials`, or `CompanyReport`
- YAML frontmatter generation (that's `extract_markdown()`'s job)
- Token budgeting or truncation
- MCP tool changes

## Implementation Approach

### Phase 1: Port Formatting Utilities into `edgar/markdown.py` ✅

**Goal**: Create a standalone markdown formatting module in the edgar package that the drill-down objects can import.

**Changes**:

1. `edgar/markdown.py` (new file):
   - [ ] Port `create_markdown_table(headers, rows, alignments)` from `quant/markdown/helpers.py`
   - [ ] Port `process_content(content, section_title, track_filtered)` — the HTML-to-markdown converter
   - [ ] Port supporting functions: `html_to_json`, `list_of_dicts_to_table`, `clean_text`, `extract_table_title`, `preprocess_currency_cells`, `preprocess_percent_cells`, `is_xbrl_metadata_table`, `is_noise_text`, `is_subsection_heading`, `postprocess_text`
   - [ ] Minimal adaptation: keep function signatures identical, only adjust imports
   - [ ] Add module docstring explaining this is the markdown formatting engine

   ```python
   """
   Markdown formatting utilities for financial data.

   Converts HTML tables, XBRL data, and structured records into
   LLM-optimized GitHub-Flavored Markdown.
   """
   ```

**Verification**:
- [ ] `from edgar.markdown import process_content, create_markdown_table` works
- [ ] `process_content("<table><tr><td>Revenue</td><td>$100M</td></tr></table>")` returns a pipe table
- [ ] `create_markdown_table(["Item", "Value"], [["Revenue", "$100M"]])` returns a valid GFM table

---

### Phase 2: Upgrade `RenderedStatement.to_markdown()` ✅

**Goal**: Fix existing issues and bring it up to the quality level of `extract_markdown()` output.

**Changes**:

1. `edgar/xbrl/rendering.py` — `RenderedStatement.to_markdown()`:
   - [ ] Add company name + ticker to the header (from `self.metadata`)
   - [ ] Strip ALL Rich markup tags from `units_note` (not just `[italic]`/`[/italic]`)
   - [ ] Fix indentation: use `\u00A0` (non-breaking space) pairs instead of regular spaces for level indentation (regular spaces are stripped by markdown renderers in pipe cells)
   - [ ] Add `detail` parameter: `'minimal'` (no header, just table), `'standard'` (default, with header), `'full'` (header + units note + source footer)
   - [ ] Add `optimize_for_llm` parameter: when `True`, drop abstract-only rows, simplify bold formatting

   ```python
   def to_markdown(self, detail: str = 'standard', optimize_for_llm: bool = False) -> str:
   ```

**Verification**:
- [ ] `stmt.render().to_markdown()` includes company name in header
- [ ] No `[dim]`, `[bold]`, `[italic]` Rich tags in output
- [ ] Indentation renders correctly in a markdown viewer
- [ ] `detail='minimal'` returns just the pipe table

---

### Phase 3: Add `Statement.to_markdown()` ✅

**Goal**: Convenience method that renders and formats in one call.

**Changes**:

1. `edgar/xbrl/statements.py` — `Statement`:
   - [ ] Add `to_markdown(detail='standard', optimize_for_llm=False) -> str`
   - [ ] Delegates to `self.render().to_markdown(detail, optimize_for_llm)`

   ```python
   def to_markdown(self, detail: str = 'standard', optimize_for_llm: bool = False) -> str:
       """Render this statement as GitHub-Flavored Markdown.

       Args:
           detail: 'minimal' (table only), 'standard' (with header), 'full' (header + footer)
           optimize_for_llm: Simplify output for LLM consumption
       """
       return self.render().to_markdown(detail=detail, optimize_for_llm=optimize_for_llm)
   ```

**Verification**:
- [ ] `financials.income_statement.to_markdown()` returns valid GFM
- [ ] Output matches `RenderedStatement.to_markdown()` for the same data

---

### Phase 4: Add `Note.to_markdown()` and `Notes.to_markdown()` ✅

**Goal**: The core deliverable — markdown output for notes with properly rendered tables.

**Changes**:

1. `edgar/xbrl/notes.py` — `Note.to_markdown()`:
   - [ ] Add `to_markdown(detail='standard', optimize_for_llm=True) -> str`
   - [ ] Structure:
     - `## Note {N}: {title}` heading
     - `**Expands:** {labels}` line (if expands exist)
     - `**From:** {statement types}` line (if expands_statements exist)
     - For each sub-table: `### {table_name}` + table content
       - Get HTML via `table_stmt.text(raw_html=True)`
       - Convert via `process_content()` from `edgar.markdown`
       - Fallback: if no HTML, use `table_stmt.text()` as plain text
     - Narrative text section (for `detail >= 'standard'`)
     - Policy sections (for `detail == 'full'`)
     - Detail sections (for `detail == 'full'`)

   ```python
   def to_markdown(self, detail: str = 'standard', optimize_for_llm: bool = True) -> str:
       """Render this note as GitHub-Flavored Markdown.

       Args:
           detail: 'minimal' (title + table names), 'standard' (+ tables + narrative),
                   'full' (+ policies + details)
           optimize_for_llm: Use LLM-optimized table formatting
       """
       from edgar.markdown import process_content
       parts = []
       parts.append(f"## Note {self.number}: {self.title}")

       if self.expands:
           parts.append(f"**Expands:** {', '.join(self.expands)}")
       if self.expands_statements:
           parts.append(f"**From:** {', '.join(self.expands_statements)}")

       # Tables — always included
       for table_stmt in self.tables:
           table_name = _extract_sub_name(table_stmt)
           parts.append(f"### {table_name}")
           html = table_stmt.text(raw_html=True)
           if html and optimize_for_llm:
               parts.append(process_content(html, section_title=table_name))
           elif html:
               parts.append(table_stmt.text() or '')

       # Narrative — standard and full
       if detail in ('standard', 'full') and self.text:
           parts.append("### Narrative")
           parts.append(self.text)

       # Policies — full only
       if detail == 'full':
           for policy in self.policies:
               name = _extract_sub_name(policy)
               parts.append(f"### Policy: {name}")
               parts.append(policy.text() or '')

           # Details — full only
           for detail_stmt in self.details:
               name = _extract_sub_name(detail_stmt)
               parts.append(f"### {name}")
               html = detail_stmt.text(raw_html=True)
               if html and optimize_for_llm:
                   parts.append(process_content(html, section_title=name))
               else:
                   parts.append(detail_stmt.text() or '')

       return '\n\n'.join(part for part in parts if part)
   ```

2. `edgar/xbrl/notes.py` — `Notes.to_markdown()`:
   - [ ] Add `to_markdown(detail='standard', focus=None, optimize_for_llm=True) -> str`
   - [ ] Structure:
     - `# Notes to Financial Statements` heading
     - `**{entity} · {form} · Period ending {date}**` subtitle
     - `---` separator
     - Each note via `note.to_markdown(detail, optimize_for_llm)`
   - [ ] `focus` parameter: list of topic strings to filter which notes are included (reuses `Notes.search()`)

   ```python
   def to_markdown(self, detail: str = 'standard', focus=None, optimize_for_llm: bool = True) -> str:
       """Render all notes as a single GitHub-Flavored Markdown document."""
       parts = ["# Notes to Financial Statements"]
       # ... header with entity/form/period ...

       notes_to_render = self._notes
       if focus:
           if isinstance(focus, str):
               focus = [focus]
           notes_to_render = []
           for topic in focus:
               notes_to_render.extend(self.search(topic))

       for note in notes_to_render:
           parts.append(note.to_markdown(detail=detail, optimize_for_llm=optimize_for_llm))

       return '\n\n---\n\n'.join(parts) if len(parts) > 1 else parts[0]
   ```

**Verification**:
- [ ] `note.to_markdown()` returns valid GFM with pipe tables for sub-tables
- [ ] `notes.to_markdown(focus='debt')` returns only debt-related notes
- [ ] `note.to_markdown(detail='minimal')` returns title + table names only
- [ ] `note.to_markdown(detail='full')` includes policies and details
- [ ] Tables from `process_content()` have proper column alignment and deduplication

---

### Phase 5: Add `StatementLineItem.to_markdown()` ✅

**Goal**: Compact markdown for a single line item with values and note link.

**Changes**:

1. `edgar/xbrl/statements.py` — `StatementLineItem`:
   - [ ] Add `to_markdown(include_note=True) -> str`
   - [ ] Format: `**{label}**: {value} ({period})` with optional note reference
   - [ ] If multiple periods, show as inline table

   ```python
   def to_markdown(self, include_note: bool = True) -> str:
       """Render this line item as markdown with values and optional note link."""
       parts = []

       # Values
       values = self.values
       if values:
           # Format as inline: **Label**: val1 (period1), val2 (period2)
           formatted = ', '.join(f"{v} ({k})" for k, v in values.items() if v is not None)
           parts.append(f"**{self.label}**: {formatted}")
       else:
           parts.append(f"**{self.label}**")

       # Note reference
       if include_note:
           note = self.note
           if note:
               parts.append(f"> Related: Note {note.number} — {note.title}")

       return '\n\n'.join(parts)
   ```

**Verification**:
- [ ] `stmt['Goodwill'].to_markdown()` returns formatted values + note reference
- [ ] `stmt['Goodwill'].to_markdown(include_note=False)` omits the note line
- [ ] Works for items with no note (no error, no empty blockquote)

---

### Phase 6: Wire `to_context(focus=...)` to use `to_markdown()` internally ✅

**Goal**: Upgrade `TenK/TenQ.to_context(focus=...)` to optionally return markdown instead of plain text.

**Changes**:

1. `edgar/company_reports/_base.py` — `_focused_context()`:
   - [ ] Add `format` parameter: `'text'` (default, backward-compatible) or `'markdown'`
   - [ ] When `format='markdown'`, delegate note rendering to `note.to_markdown()` instead of `note.to_context()` + manual `_append_expands_with_values()`

2. `edgar/company_reports/ten_k.py` and `ten_q.py` — `to_context()`:
   - [ ] Pass `format` parameter through to `_focused_context()`

   ```python
   def to_context(self, detail='standard', focus=None, format='text') -> str:
       if focus:
           return self._focused_context(focus, detail, format=format)
       # ... existing standard path ...
   ```

**Verification**:
- [ ] `tenk.to_context(focus='debt')` still returns plain text (backward-compatible)
- [ ] `tenk.to_context(focus='debt', format='markdown')` returns GFM with pipe tables
- [ ] Both paths return the same semantic content

## Testing Strategy

### Unit Tests
- `tests/test_markdown.py` — test `create_markdown_table`, `process_content` with sample HTML
- `tests/test_note_markdown.py` — test `Note.to_markdown()` with VCR cassettes
- `tests/test_statement_markdown.py` — test `Statement.to_markdown()` output format

### Integration Tests (network, VCR)
- Round-trip: `Company("MSFT").get_filings(form="10-K").latest().obj().notes['Debt'].to_markdown()`
- Verify table content matches known values (assert specific cells, not just `is not None`)

### Manual Verification
- Visual check: paste `to_markdown()` output into a markdown renderer
- LLM check: feed output to an LLM and verify it can answer questions about the data

## Risk Mitigation

### Potential Issues
1. **Issue**: `bs4` import adds startup cost for users who don't need markdown
   **Mitigation**: Lazy import — `from edgar.markdown import process_content` inside `to_markdown()` methods, not at module top level

2. **Issue**: `process_content()` is ~200 lines with many helpers — large port
   **Mitigation**: Port the full file as-is (proven code), don't refactor during port. Exact copy with only import path changes.

3. **Issue**: Some notes have no HTML in their tables (`text(raw_html=True)` returns `None`)
   **Mitigation**: Fallback chain: HTML → `process_content()`, plain text → `postprocess_text()`, empty → skip

4. **Issue**: `RenderedStatement.to_markdown()` signature change
   **Mitigation**: New parameters are keyword-only with defaults matching current behavior

### Rollback Plan
- All changes are additive (`to_markdown()` methods) — no existing API is modified
- `_focused_context(format=...)` defaults to `'text'`, preserving current behavior
- `RenderedStatement.to_markdown()` keeps its current output as default

## Dependencies
- `beautifulsoup4` — already a dependency of edgartools
- No new external dependencies

## Success Criteria
- [ ] `note.to_markdown()` produces valid GFM with properly formatted pipe tables
- [ ] `stmt.to_markdown()` produces valid GFM with aligned numeric columns
- [ ] `item.to_markdown()` shows values and note reference
- [ ] `notes.to_markdown(focus='debt')` returns a focused markdown document
- [ ] All `to_markdown()` output renders correctly in GitHub/VSCode markdown preview
- [ ] No regression in existing `to_context()`, `__rich__()`, or `text()` methods
- [ ] `process_content()` in `edgar/markdown.py` passes the same test cases as the original

## Phase Summary

| Phase | What | Key Files |
|---|---|---|
| 1 | Port formatting utilities | `edgar/markdown.py` (new) |
| 2 | Fix `RenderedStatement.to_markdown()` | `edgar/xbrl/rendering.py` |
| 3 | Add `Statement.to_markdown()` | `edgar/xbrl/statements.py` |
| 4 | Add `Note.to_markdown()` + `Notes.to_markdown()` | `edgar/xbrl/notes.py` |
| 5 | Add `StatementLineItem.to_markdown()` | `edgar/xbrl/statements.py` |
| 6 | Wire `to_context(format='markdown')` | `edgar/company_reports/_base.py`, `ten_k.py`, `ten_q.py` |
