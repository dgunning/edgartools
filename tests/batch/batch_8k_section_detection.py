"""
Batch test: 8-K section detection validation across diverse filings.

Tests section detection on a large sample of 8-K filings from multiple years
to validate the regex pattern and confidence score fixes (Issue edgartools-1ho).

Run with:
    python tests/batch/batch_8k_section_detection.py
    python tests/batch/batch_8k_section_detection.py --sample-size 50
    python tests/batch/batch_8k_section_detection.py --years 2020 2021 2022 2023 2024
"""
import argparse
from typing import Dict, List, Any
from edgar import get_filings
from edgar.documents import parse_html
from edgar.documents.config import ParserConfig
from tqdm.auto import tqdm


def test_8k_section_detection(
    years: List[int] = None,
    sample_size: int = 20
) -> Dict[str, Any]:
    """
    Test 8-K section detection on a sample of filings.

    Args:
        years: List of years to sample from (default: [2020, 2023])
        sample_size: Number of filings to sample per year

    Returns:
        Dictionary with test results
    """
    if years is None:
        years = [2020, 2023]

    print(f"\n{'='*80}")
    print(f"8-K Section Detection Batch Test")
    print(f"{'='*80}")
    print(f"Years: {years}")
    print(f"Sample size per year: {sample_size}")
    print(f"Total filings to test: {len(years) * sample_size}")
    print(f"{'='*80}\n")

    results = {
        "total": 0,
        "success": 0,
        "no_sections": 0,
        "parse_errors": 0,
        "download_errors": 0,
        "filings_with_sections": [],
        "filings_without_sections": [],
        "errors": [],
        "section_counts": {}
    }

    for year in years:
        print(f"\nFetching {sample_size} random 8-K filings from {year}...")
        try:
            filings = get_filings(form="8-K", year=year).sample(sample_size)
        except Exception as e:
            print(f"❌ Error fetching filings for {year}: {e}")
            results["errors"].append({
                "year": year,
                "error": str(e),
                "type": "fetch"
            })
            continue

        print(f"Testing {len(filings)} filings from {year}...\n")

        for filing in tqdm(filings, desc=f"Year {year}"):
            results["total"] += 1

            try:
                # Download HTML
                try:
                    html = filing.document.download()
                except Exception as e:
                    results["download_errors"] += 1
                    results["errors"].append({
                        "company": filing.company,
                        "accession": filing.accession_no,
                        "date": str(filing.filing_date),
                        "error": str(e),
                        "type": "download"
                    })
                    continue

                # Parse with ParserConfig
                try:
                    config = ParserConfig(form='8-K')
                    doc = parse_html(html, config)
                except Exception as e:
                    results["parse_errors"] += 1
                    results["errors"].append({
                        "company": filing.company,
                        "accession": filing.accession_no,
                        "date": str(filing.filing_date),
                        "error": str(e),
                        "type": "parse"
                    })
                    continue

                # Get sections
                sections = doc.sections
                num_sections = len(sections)

                # Track section count distribution
                results["section_counts"][num_sections] = results["section_counts"].get(num_sections, 0) + 1

                if num_sections > 0:
                    results["success"] += 1

                    # Collect section info
                    section_info = []
                    for name, section in sections.items():
                        section_info.append({
                            "name": name,
                            "title": section.title,
                            "confidence": section.confidence,
                            "method": section.detection_method
                        })

                    results["filings_with_sections"].append({
                        "company": filing.company,
                        "accession": filing.accession_no,
                        "date": str(filing.filing_date),
                        "year": year,
                        "num_sections": num_sections,
                        "sections": section_info
                    })
                else:
                    results["no_sections"] += 1
                    results["filings_without_sections"].append({
                        "company": filing.company,
                        "accession": filing.accession_no,
                        "date": str(filing.filing_date),
                        "year": year
                    })

            except Exception as e:
                results["errors"].append({
                    "company": filing.company,
                    "accession": filing.accession_no,
                    "date": str(filing.filing_date),
                    "error": str(e),
                    "type": "unknown"
                })

    return results


def print_results(results: Dict[str, Any]) -> None:
    """Print detailed test results."""
    print(f"\n\n{'='*80}")
    print(f"RESULTS SUMMARY")
    print(f"{'='*80}\n")

    total = results["total"]
    if total == 0:
        print("❌ No filings tested")
        return

    success = results["success"]
    no_sections = results["no_sections"]
    parse_errors = results["parse_errors"]
    download_errors = results["download_errors"]

    success_rate = (success / total * 100) if total > 0 else 0

    print(f"Total filings tested: {total}")
    print(f"  ✅ With sections:      {success:4d} ({success_rate:5.1f}%)")
    print(f"  ⚠️  No sections:        {no_sections:4d} ({no_sections/total*100:5.1f}%)")
    print(f"  ❌ Parse errors:       {parse_errors:4d} ({parse_errors/total*100:5.1f}%)")
    print(f"  ❌ Download errors:    {download_errors:4d} ({download_errors/total*100:5.1f}%)")
    print(f"  ❌ Other errors:       {len(results['errors']) - parse_errors - download_errors:4d}")

    # Section count distribution
    print(f"\n{'='*80}")
    print(f"SECTION COUNT DISTRIBUTION")
    print(f"{'='*80}\n")

    section_counts = sorted(results["section_counts"].items())
    for count, num_filings in section_counts:
        pct = num_filings / total * 100
        bar = "█" * int(pct / 2)
        print(f"  {count:2d} sections: {num_filings:4d} ({pct:5.1f}%) {bar}")

    # Show sample successes
    if results["filings_with_sections"]:
        print(f"\n{'='*80}")
        print(f"SAMPLE SUCCESSES (showing first 5)")
        print(f"{'='*80}\n")

        for filing in results["filings_with_sections"][:5]:
            print(f"{filing['company']} ({filing['date']})")
            print(f"  Accession: {filing['accession']}")
            print(f"  Sections: {filing['num_sections']}")
            for section in filing['sections']:
                print(f"    • {section['name']}: {section['title']}")
                print(f"      confidence={section['confidence']:.2f}, method={section['method']}")
            print()

    # Show sample failures
    if results["filings_without_sections"]:
        print(f"\n{'='*80}")
        print(f"FILINGS WITHOUT SECTIONS (showing first 5)")
        print(f"{'='*80}\n")

        for filing in results["filings_without_sections"][:5]:
            print(f"{filing['company']} ({filing['date']})")
            print(f"  Accession: {filing['accession']}")
            print()

    # Show errors
    if results["errors"]:
        print(f"\n{'='*80}")
        print(f"ERRORS (showing first 5)")
        print(f"{'='*80}\n")

        for error in results["errors"][:5]:
            print(f"{error.get('company', 'Unknown')} ({error.get('date', 'Unknown')})")
            print(f"  Type: {error['type']}")
            print(f"  Error: {error['error']}")
            print()

    # Overall assessment
    print(f"\n{'='*80}")
    if success_rate >= 80:
        print(f"✅ EXCELLENT: {success_rate:.1f}% success rate")
        print(f"   Section detection working well across diverse filings")
    elif success_rate >= 60:
        print(f"⚠️  GOOD: {success_rate:.1f}% success rate")
        print(f"   Section detection working but with room for improvement")
    else:
        print(f"❌ NEEDS WORK: {success_rate:.1f}% success rate")
        print(f"   Section detection needs investigation")
    print(f"{'='*80}\n")


def main():
    """Run batch test with command line arguments."""
    parser = argparse.ArgumentParser(
        description="Batch test 8-K section detection across multiple filings"
    )
    parser.add_argument(
        "--years",
        type=int,
        nargs="+",
        default=[2020, 2023],
        help="Years to sample filings from (default: 2020 2023)"
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=20,
        help="Number of filings to sample per year (default: 20)"
    )

    args = parser.parse_args()

    results = test_8k_section_detection(
        years=args.years,
        sample_size=args.sample_size
    )

    print_results(results)


if __name__ == "__main__":
    main()
