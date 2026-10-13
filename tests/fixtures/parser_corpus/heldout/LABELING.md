# Labelling guide: held-out 10-K truth set

You are given one 10-K as numbered text lines (`NNNNNN| text`), the full
document as edgartools renders it. Your job is to find every Item the filing
actually contains and say on which lines each one starts and ends. Work from
the text alone: do not run edgartools' section detection, and do not read
`boundary_truth.json`, `heldout_10k.json` or any test output.

## Which items

Standard 10-K items: 1, 1A, 1B, 1C, 2, 3, 4, 5, 6, 7, 7A, 8, 9, 9A, 9B, 9C,
10, 11, 12, 13, 14, 15, 16. Key them bare: `"1A"`, `"7A"`. `Item 9A(T)` is
`"9A"`. A filer's own "Item 4A. Executive Officers" is not a standard item:
it is the executive-officer section, which belongs to no item. Older filings
number by the form of their day (a 2001 10-K's exhibits item is Item 14);
key what the filing prints.

- An item is **present** when the body of the filing carries its heading,
  even if all it says is "None.", "Not applicable.", "[Reserved]", or that the
  information is incorporated by reference to the proxy statement.
- An item listed only in the table of contents, or only mentioned in a
  sentence ("see Item 7"), is not present. List items the TOC lists but the
  body never reaches under `absent` with a note.
- A filer that prints no "Item N" label but uses the item's title as a
  heading ("Risk Factors", "Legal Proceedings") still has the item; set
  `title_only: true`.
- One heading covering several items ("Items 10, 11, 12, 13 and 14") gives
  each of those keys the same lines, with `note: "combined 10-14"`.
- Older filings may have no Item 1A/1B/1C/7A/9A/9B/9C/16. Do not invent them.

## Where an item starts

On the line that carries its heading: the "Item N" label, or the title line
when the filer prints no label. Not on page furniture above it (page numbers,
running headers, "Table of Contents" back-links, a "PART II" divider).

## Where an item ends

On the last line of its own content, which is the line before the first of these:

- the next item's heading;
- a Part divider ("PART II", "PART III — OTHER INFORMATION"), which belongs to
  neither item;
- trailing page furniture: page numbers ("23", "F-4", "Page 12 of 80"),
  running headers or footers repeated on many pages (company name, "Form
  10-K", "Annual Report 2023"), "Table of Contents" or "Index" back-links.
  A date line ("February 20, 2025") is NOT furniture;
- for **Item 4**: an unnumbered "Executive Officers of the Registrant" (or
  similar) section, which belongs to no item;
- for the **last item** (15 or 16): the SIGNATURES heading, when nothing of
  substance follows the signature block. When the financial statements, an
  auditor's report, a financial-statement schedule or an exhibit index follow
  the signatures, the last item runs through them to the end of that content
  (excluding trailing furniture): content is never left in no section.
  Mark an exhibit index printed after the last item `note: "policy-open:
  exhibit index after last item"`.

## Item 8 that only points elsewhere

When Item 8 says no more than where the statements are ("The financial
statements ... immediately following Part IV", "begin on page F-1", "see
Item 15") AND the statements are printed at the back of the document, after
the last item: Item 8 is the statements. It starts at the first heading of
the statements block (the "Index to Financial Statements" or the auditor's
report, including a registrant-name title line directly above it) and ends
where the statements block ends, or, when an exhibit index, schedule or
appendix follows the statements, at the end of that content (content is
never left in no section); the last item then ends before that heading (or
at its own SIGNATURES). Set `note: "item 8 pointer -> back
statements"`. If the pointer leads to statements *inside* Item 15, or to an
exhibit not in the document, Item 8 is the short pointer text itself.

## Lines that start or end mid-line

Some headings share a line with body text, or a table row renders as one line.
Give `start_text` (the text the item starts at, copied from that line) or
`end_text` (the text its last line ends with) when the boundary is not at the
line edge. Otherwise omit them.

## Output

Return only JSON, keyed by accession:

```json
{"0000950129-04-000224": {
  "items": {
    "1":  {"start": 412, "end": 980},
    "1A": {"start": 981, "end": 1530, "note": "..."},
    "7":  {"start": 2010, "end": 2890, "start_text": "Item 7. Management's", "end_text": "liquidity."}
  },
  "absent": [{"item": "1C", "note": "listed in TOC, no body heading"}],
  "notes": "anything unusual: no TOC, text filing, combined items, statements at the back"
}}
```

Before answering, re-read the lines on both sides of every boundary you
chose: the line after an end and the line before a start must not belong to
the item.
