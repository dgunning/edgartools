"""
424B5/424B3 Filing Detailed Analyzer

This script performs detailed analysis of individual 424B5 and 424B3 prospectus filings
to identify extractable business information, HTML structure patterns, and variations.

Purpose:
- Document HTML structure and layout patterns
- Identify reliable extraction patterns for key fields
- Catalog table structures and section layouts
- Test new HTML parser capabilities
- Build extraction pattern catalog
"""

import json
import re
from pathlib import Path

import pandas as pd

from edgar import find
from edgar.documents import HTMLParser

# Load sample dataset
SAMPLE_DATASET_PATH = '/Users/dwight/PycharmProjects/edgartools/docs-internal/research/sec-filings/forms/424b/sample_dataset.csv'
OUTPUT_DIR = '/Users/dwight/PycharmProjects/edgartools/docs-internal/research/sec-filings/forms/424b/analysis'

class Filing424BAnalyzer:
    """Detailed analyzer for 424B5/424B3 filings."""

    def __init__(self, accession_number: str, form_type: str, company_name: str):
        self.accession_number = accession_number
        self.form_type = form_type
        self.company_name = company_name
        self.filing = None
        self.html = None
        self.document = None
        self.analysis_results = {}

    def load_filing(self):
        """Load filing from SEC."""
        print(f"\n{'='*80}")
        print(f"Loading filing: {self.company_name}")
        print(f"Accession: {self.accession_number}")
        print(f"Form: {self.form_type}")
        print(f"{'='*80}")

        # Use find to get filing
        filing = find(self.accession_number)
        if filing:
            self.filing = filing
            print("✓ Filing loaded successfully")
            return True
        else:
            print("✗ Failed to load filing")
            return False

    def extract_html(self):
        """Extract HTML content."""
        if not self.filing:
            return False

        try:
            self.html = self.filing.html()
            print(f"✓ HTML extracted (length: {len(self.html):,} chars)")
            return True
        except Exception as e:
            print(f"✗ HTML extraction failed: {e}")
            return False

    def parse_with_new_parser(self):
        """Parse HTML with new HTMLParser."""
        if not self.html:
            return False

        try:
            parser = HTMLParser()
            self.document = parser.parse(self.html)
            print("✓ Document parsed with HTMLParser")
            print(f"  - Metadata: {self.document.metadata}")
            return True
        except Exception as e:
            print(f"✗ Parsing failed: {e}")
            return False

    def analyze_cover_page(self):
        """Analyze cover page structure and content."""
        print("\n--- COVER PAGE ANALYSIS ---")

        if not self.html:
            return {}

        # Extract first 5000 characters as cover page
        cover_page = self.html[:5000]

        results = {}

        # 1. Offering Status (Preliminary vs Final)
        offering_status = "unknown"
        if re.search(r'PRELIMINARY\s+PROSPECTUS', cover_page, re.IGNORECASE):
            offering_status = "preliminary"
        elif re.search(r'PROSPECTUS\s+SUPPLEMENT', cover_page, re.IGNORECASE):
            offering_status = "final_supplement"
        elif 'PROSPECTUS' in cover_page.upper():
            offering_status = "final"

        results['offering_status'] = offering_status
        print(f"  Offering Status: {offering_status}")

        # 2. Rule Reference
        rule_pattern = r'Filed\s+Pursuant\s+to\s+Rule\s+(424\([a-z]\)\(\d+\))'
        rule_match = re.search(rule_pattern, cover_page, re.IGNORECASE)
        if rule_match:
            results['rule_reference'] = rule_match.group(1)
            print(f"  Rule Reference: {rule_match.group(1)}")

        # 3. Registration Number
        reg_pattern = r'Registration\s+(?:No\.?|Number)\s+(333-\d+)'
        reg_match = re.search(reg_pattern, cover_page, re.IGNORECASE)
        if reg_match:
            results['registration_number'] = reg_match.group(1)
            print(f"  Registration Number: {reg_match.group(1)}")

        # 4. Security Type
        security_patterns = [
            r'(\d{1,3}(?:,\d{3})*)\s+(?:shares\s+of\s+)?([Cc]ommon\s+[Ss]tock)',
            r'([Pp]referred\s+[Ss]tock)',
            r'(\$[\d,]+\s+(?:principal\s+amount\s+of\s+)?[Nn]otes)',
            r'([Ww]arrants)',
        ]

        for pattern in security_patterns:
            match = re.search(pattern, cover_page)
            if match:
                results['security_type'] = match.group(0)
                print(f"  Security Type: {match.group(0)}")
                break

        # 5. Offering Amount
        amount_patterns = [
            r'\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|Million|MILLION)',
            r'\$\s*([\d,]+)',
        ]

        for pattern in amount_patterns:
            match = re.search(pattern, cover_page)
            if match:
                results['offering_amount'] = match.group(0)
                print(f"  Offering Amount: {match.group(0)}")
                break

        # 6. ATM Indicator
        atm_keywords = ['at-the-market', 'ATM offering', 'at the market']
        is_atm = any(keyword.lower() in cover_page.lower() for keyword in atm_keywords)
        results['is_atm'] = is_atm
        print(f"  ATM Offering: {is_atm}")

        self.analysis_results['cover_page'] = results
        return results

    def analyze_tables(self):
        """Analyze table structures in the document."""
        print("\n--- TABLE ANALYSIS ---")

        if not self.document:
            return []

        tables = self.document.tables
        print(f"  Total tables found: {len(tables)}")

        table_info = []
        for i, table in enumerate(tables[:10]):  # Analyze first 10 tables
            info = {
                'index': i,
                'rows': len(table.rows) if hasattr(table, 'rows') else 'unknown',
                'columns': len(table.columns) if hasattr(table, 'columns') else 'unknown',
                'caption': getattr(table, 'caption', None),
            }

            # Try to identify table type based on content
            table_text = str(table)[:200].lower()
            if 'offering' in table_text and ('price' in table_text or 'shares' in table_text):
                info['likely_type'] = 'offering_terms'
            elif 'selling' in table_text and 'shareholder' in table_text:
                info['likely_type'] = 'selling_shareholders'
            elif 'underwriter' in table_text or 'underwriting' in table_text:
                info['likely_type'] = 'underwriting'
            elif 'dilution' in table_text:
                info['likely_type'] = 'dilution'
            else:
                info['likely_type'] = 'other'

            table_info.append(info)

            print(f"  Table {i}: {info['rows']}x{info['columns']} - Type: {info.get('likely_type', 'unknown')}")
            if info.get('caption'):
                print(f"    Caption: {info['caption'][:100]}")

        self.analysis_results['tables'] = table_info
        return table_info

    def analyze_sections(self):
        """Analyze major sections in the document."""
        print("\n--- SECTION ANALYSIS ---")

        if not self.document:
            return []

        # Try to identify major sections
        html_lower = self.html.lower() if self.html else ""

        sections_found = []

        # Common section headers
        section_patterns = [
            r'(?:offering|issuance)\s+terms',
            r'use\s+of\s+proceeds',
            r'underwriting',
            r'selling\s+shareholders?',
            r'dilution',
            r'risk\s+factors',
            r'plan\s+of\s+distribution',
            r'description\s+of\s+(?:capital\s+stock|securities)',
        ]

        for pattern in section_patterns:
            match = re.search(pattern, html_lower)
            if match:
                clean_pattern = pattern.replace(r'\s+', ' ')
                sections_found.append(clean_pattern)
                print(f"  ✓ Found section: {clean_pattern}")

        self.analysis_results['sections'] = sections_found
        return sections_found

    def analyze_424b5_specific(self):
        """Analyze 424B5-specific fields (new issuance)."""
        if self.form_type != '424B5':
            return {}

        print("\n--- 424B5-SPECIFIC ANALYSIS (New Issuance) ---")

        results = {}

        if not self.html:
            return results

        html_lower = self.html.lower()

        # Look for underwriting section
        has_underwriting = 'underwriting' in html_lower
        results['has_underwriting_section'] = has_underwriting
        print(f"  Has Underwriting Section: {has_underwriting}")

        # Look for lead underwriters (typically first few names after "Underwriting" header)
        if has_underwriting:
            # Extract section around "underwriting"
            underwriting_idx = html_lower.find('underwriting')
            underwriting_section = self.html[underwriting_idx:underwriting_idx+5000]

            # Look for common financial institution names
            financial_institutions = [
                'Goldman Sachs',
                'Morgan Stanley',
                'JP Morgan',
                'BofA Securities',
                'Citigroup',
                'Jefferies',
                'Barclays',
                'Wells Fargo',
            ]

            found_underwriters = []
            for institution in financial_institutions:
                if institution.lower() in underwriting_section.lower():
                    found_underwriters.append(institution)

            results['potential_underwriters'] = found_underwriters
            if found_underwriters:
                print(f"  Potential Underwriters Found: {', '.join(found_underwriters)}")

        # Look for offering price patterns
        price_patterns = [
            r'offering\s+price[:\s]+\$\s*[\d,.]+',
            r'price\s+to\s+public[:\s]+\$\s*[\d,.]+',
        ]

        for pattern in price_patterns:
            match = re.search(pattern, html_lower)
            if match:
                results['offering_price_pattern'] = match.group(0)
                print(f"  Offering Price Pattern: {match.group(0)}")
                break

        self.analysis_results['424b5_specific'] = results
        return results

    def analyze_424b3_specific(self):
        """Analyze 424B3-specific fields (resale registration)."""
        if self.form_type != '424B3':
            return {}

        print("\n--- 424B3-SPECIFIC ANALYSIS (Resale Registration) ---")

        results = {}

        if not self.html:
            return results

        html_lower = self.html.lower()

        # Look for selling shareholders section
        has_selling_shareholders = 'selling' in html_lower and 'shareholder' in html_lower
        results['has_selling_shareholders_section'] = has_selling_shareholders
        print(f"  Has Selling Shareholders Section: {has_selling_shareholders}")

        # Look for PIPE indicator
        pipe_keywords = ['pipe', 'private investment in public equity', 'private placement']
        is_pipe = any(keyword in html_lower for keyword in pipe_keywords)
        results['likely_pipe_offering'] = is_pipe
        print(f"  Likely PIPE Offering: {is_pipe}")

        # Look for resale-related terminology
        resale_keywords = ['resale', 'secondary offering', 'registrant is not selling']
        has_resale_language = any(keyword in html_lower for keyword in resale_keywords)
        results['has_resale_language'] = has_resale_language
        print(f"  Has Resale Language: {has_resale_language}")

        # Count potential selling shareholders (rough estimate)
        # Look for patterns like "Name of Selling Shareholder" in tables
        shareholder_count_estimate = html_lower.count('selling shareholder')
        results['shareholder_mentions'] = shareholder_count_estimate
        print(f"  'Selling Shareholder' Mentions: {shareholder_count_estimate}")

        self.analysis_results['424b3_specific'] = results
        return results

    def generate_summary(self):
        """Generate analysis summary."""
        print(f"\n{'='*80}")
        print(f"ANALYSIS SUMMARY: {self.company_name}")
        print(f"{'='*80}")

        summary = {
            'accession_number': self.accession_number,
            'form_type': self.form_type,
            'company_name': self.company_name,
            'analysis_date': pd.Timestamp.now().isoformat(),
            'html_length': len(self.html) if self.html else 0,
            'results': self.analysis_results
        }

        # Print key findings
        if 'cover_page' in self.analysis_results:
            cp = self.analysis_results['cover_page']
            print("\nCover Page Extraction:")
            print(f"  - Offering Status: {cp.get('offering_status', 'N/A')}")
            print(f"  - Registration Number: {cp.get('registration_number', 'N/A')}")
            print(f"  - Security Type: {cp.get('security_type', 'N/A')}")
            print(f"  - Is ATM: {cp.get('is_atm', 'N/A')}")

        if 'tables' in self.analysis_results:
            print("\nTable Analysis:")
            print(f"  - Total Tables: {len(self.analysis_results['tables'])}")
            table_types = [t.get('likely_type', 'unknown') for t in self.analysis_results['tables']]
            print(f"  - Table Types: {set(table_types)}")

        if 'sections' in self.analysis_results:
            print(f"\nSections Found: {len(self.analysis_results['sections'])}")
            for section in self.analysis_results['sections']:
                print(f"  - {section}")

        print(f"\n{'='*80}\n")

        return summary

    def save_analysis(self, output_dir: str):
        """Save analysis results to JSON file."""
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        filename = f"{self.form_type}_{self.accession_number.replace('-', '_')}.json"
        filepath = Path(output_dir) / filename

        summary = self.generate_summary()

        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"Analysis saved to: {filepath}")
        return filepath

    def run_full_analysis(self):
        """Run complete analysis pipeline."""
        # Load filing
        if not self.load_filing():
            return None

        # Extract HTML
        if not self.extract_html():
            return None

        # Parse with new parser
        self.parse_with_new_parser()

        # Analyze components
        self.analyze_cover_page()
        self.analyze_tables()
        self.analyze_sections()

        # Form-specific analysis
        if self.form_type == '424B5':
            self.analyze_424b5_specific()
        elif self.form_type == '424B3':
            self.analyze_424b3_specific()

        # Generate and save summary
        return self.generate_summary()


def analyze_representative_sample():
    """Analyze a representative subset of filings."""
    # Load sample dataset
    df = pd.read_csv(SAMPLE_DATASET_PATH)

    # Select representative filings for detailed analysis
    # Priority: Recent 424B5, Recent 424B3, Historical samples

    representative_filings = [
        # Recent 424B5 - biotech
        ('0001104659-24-041120', '424B5', 'Adagene Inc.'),
        # Recent 424B5 - multiple filings by same company
        ('0001104659-24-103798', '424B5', 'EYENOVIA, INC.'),
        # 2022 424B5 - mid-period
        ('0001193125-22-315109', '424B5', 'AMYRIS, INC.'),
        # 2020 424B5 - historical
        ('0001178913-20-003490', '424B5', 'BioLineRx Ltd.'),
        # Recent 424B3 - PIPE/resale
        ('0001104659-24-132173', '424B3', 'Oklo Inc.'),
        # 2022 424B3
        ('0001213900-22-083978', '424B3', 'MESOBLAST LTD'),
        # 2020 424B3 - high-profile
        ('0001104659-20-139163', '424B3', 'Nikola Corp'),
    ]

    results = []

    for accession, form_type, company_name in representative_filings:
        print(f"\n\n{'#'*80}")
        print(f"# ANALYZING: {company_name} ({form_type})")
        print(f"{'#'*80}\n")

        analyzer = Filing424BAnalyzer(accession, form_type, company_name)

        try:
            summary = analyzer.run_full_analysis()
            if summary:
                analyzer.save_analysis(OUTPUT_DIR)
                results.append(summary)
        except Exception as e:
            print(f"ERROR analyzing {company_name}: {e}")
            import traceback
            traceback.print_exc()

        # Rate limiting
        import time
        time.sleep(1)

    # Save combined results
    combined_path = Path(OUTPUT_DIR) / 'combined_analysis.json'
    with open(combined_path, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*80}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*80}")
    print(f"  Total filings analyzed: {len(results)}")
    print(f"  Results saved to: {OUTPUT_DIR}")
    print(f"  Combined results: {combined_path}")
    print(f"{'='*80}\n")

    return results


if __name__ == "__main__":
    results = analyze_representative_sample()
