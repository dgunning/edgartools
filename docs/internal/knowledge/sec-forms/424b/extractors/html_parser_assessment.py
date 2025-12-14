"""
HTML Parser Capability Assessment

Evaluate the new HTML parser's ability to extract tables, detect sections,
and handle complex 424B prospectus filing structures.

Week 2 Research - 424B5/424B3 Data Extraction Feasibility Assessment
"""

import json
from typing import Any, Dict, List

from edgar import find
from edgar.documents.parser import HTMLParser


def assess_table_extraction(accession_number: str, company_name: str, form: str) -> Dict[str, Any]:
    """
    Assess table extraction quality for a filing.

    Args:
        accession_number: Filing accession number
        company_name: Company name for display
        form: Form type (424B5 or 424B3)

    Returns:
        Dict with table assessment results
    """
    print(f"\nAssessing: {company_name} ({form})")

    filing = find(accession_number)
    html = filing.html()

    parser = HTMLParser()
    document = parser.parse(html)

    assessment = {
        'accession_number': accession_number,
        'company_name': company_name,
        'form': form,
        'table_count': len(document.tables),
        'tables': []
    }

    # Analyze each table
    for i, table in enumerate(document.tables):
        table_info = {
            'table_index': i,
            'row_count': len(table.rows),
            'has_caption': False,  # TODO: Check if caption exists
            'sample_cells': [],
            'structure_quality': 'Unknown'
        }

        # Get sample cells from first 2 rows
        for row_idx, row in enumerate(table.rows[:2]):
            for cell_idx, cell in enumerate(row.cells[:5]):  # First 5 cells
                cell_text = str(cell).strip()[:100]  # First 100 chars
                table_info['sample_cells'].append({
                    'row': row_idx,
                    'col': cell_idx,
                    'text': cell_text
                })

        # Try to identify table purpose based on content
        table_text = ' '.join([str(cell) for row in table.rows for cell in row.cells]).lower()

        if 'underwriter' in table_text or 'book-running' in table_text:
            table_info['likely_type'] = 'underwriting'
        elif 'selling shareholder' in table_text or 'selling stockholder' in table_text:
            table_info['likely_type'] = 'selling_shareholders'
        elif 'dilution' in table_text:
            table_info['likely_type'] = 'dilution'
        elif 'capitalization' in table_text:
            table_info['likely_type'] = 'capitalization'
        elif 'use of proceeds' in table_text:
            table_info['likely_type'] = 'use_of_proceeds'
        else:
            table_info['likely_type'] = 'other'

        assessment['tables'].append(table_info)

    return assessment


def assess_section_detection(accession_number: str, company_name: str, form: str) -> Dict[str, Any]:
    """
    Assess section detection accuracy.

    Args:
        accession_number: Filing accession number
        company_name: Company name for display
        form: Form type (424B5 or 424B3)

    Returns:
        Dict with section detection results
    """
    print(f"\nSection detection: {company_name} ({form})")

    filing = find(accession_number)
    html = filing.html()

    parser = HTMLParser()
    document = parser.parse(html)

    # Expected sections by form type
    expected_sections = {
        '424B5': [
            'use of proceeds',
            'underwriting',
            'dilution',
            'risk factors',
            'plan of distribution',
            'description of'
        ],
        '424B3': [
            'selling shareholders',
            'selling stockholders',
            'risk factors',
            'plan of distribution'
        ]
    }

    # Check for sections in document
    html_lower = html.lower()
    sections_found = []

    for section in expected_sections.get(form, []):
        if section in html_lower:
            sections_found.append(section)

    assessment = {
        'accession_number': accession_number,
        'company_name': company_name,
        'form': form,
        'expected_sections': expected_sections[form],
        'sections_found': sections_found,
        'detection_rate': len(sections_found) / len(expected_sections[form]) * 100
    }

    return assessment


def run_html_parser_assessment():
    """Run comprehensive HTML parser assessment on sample filings."""

    print("=" * 80)
    print("HTML PARSER CAPABILITY ASSESSMENT")
    print("=" * 80)

    # Test filings: Mix of 424B5 and 424B3
    test_filings = [
        # 424B5 filings
        ('0001104659-24-041120', 'Adagene Inc.', '424B5'),
        ('0001140361-24-031669', 'Jefferies Financial Group Inc.', '424B5'),
        ('0001104659-24-103798', 'EYENOVIA, INC.', '424B5'),

        # 424B3 filings
        ('0001213900-24-113730', 'ADIAL PHARMACEUTICALS, INC.', '424B3'),
        ('0001104659-24-132173', 'Oklo Inc.', '424B3'),
        ('0001839882-24-047337', 'UBS AG', '424B3'),
    ]

    # Table extraction assessment
    print("\n" + "=" * 80)
    print("TABLE EXTRACTION ASSESSMENT")
    print("=" * 80)

    table_assessments = []
    for accession, company, form in test_filings:
        assessment = assess_table_extraction(accession, company, form)
        table_assessments.append(assessment)

        print(f"  Tables found: {assessment['table_count']}")
        table_types = [t['likely_type'] for t in assessment['tables']]
        print(f"  Table types: {table_types}")

    # Section detection assessment
    print("\n" + "=" * 80)
    print("SECTION DETECTION ASSESSMENT")
    print("=" * 80)

    section_assessments = []
    for accession, company, form in test_filings:
        assessment = assess_section_detection(accession, company, form)
        section_assessments.append(assessment)

        print(f"  Detection rate: {assessment['detection_rate']:.1f}%")
        print(f"  Sections found: {assessment['sections_found']}")

    # Save results
    results = {
        'table_assessments': table_assessments,
        'section_assessments': section_assessments
    }

    output_file = '/Users/dwight/PycharmProjects/edgartools/docs-internal/research/sec-filings/forms/424b/results/html_parser_assessment.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n✓ HTML parser assessment saved to: {output_file}")

    # Summary statistics
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)

    avg_table_count = sum(a['table_count'] for a in table_assessments) / len(table_assessments)
    print(f"\nAverage tables per filing: {avg_table_count:.1f}")

    b5_tables = [a['table_count'] for a in table_assessments if a['form'] == '424B5']
    b3_tables = [a['table_count'] for a in table_assessments if a['form'] == '424B3']
    print(f"424B5 average tables: {sum(b5_tables) / len(b5_tables):.1f}")
    print(f"424B3 average tables: {sum(b3_tables) / len(b3_tables):.1f}")

    avg_detection = sum(a['detection_rate'] for a in section_assessments) / len(section_assessments)
    print(f"\nAverage section detection rate: {avg_detection:.1f}%")

    # Table type distribution
    all_table_types = [t['likely_type'] for a in table_assessments for t in a['tables']]
    type_counts = {}
    for t_type in all_table_types:
        type_counts[t_type] = type_counts.get(t_type, 0) + 1

    print("\nTable type distribution:")
    for t_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {t_type}: {count}")

    print("\n" + "=" * 80)
    print("ASSESSMENT COMPLETE")
    print("=" * 80)


if __name__ == '__main__':
    run_html_parser_assessment()
