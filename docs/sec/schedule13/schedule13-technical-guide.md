# SEC Schedule 13D and 13G Technical Guide

> Based on EDGAR Schedule 13D and 13G XML Technical Specification v1.0 (December 2023)

## Overview

Schedule 13D and 13G are SEC filings that report beneficial ownership of equity securities. These filings are required when a person or group acquires more than 5% of a class of equity securities.

### Filing Types

| Submission Type | Description |
|-----------------|-------------|
| `SCHEDULE 13D` | Report acquisition of beneficial ownership of more than 5% of certain classes of equity securities |
| `SCHEDULE 13D/A` | Amendment to Schedule 13D |
| `SCHEDULE 13G` | Report beneficial ownership of more than 5% by passive, qualified institutional, or exempt investors |
| `SCHEDULE 13G/A` | Amendment to Schedule 13G |

### Key Difference: 13D vs 13G

- **Schedule 13D**: Required for investors who acquire >5% with intent to influence or control the company
- **Schedule 13G**: Shorter form available to passive investors, qualified institutional investors, or exempt investors who acquire >5% without intent to influence control

## XML Submission Structure

Both Schedule 13D and 13G submissions are XML documents that must conform to EDGAR schemas. The high-level structure is:

```xml
<?xml version="1.0"?>
<edgarSubmission xmlns="http://www.sec.gov/edgar/schedule13d"
                 xmlns:com="http://www.sec.gov/edgar/common">
    <headerData>
        <!-- Submission metadata and filer credentials -->
    </headerData>
    <formData>
        <!-- Cover page, reporting persons, items, signatures -->
    </formData>
    <documents>
        <!-- Optional attached documents -->
    </documents>
</edgarSubmission>
```

## Schema Files

The EDGAR system uses these XSD schema files for validation:

| Schema File | Purpose |
|-------------|---------|
| `eis_Schedule13D_Filer.xsd` | Defines elements for Schedule 13D submissions |
| `eis_Schedule13G_Filer.xsd` | Defines elements for Schedule 13G submissions |
| `eis_Common.xsd` | Common submission fields across all EDGAR submissions |
| `eis_stateCodes.xsd` | Valid state and country codes |

## Namespaces

- **Schedule 13D**: `http://www.sec.gov/edgar/schedule13d`
- **Schedule 13G**: `http://www.sec.gov/edgar/schedule13g`
- **Common elements**: `http://www.sec.gov/edgar/common`

## Data Types

| Type | Constraints |
|------|-------------|
| `Boolean` | `"true"`, `"false"`, `"1"`, or `"0"`. Cannot be null/blank |
| `date` | Format: `MM-DD-YYYY`. Cannot be null/blank |
| `integer` | Digits 0-9 only. No commas, minus, dollar signs, parentheses |
| `string` | Must escape: `<` as `&lt;`, `>` as `&gt;`, `&` as `&amp;`, `"` as `&quot;` |
| `decimal` | Non-negative decimal values (e.g., `14,2` = 14 digits, 2 decimal places) |

## Element Applicability Legend

| Code | Meaning |
|------|---------|
| `m` | Mandatory |
| `m#` | Conditional mandatory (mandatory if parent is included) |
| `m#1` | Conditional mandatory based on other element values |
| `o` | Optional |
| `o#` | Optional in schema; EDGAR populates value |
| `NA` | Does not apply; used for server-side processing |

## Related Files

- [Schema Reference](schema-reference.md) - Detailed XML element specifications
- [Data Value Codes](data-value-codes.md) - Enumerated values and codes
- [XML Examples](xml-examples.md) - Complete example submissions

## Transmission

Submissions can be transmitted via:
- **EDGAR FilerWeb**: https://www.edgarfiling.sec.gov/
- **OnlineForms/XML Website**: https://www.onlineforms.edgarfiling.sec.gov (use "Transmit XML Submission")

### Requirements
- Must have a CIK (Central Index Key)
- Must have EDGAR access codes (password, CCC)

## File Formatting Rules

1. Filename must end with `.xml` extension
2. File cannot be compressed
3. Use indentation for readability (strongly recommended)
4. `<?xml version="1.0"?>` declaration is optional but must be first line if included
5. Keep begin tag, data value, and end tag on same line:
   ```xml
   <!-- Correct -->
   <cik>1212121212</cik>

   <!-- Incorrect - will cause parsing errors -->
   <cik>
   1212121212
   </cik>
   ```

## Document Attachments

### Allowed File Extensions
- `.pdf`
- `.txt`
- `.htm`
- `.xml`

### File Naming Rules
- Maximum 32 characters including extension
- Valid characters: lowercase letters, digits 0-9, one underscore, one hyphen, one period
- First character must be a letter
- No spaces allowed

### Document Encoding
Document contents must be MIME/Base64 encoded in the `<contents>` element:

```xml
<documents>
    <com:document>
        <com:conformedName>exhibit.pdf</com:conformedName>
        <com:conformedDocumentType>EX-99</com:conformedDocumentType>
        <com:description>Supporting exhibit</com:description>
        <com:contents>YXNkZmY=</com:contents>
    </com:document>
</documents>
```

## Error Handling

Submissions that violate schema constraints or business rules will be:
- **SUSPENDED**: Serious errors (schema violations, invalid values, missing mandatory fields)
- **WARNING**: Minor issues (duplicate notification addresses)

### Common Suspension Causes
- Elements not in prescribed sequence
- String values exceeding maximum length
- Invalid choice list values
- Missing mandatory element values
- Special characters not escaped
- Invalid CIK
- Duplicate reporting person names
- Signature mismatches with reporting persons

See [Schema Reference](schema-reference.md) for detailed element constraints.
