"""
Comprehensive Extractor Testing Script

Tests all prototype extractors on the full 35-filing sample dataset and
generates success rate statistics and failure analysis.

Week 2 Research - 424B5/424B3 Data Extraction Feasibility Assessment
"""

import csv
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

# Import our extractors
from cover_page_extractors import CoverPageExtractor
from table_extractors import OfferingTermsExtractor, SellingShareholderExtractor, UnderwriterExtractor


class ExtractorTester:
    """Test extractors on sample dataset and collect statistics."""

    def __init__(self, sample_csv_path: str):
        """
        Initialize tester with sample dataset.

        Args:
            sample_csv_path: Path to sample_dataset.csv
        """
        self.sample_csv_path = sample_csv_path
        self.results = []
        self.stats = defaultdict(lambda: {'success': 0, 'total': 0, 'failures': []})

    def load_sample_dataset(self) -> List[Dict[str, str]]:
        """Load sample dataset from CSV."""
        samples = []
        with open(self.sample_csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                samples.append(row)
        return samples

    def test_single_filing(self, filing_info: Dict[str, str]) -> Dict[str, Any]:
        """
        Test all extractors on a single filing.

        Args:
            filing_info: Dict with accession_number, form, company_name, etc.

        Returns:
            Dictionary with extraction results
        """
        accession_number = filing_info['accession_number']
        form = filing_info['form']
        company_name = filing_info['company_name']

        print(f"\nTesting: {company_name} ({form}) - {accession_number}")

        result = {
            'accession_number': accession_number,
            'form': form,
            'company_name': company_name,
            'filing_date': filing_info.get('filing_date'),
            'test_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'extraction_results': {},
            'errors': []
        }

        try:
            # Load filing using find() - most direct method
            from edgar import find
            from edgar.documents.parser import HTMLParser

            filing = find(accession_number)
            if not filing:
                raise Exception(f"Filing not found: {accession_number}")

            html = filing.html()

            # Parse document using HTMLParser
            parser = HTMLParser()
            document = parser.parse(html)

            # Test cover page extractors
            print("  - Testing cover page extractors...")
            cover_extractor = CoverPageExtractor(html)
            result['extraction_results']['cover_page'] = cover_extractor.extract_all()

            # Test form-specific extractors
            if form == '424B5':
                print("  - Testing 424B5-specific extractors (underwriters)...")

                # Underwriter extraction
                underwriter_extractor = UnderwriterExtractor(html, document)
                result['extraction_results']['underwriters'] = underwriter_extractor.extract_all()

                # Offering terms
                terms_extractor = OfferingTermsExtractor(html, document)
                result['extraction_results']['offering_terms'] = terms_extractor.extract_all()

            elif form == '424B3':
                print("  - Testing 424B3-specific extractors (selling shareholders)...")

                # Selling shareholder extraction
                shareholder_extractor = SellingShareholderExtractor(html, document)
                result['extraction_results']['selling_shareholders'] = shareholder_extractor.extract_all()

            print("  ✓ Extraction complete")

        except Exception as e:
            error_msg = f"Error processing filing: {str(e)}"
            print(f"  ✗ {error_msg}")
            result['errors'].append(error_msg)

        return result

    def calculate_field_success(self, field_path: List[str], value: Any) -> bool:
        """
        Determine if a field extraction was successful.

        Args:
            field_path: Path to field (e.g., ['cover_page', 'offering_amount', 'amount'])
            value: Extracted value

        Returns:
            True if extraction successful, False otherwise
        """
        # Check if value exists and is not None
        if value is None:
            return False

        # For dict results, check confidence or specific success indicators
        if isinstance(value, dict):
            # Check confidence level
            confidence = value.get('confidence')
            if confidence in ['High', 'Medium']:
                # Also check if key field has actual data
                if 'amount' in value:
                    return value['amount'] is not None
                elif 'security_type' in value:
                    return value['security_type'] is not None
                elif 'price' in value:
                    return value['price'] is not None
                elif 'share_count' in value:
                    return value['share_count'] is not None
                elif 'registration_number' in value:
                    return value['registration_number'] is not None
                elif 'is_atm' in value:
                    return True  # Boolean fields always have a value
                elif 'underwriters' in value:
                    return len(value['underwriters']) > 0
                elif 'shareholders' in value:
                    return len(value['shareholders']) > 0
                elif 'section_found' in value:
                    return value['section_found'] is True
                elif 'has_greenshoe' in value:
                    return True  # Boolean fields always have a value
                else:
                    return confidence in ['High', 'Medium']
            return False

        # For list results
        if isinstance(value, list):
            return len(value) > 0

        # For boolean results
        if isinstance(value, bool):
            return True  # Booleans always have a value

        # For string/number results
        return bool(value)

    def update_statistics(self, results: List[Dict[str, Any]]):
        """
        Calculate success statistics for each field.

        Args:
            results: List of extraction results
        """
        # Define fields to track
        fields_to_track = {
            'cover_page.offering_amount': ['cover_page', 'offering_amount'],
            'cover_page.security_type': ['cover_page', 'security_type'],
            'cover_page.offering_price': ['cover_page', 'offering_price'],
            'cover_page.share_count': ['cover_page', 'share_count'],
            'cover_page.gross_proceeds': ['cover_page', 'gross_proceeds'],
            'cover_page.net_proceeds': ['cover_page', 'net_proceeds'],
            'cover_page.registration_number': ['cover_page', 'registration_number'],
            'cover_page.atm_indicator': ['cover_page', 'atm_indicator'],

            # 424B5 specific
            'underwriters.from_section': ['underwriters', 'from_section'],
            'underwriters.from_table': ['underwriters', 'from_table'],
            'underwriters.discount': ['underwriters', 'underwriting_discount'],
            'offering_terms.greenshoe': ['offering_terms', 'greenshoe'],

            # 424B3 specific
            'selling_shareholders.section': ['selling_shareholders', 'section_detection'],
            'selling_shareholders.table': ['selling_shareholders', 'table_extraction'],
            'selling_shareholders.resale_amount': ['selling_shareholders', 'resale_amount'],
        }

        for result in results:
            form = result['form']
            extraction_results = result.get('extraction_results', {})

            for field_name, field_path in fields_to_track.items():
                # Check if field is applicable to this form
                if form == '424B5' and field_name.startswith('selling_shareholders'):
                    continue
                if form == '424B3' and field_name.startswith('underwriters'):
                    continue
                if form == '424B3' and field_name.startswith('offering_terms'):
                    continue

                # Navigate to field value
                value = extraction_results
                try:
                    for key in field_path:
                        value = value[key]
                except (KeyError, TypeError):
                    value = None

                # Check success
                is_success = self.calculate_field_success(field_path, value)

                # Update statistics
                stat_key = f"{form}.{field_name}"
                self.stats[stat_key]['total'] += 1

                if is_success:
                    self.stats[stat_key]['success'] += 1
                else:
                    self.stats[stat_key]['failures'].append({
                        'accession_number': result['accession_number'],
                        'company_name': result['company_name'],
                        'extracted_value': value
                    })

    def generate_success_rate_matrix(self) -> List[Dict[str, Any]]:
        """
        Generate success rate matrix for all fields.

        Returns:
            List of dicts with field statistics
        """
        matrix = []

        for stat_key, stat_data in sorted(self.stats.items()):
            form, field = stat_key.split('.', 1)
            total = stat_data['total']
            success = stat_data['success']
            success_rate = (success / total * 100) if total > 0 else 0

            # Determine reliability
            if success_rate >= 80:
                reliability = 'High'
            elif success_rate >= 60:
                reliability = 'Medium'
            else:
                reliability = 'Low'

            matrix.append({
                'form': form,
                'field': field,
                'success_count': success,
                'total_count': total,
                'success_rate_pct': round(success_rate, 1),
                'reliability': reliability,
                'failure_count': total - success
            })

        return matrix

    def run_full_test(self, output_dir: str):
        """
        Run complete test suite on all sample filings.

        Args:
            output_dir: Directory to save results
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        print("=" * 80)
        print("424B5/424B3 EXTRACTOR TESTING - FULL SAMPLE DATASET")
        print("=" * 80)

        # Load sample dataset
        samples = self.load_sample_dataset()
        print(f"\nLoaded {len(samples)} sample filings")
        print(f"  - 424B5: {sum(1 for s in samples if s['form'] == '424B5')}")
        print(f"  - 424B3: {sum(1 for s in samples if s['form'] == '424B3')}")

        # Test each filing
        print("\nTesting extractors on all filings...")
        print("-" * 80)

        for i, sample in enumerate(samples, 1):
            print(f"\n[{i}/{len(samples)}]", end=' ')
            result = self.test_single_filing(sample)
            self.results.append(result)

            # Small delay to avoid rate limiting
            time.sleep(0.5)

        # Calculate statistics
        print("\n" + "=" * 80)
        print("CALCULATING STATISTICS...")
        print("=" * 80)

        self.update_statistics(self.results)

        # Generate success rate matrix
        matrix = self.generate_success_rate_matrix()

        # Save detailed results
        results_file = output_path / 'detailed_extraction_results.json'
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\n✓ Detailed results saved to: {results_file}")

        # Save success rate matrix
        matrix_file = output_path / 'success_rates.json'
        with open(matrix_file, 'w') as f:
            json.dump(matrix, f, indent=2)
        print(f"✓ Success rate matrix saved to: {matrix_file}")

        # Save success rate matrix as CSV
        matrix_csv = output_path / 'success_rates.csv'
        with open(matrix_csv, 'w', newline='') as f:
            if matrix:
                writer = csv.DictWriter(f, fieldnames=matrix[0].keys())
                writer.writeheader()
                writer.writerows(matrix)
        print(f"✓ Success rate CSV saved to: {matrix_csv}")

        # Save failure analysis
        failures_file = output_path / 'failure_analysis.json'
        failures = {k: v['failures'] for k, v in self.stats.items() if v['failures']}
        with open(failures_file, 'w') as f:
            json.dump(failures, f, indent=2)
        print(f"✓ Failure analysis saved to: {failures_file}")

        # Print summary
        print("\n" + "=" * 80)
        print("EXTRACTION SUCCESS RATE SUMMARY")
        print("=" * 80)

        # Group by form
        for form in ['424B5', '424B3']:
            form_stats = [m for m in matrix if m['form'] == form]
            if form_stats:
                print(f"\n{form} Fields:")
                print(f"{'Field':<40} {'Success Rate':<15} {'Reliability':<12} {'Count'}")
                print("-" * 80)
                for stat in form_stats:
                    field = stat['field']
                    rate = f"{stat['success_rate_pct']}%"
                    reliability = stat['reliability']
                    count = f"{stat['success_count']}/{stat['total_count']}"
                    print(f"{field:<40} {rate:<15} {reliability:<12} {count}")

        # Overall statistics
        print("\n" + "=" * 80)
        print("OVERALL STATISTICS")
        print("=" * 80)

        high_success = [m for m in matrix if m['reliability'] == 'High']
        medium_success = [m for m in matrix if m['reliability'] == 'Medium']
        low_success = [m for m in matrix if m['reliability'] == 'Low']

        print(f"\nHigh Reliability (≥80%): {len(high_success)} fields")
        print(f"Medium Reliability (60-79%): {len(medium_success)} fields")
        print(f"Low Reliability (<60%): {len(low_success)} fields")

        avg_success_rate = sum(m['success_rate_pct'] for m in matrix) / len(matrix) if matrix else 0
        print(f"\nAverage Success Rate: {avg_success_rate:.1f}%")

        print("\n" + "=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)


if __name__ == '__main__':
    # Run full test suite
    sample_csv = '/Users/dwight/PycharmProjects/edgartools/docs-internal/research/sec-filings/forms/424b/sample_dataset.csv'
    output_dir = '/Users/dwight/PycharmProjects/edgartools/docs-internal/research/sec-filings/forms/424b/results'

    tester = ExtractorTester(sample_csv)
    tester.run_full_test(output_dir)
