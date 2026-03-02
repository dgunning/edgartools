# SEC Filing Attachments & Exhibits Reference

Reference guide for working with SEC filing attachments via EdgarTools. Covers the data model, available properties, exhibit type classifications, and description enhancement logic.

---

## Data Model

### Attachment

Represents a single document within an SEC filing. Every filing contains one or more attachments: a primary document (the filing itself) and supplementary exhibits, graphics, XBRL data files, and other supporting documents.

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `sequence_number` | `str` | Position in the filing (e.g., `"1"`, `"2"`, `"15"`). Sequence `"1"` is always the primary document. May be empty for some data files. |
| `document` | `str` | Filename of the attachment (e.g., `"aapl-20251231.htm"`, `"ex31-1.htm"`, `"image_0.jpg"`). |
| `document_type` | `str` | SEC document type code (e.g., `"10-K"`, `"EX-21"`, `"EX-31.1"`, `"GRAPHIC"`, `"EX-101.SCH"`). |
| `description` | `str` | Description from the filing's SGML metadata or the SEC index page. Often repeats the `document_type` for exhibits (e.g., `"EX-21"`) which is not useful. May be a meaningful description (e.g., `"Employment Agreement - John Doe"`). Can be empty. |
| `purpose` | `str \| None` | Human-readable label from `FilingSummary.xml` (e.g., `"Cover"`, `"CONSOLIDATED BALANCE SHEETS"`). Only populated for iXBRL report documents (R1.htm, R2.htm, etc.). `None` for exhibits and other attachments. |
| `size` | `int \| None` | File size in bytes. `None` when loaded from SGML or unavailable. |
| `ixbrl` | `bool` | Whether this document is in Inline XBRL format. |
| `path` | `str` | Relative URL path for constructing the full SEC download URL. |
| `url` | `str` | *(property)* Full SEC EDGAR URL for downloading this attachment. |
| `extension` | `str` | *(property)* File extension including the dot (e.g., `".htm"`, `".xml"`, `".jpg"`). |
| `empty` | `bool` | *(property)* `True` if the attachment has no document filename (occurs in some older filings). |

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `content` | `str \| bytes` | Downloads and returns the raw file content. Text for HTML/XML/TXT, bytes for binary files. |
| `download(path=None)` | `str \| bytes` | Downloads the file. If `path` is provided (file or directory), saves to disk and returns the path. If `None`, returns content directly. |
| `text()` | `str \| None` | Returns a plain-text rendering of the attachment. For HTML documents, parses and extracts readable text. For reports (R*.htm), delegates to the report's text renderer. |
| `markdown()` | `str \| None` | Converts HTML attachments to Markdown format. Returns `None` for non-HTML documents. |
| `view()` | `None` | Renders the attachment to the terminal using Rich. For reports, renders the structured report view. |
| `is_html()` | `bool` | `True` if extension is `.htm` or `.html`. |
| `is_xml()` | `bool` | `True` if extension is `.xsd`, `.xml`, or `.xbrl`. |
| `is_text()` | `bool` | `True` if the file is a text-based document. |
| `is_binary()` | `bool` | `True` if the file is binary (images, PDFs, etc.). |
| `is_report()` | `bool` | `True` if the filename matches the pattern `R*.htm` (iXBRL viewer report pages). |

#### Description Priority

When displaying attachment descriptions, the effective description is resolved in this order:

1. **`purpose`** — From FilingSummary.xml. Best quality, but only available for iXBRL report pages.
2. **`description`** — From SGML metadata or the SEC index HTML page. Quality varies: sometimes a real description, sometimes just echoes the type code.
3. **Empty** — No description available.

The core problem: for many exhibits, `description` equals `document_type` (e.g., both are `"EX-21"`), providing no additional information to the user.

---

### Attachments (Collection)

Container for all attachments within a filing. Provides iteration, querying, and bulk operations.

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `documents` | `list[Attachment]` | All document-type attachments (primary + exhibits). |
| `data_files` | `list[Attachment] \| None` | XBRL and other data files. `None` if no data files section exists. |
| `primary_documents` | `list[Attachment]` | The primary filing document(s) — typically sequence `"1"`. |
| `primary_html_document` | `Attachment \| None` | *(property)* The main HTML document of the filing. |
| `primary_xml_document` | `Attachment \| None` | *(property)* The main XML document, if any. |
| `text_document` | `Attachment \| None` | *(property)* The complete submission text file. |
| `exhibits` | `Attachments` | *(property)* Filtered collection containing only the primary document and all EX-* type attachments. |
| `graphics` | `Attachments` | *(property)* Filtered collection containing only GRAPHIC type attachments. |

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `__getitem__(item)` | `Attachment` | Access by sequence number (`int` or digit string) or by filename (`str`). Raises `KeyError` if not found. |
| `get_by_sequence(seq)` | `Attachment` | Get attachment by its exact sequence number. |
| `get_by_index(index)` | `Attachment` | Get attachment by zero-based position in the combined list. |
| `get_report(filename)` | `Report \| None` | Get the structured report object for a given report filename. |
| `query(query_str)` | `Attachments` | Filter attachments using a query expression (see below). |
| `download(path, archive=False)` | `None` | Download all attachments to a directory, or to a zip file if `archive=True`. |
| `markdown()` | `dict[str, str]` | Convert all HTML attachments to Markdown. Returns `{filename: markdown_content}`. |
| `serve(port=8000)` | `tuple` | Launch a local HTTP server to browse attachments in a web browser. |
| `__len__()` | `int` | Total number of attachments (documents + data files). |
| `__iter__()` | `Iterator[Attachment]` | Iterate over all attachments. |

#### Query Syntax

The `query()` method supports conditions on `document`, `description`, and `document_type`:

```python
# Find press releases
attachments.query("'RELEASE' in description and document_type in ['EX-99.1', 'EX-99']")

# Find all HTML exhibits
attachments.query("document.endswith('.htm') and re.match('EX-', document_type)")

# Find specific exhibit type
attachments.query("document_type == 'EX-21'")
```

---

## SEC Exhibit Type Descriptions

The following table maps SEC exhibit type codes to their standard descriptions as defined by **Regulation S-K, Item 601** (17 CFR § 229.601). Use this to provide meaningful descriptions when the filing's own description is missing or just echoes the type code.

### Enhancement Logic

```
if description is meaningful (non-empty AND differs from document_type):
    use description as-is
else:
    look up document_type in EXHIBIT_DESCRIPTIONS (exact match first, then base type)
    if found:
        use the standard description
    else:
        leave description empty
```

For sub-numbered exhibits (e.g., `EX-10.5`, `EX-23.3`), the numeric suffix is a sequential counter, not a meaningful classification. Fall back to the base type: `EX-10.5` → look up `EX-10` → "Material contracts".

### Core Corporate Documents (1-10)

| Type | Description |
|------|-------------|
| `EX-1` | Underwriting agreement |
| `EX-1.A` | Underwriting agreement — form of underwriting agreement |
| `EX-1.B` | Underwriting agreement — form of selected dealer agreement |
| `EX-2` | Plan of acquisition, reorganization, arrangement, liquidation, or succession |
| `EX-3` | Articles of incorporation and bylaws |
| `EX-3.A` | Articles of incorporation |
| `EX-3.B` | Bylaws |
| `EX-4` | Instruments defining the rights of security holders |
| `EX-5` | Opinion re legality |
| `EX-7` | Correspondence from independent accountant regarding non-reliance on previously issued audit report |
| `EX-8` | Opinion re tax matters |
| `EX-9` | Voting trust agreement |
| `EX-10` | Material contracts |

### Financial and Compliance (11-20)

| Type | Description |
|------|-------------|
| `EX-11` | Statement re computation of per share earnings |
| `EX-12` | Statement re computation of ratios |
| `EX-13` | Annual report to security holders |
| `EX-14` | Code of ethics |
| `EX-15` | Letter re unaudited interim financial information |
| `EX-16` | Letter re change in certifying accountant |
| `EX-17` | Correspondence on departure of director |
| `EX-18` | Letter re change in accounting principles |
| `EX-19` | Insider trading policies and procedures |
| `EX-20` | Other documents or statements to security holders |

### Required Disclosures (21-32)

| Type | Description |
|------|-------------|
| `EX-21` | Subsidiaries of the registrant |
| `EX-22` | Subsidiary guarantors and issuers of guaranteed securities |
| `EX-23` | Consent of experts and counsel |
| `EX-24` | Power of attorney |
| `EX-25` | Statement of eligibility of trustee |
| `EX-26` | Invitation for competitive bids |
| `EX-27` | Financial data schedule (obsolete — replaced by XBRL) |
| `EX-28` | Information from reports furnished to state insurance regulatory authorities |
| `EX-29` | Additional exhibits |
| `EX-30` | Disclosure regarding foreign jurisdictions that prevent inspections |

### Certifications (31-32)

| Type | Description |
|------|-------------|
| `EX-31` | Rule 13a-14(a)/15d-14(a) certification (Sarbanes-Oxley Section 302) |
| `EX-31.1` | Certification of Chief Executive Officer pursuant to Section 302 |
| `EX-31.2` | Certification of Chief Financial Officer pursuant to Section 302 |
| `EX-32` | Section 1350 certification (Sarbanes-Oxley Section 906) |
| `EX-32.1` | Certification of Chief Executive Officer pursuant to Section 906 |
| `EX-32.2` | Certification of Chief Financial Officer pursuant to Section 906 |

### Specialized Exhibits (33+)

| Type | Description |
|------|-------------|
| `EX-33` | Report on assessment of compliance with servicing criteria |
| `EX-34` | Attestation report on assessment of compliance with servicing criteria |
| `EX-35` | Servicer compliance statement |
| `EX-36` | Static pool information |
| `EX-95` | Mine safety disclosure |
| `EX-96` | Technical report summary (mining) |
| `EX-97` | Compensation recovery (clawback) policy |
| `EX-99` | Additional exhibits not otherwise categorized |
| `EX-99.1` | Additional exhibit (commonly press releases, presentations, or supplemental data) |

### XBRL Interactive Data (101)

| Type | Description |
|------|-------------|
| `EX-101` | Interactive data file (general) |
| `EX-101.INS` | XBRL instance document — contains the actual reported data values |
| `EX-101.SCH` | XBRL taxonomy extension schema — defines custom elements |
| `EX-101.CAL` | XBRL calculation linkbase — defines mathematical relationships between elements |
| `EX-101.DEF` | XBRL definition linkbase — defines dimensional relationships |
| `EX-101.LAB` | XBRL label linkbase — maps element IDs to human-readable labels |
| `EX-101.PRE` | XBRL presentation linkbase — defines display order and grouping |

### Cover Page and Filing Fees (104, 107)

| Type | Description |
|------|-------------|
| `EX-104` | Cover page interactive data file (Inline XBRL embedded in the cover page) |
| `EX-107` | Filing fee table |

### Non-Exhibit Document Types

These are not exhibit types but appear as `document_type` values on attachments:

| Type | Description |
|------|-------------|
| `10-K` | Annual report |
| `10-Q` | Quarterly report |
| `8-K` | Current report |
| `DEF 14A` | Definitive proxy statement |
| `S-1` | Registration statement |
| `20-F` | Annual report (foreign private issuer) |
| `GRAPHIC` | Image file (JPG, PNG, GIF) |
| `HTML` | HTML document |
| `XML` | XML document |
| `JSON` | JSON data file |
| `PDF` | PDF document |
| `EXCEL` | Excel spreadsheet |
| `ZIP` | Archive file |
| `CSS` | Stylesheet |
| `JS` | JavaScript file |
| `INFORMATION TABLE` | Structured data table (e.g., 13F holdings) |
| `EX-101.SCH` | XBRL taxonomy extension schema document |
| `EX-101.CAL` | XBRL taxonomy extension calculation linkbase document |
| `EX-101.DEF` | XBRL taxonomy extension definition linkbase document |
| `EX-101.LAB` | XBRL taxonomy extension label linkbase document |
| `EX-101.PRE` | XBRL taxonomy extension presentation linkbase document |

---

## Exhibit Categories

Exhibits can be grouped into broad functional categories for filtering and display:

| Category | Exhibit Numbers | Purpose |
|----------|----------------|---------|
| **Corporate** | 1-5, 9, 21, 22, 24, 25 | Incorporation documents, bylaws, underwriting, subsidiaries, powers of attorney |
| **Material Contracts** | 10 | Employment agreements, credit facilities, leases, M&A agreements |
| **Financial** | 11-13, 15, 16, 18, 23, 28, 35, 36 | Earnings computations, auditor consents, accountant correspondence |
| **Compliance** | 7, 8, 14, 17, 19, 31, 32, 97 | Certifications, code of ethics, insider trading policies, clawback policies |
| **XBRL** | 101, 104 | Machine-readable financial data and cover pages |
| **Mining** | 95, 96 | Mine safety disclosures and technical reports |
| **Additional** | 99, 100 | Press releases, supplemental data, and any exhibits not fitting other categories |
| **Filing Fees** | 107 | Fee table calculations |

---

## Lookup Dictionary

Complete dictionary for programmatic use. Keys are exhibit type codes, values are standard descriptions.

```python
EXHIBIT_DESCRIPTIONS = {
    # Core corporate documents (1-10)
    "EX-1": "Underwriting agreement",
    "EX-1.A": "Underwriting agreement - form of underwriting agreement",
    "EX-1.B": "Underwriting agreement - form of selected dealer agreement",
    "EX-2": "Plan of acquisition, reorganization, arrangement, liquidation, or succession",
    "EX-3": "Articles of incorporation and bylaws",
    "EX-3.A": "Articles of incorporation",
    "EX-3.B": "Bylaws",
    "EX-4": "Instruments defining the rights of security holders",
    "EX-5": "Opinion re legality",
    "EX-7": "Correspondence from independent accountant regarding non-reliance",
    "EX-8": "Opinion re tax matters",
    "EX-9": "Voting trust agreement",
    "EX-10": "Material contracts",

    # Financial and compliance (11-20)
    "EX-11": "Statement re computation of per share earnings",
    "EX-12": "Statement re computation of ratios",
    "EX-13": "Annual report to security holders",
    "EX-14": "Code of ethics",
    "EX-15": "Letter re unaudited interim financial information",
    "EX-16": "Letter re change in certifying accountant",
    "EX-17": "Correspondence on departure of director",
    "EX-18": "Letter re change in accounting principles",
    "EX-19": "Insider trading policies and procedures",
    "EX-20": "Other documents or statements to security holders",

    # Required disclosures (21-32)
    "EX-21": "Subsidiaries of the registrant",
    "EX-22": "Subsidiary guarantors and issuers of guaranteed securities",
    "EX-23": "Consent of experts and counsel",
    "EX-24": "Power of attorney",
    "EX-25": "Statement of eligibility of trustee",
    "EX-26": "Invitation for competitive bids",
    "EX-27": "Financial data schedule",
    "EX-28": "Information from reports furnished to state insurance regulatory authorities",
    "EX-29": "Additional exhibits",
    "EX-30": "Disclosure regarding foreign jurisdictions that prevent inspections",

    # Certifications (31-32)
    "EX-31": "Rule 13a-14(a)/15d-14(a) certification (Section 302)",
    "EX-31.1": "Certification of CEO pursuant to Section 302",
    "EX-31.2": "Certification of CFO pursuant to Section 302",
    "EX-32": "Section 1350 certification (Section 906)",
    "EX-32.1": "Certification of CEO pursuant to Section 906",
    "EX-32.2": "Certification of CFO pursuant to Section 906",

    # Specialized (33+)
    "EX-33": "Report on assessment of compliance with servicing criteria",
    "EX-34": "Attestation report on assessment of compliance with servicing criteria",
    "EX-35": "Servicer compliance statement",
    "EX-36": "Static pool information",
    "EX-95": "Mine safety disclosure",
    "EX-96": "Technical report summary (mining)",
    "EX-97": "Compensation recovery (clawback) policy",
    "EX-99": "Additional exhibits",
    "EX-99.1": "Additional exhibit",
    "EX-99.2": "Additional exhibit",
    "EX-100": "Additional exhibits",

    # XBRL (101)
    "EX-101": "Interactive data file",
    "EX-101.INS": "XBRL instance document",
    "EX-101.SCH": "XBRL taxonomy extension schema",
    "EX-101.CAL": "XBRL calculation linkbase",
    "EX-101.DEF": "XBRL definition linkbase",
    "EX-101.LAB": "XBRL label linkbase",
    "EX-101.PRE": "XBRL presentation linkbase",

    # Cover page and fees
    "EX-104": "Cover page interactive data file",
    "EX-107": "Filing fee table",
}
```

---

## Description Enhancement Algorithm

```
function enhance_description(attachment):
    # Step 1: Use purpose if available (from FilingSummary.xml)
    if attachment.purpose is not None and attachment.purpose != "":
        return attachment.purpose

    # Step 2: Use description if it's meaningful
    if attachment.description is not None and attachment.description != "":
        normalized_desc = attachment.description.strip().upper()
        normalized_type = attachment.document_type.strip().upper()
        if normalized_desc != normalized_type:
            return attachment.description

    # Step 3: Look up standard description by exhibit type
    doc_type = attachment.document_type
    if doc_type in EXHIBIT_DESCRIPTIONS:
        return EXHIBIT_DESCRIPTIONS[doc_type]

    # Step 4: Try base type fallback (EX-10.5 → EX-10)
    if "." in doc_type:
        base_type = doc_type.split(".")[0]
        if base_type in EXHIBIT_DESCRIPTIONS:
            return EXHIBIT_DESCRIPTIONS[base_type]

    # Step 5: No enhancement possible
    return attachment.description or ""
```

### Examples

| document_type | Raw description | Enhanced description | Source |
|---------------|----------------|---------------------|--------|
| `EX-3.B` | `EX-3.B` | Bylaws | Exact match in lookup |
| `EX-21` | `EX-21` | Subsidiaries of the registrant | Exact match in lookup |
| `EX-23` | `EX-23` | Consent of experts and counsel | Exact match in lookup |
| `EX-24` | `EX-24` | Power of attorney | Exact match in lookup |
| `EX-31.1` | `EX-31.1` | Certification of CEO pursuant to Section 302 | Exact match in lookup |
| `EX-10.N` | `EX-10.N` | Material contracts | Base type fallback (EX-10) |
| `EX-10.L` | `EX-10.L` | Material contracts | Base type fallback (EX-10) |
| `EX-10.5` | `Employment Agreement - CEO` | Employment Agreement - CEO | Original description is meaningful |
| `EX-101.SCH` | `XBRL TAXONOMY EXTENSION SCHEMA DOCUMENT` | XBRL TAXONOMY EXTENSION SCHEMA DOCUMENT | Original description is meaningful |
| `R8.htm` | *(empty)* | CONSOLIDATED BALANCE SHEETS | From `purpose` (FilingSummary) |

### Suffix Convention

Numeric suffixes on exhibit types (`.1`, `.2`, `.23`, etc.) are **sequential counters**, not semantic classifications:
- `EX-10.1`, `EX-10.2`, `EX-10.3` — Three different material contracts, filed in order
- `EX-23.1`, `EX-23.2` — Two different auditor consents (e.g., for different subsidiaries)
- `EX-31.1`, `EX-31.2` — CEO and CFO certifications (this is a known convention for 31/32)

Letter suffixes on exhibit types (`.A`, `.B`, etc.) **are** semantic:
- `EX-3.A` = Articles of incorporation
- `EX-3.B` = Bylaws

---

## Regulatory Reference

All exhibit type definitions are sourced from:

- **17 CFR § 229.601** — Regulation S-K, Item 601 (Exhibits)
- **EDGAR Filer Manual, Volume II** — Document type codes and filing requirements
- **SEC XBRL Guide** — Interactive data exhibit specifications (EX-101, EX-104)
