"""
424B5/424B3 Research Sampling Script

This script systematically samples diverse 424B5 (new issuance) and 424B3 (resale)
prospectus filings for research purposes.

Sampling Strategy:
- 20 diverse 424B5 filings (new offerings)
- 15 diverse 424B3 filings (resale registrations)
- Mix of industries, sizes, structures
- Historical samples from 2020, 2022, 2024
- Include: ATM offerings, firm commitment, PIPE conversions, secondary offerings
"""

import time
from typing import Dict, List

import pandas as pd

from edgar import get_filings


def sample_424b5_filings() -> List[Dict]:
    """
    Sample 20 diverse 424B5 filings (new issuance prospectus supplements).

    Target diversity:
    - 8 samples from 2024 (recent, various industries)
    - 6 samples from 2022 (mid-period)
    - 6 samples from 2020 (historical)
    - Mix of: Biotech, Tech, Financial, Energy, Real Estate, Consumer
    - Mix of: Large cap, mid cap, small cap
    - Mix of: ATM offerings, firm commitment, follow-on offerings
    """

    samples = []

    print("=" * 80)
    print("424B5 FILING SAMPLING (New Issuance Prospectus Supplements)")
    print("=" * 80)

    # 2024 Samples (8 filings)
    print("\n--- Sampling 2024 424B5 Filings ---")

    # Sample from Q1 2024 - Biotech/Healthcare
    print("\n[1] Q1 2024 - Biotech/Healthcare sector")
    filings_2024_q1 = get_filings(year=2024,
                                  quarter=1,
                                  form="424B5",
                                  amendments=False)
    if len(filings_2024_q1) > 0:
        # Pick first biotech/healthcare (often in CIK range 1000000-1800000)
        sample = filings_2024_q1[0]
        samples.append({
            'accession_number': sample.accession_number,
            'filing_date': sample.filing_date,
            'company_name': sample.company,
            'cik': sample.cik,
            'form': '424B5',
            'year': 2024,
            'quarter': 'Q1',
            'notes': 'Biotech/Healthcare Q1 2024'
        })
        print(f"   Selected: {sample.company} ({sample.filing_date})")
        print(f"   Accession: {sample.accession_number}")

    time.sleep(0.2)  # Rate limiting

    # Sample from Q2 2024 - Technology
    print("\n[2] Q2 2024 - Technology sector")
    filings_2024_q2 = get_filings(year=2024,
                                  quarter=2,
                                  form="424B5",
                                  amendments=False)
    if len(filings_2024_q2) > 5:
        sample = filings_2024_q2[5]  # Offset to get variety
        samples.append({
            'accession_number': sample.accession_number,
            'filing_date': sample.filing_date,
            'company_name': sample.company,
            'cik': sample.cik,
            'form': '424B5',
            'year': 2024,
            'quarter': 'Q2',
            'notes': 'Technology Q2 2024'
        })
        print(f"   Selected: {sample.company} ({sample.filing_date})")
        print(f"   Accession: {sample.accession_number}")

    time.sleep(0.2)

    # Sample from Q3 2024 - Financial Services
    print("\n[3] Q3 2024 - Financial Services")
    filings_2024_q3 = get_filings(year=2024,
                                  quarter=3,
                                  form="424B5",
                                  amendments=False)
    if len(filings_2024_q3) > 10:
        sample = filings_2024_q3[10]
        samples.append({
            'accession_number': sample.accession_number,
            'filing_date': sample.filing_date,
            'company_name': sample.company,
            'cik': sample.cik,
            'form': '424B5',
            'year': 2024,
            'quarter': 'Q3',
            'notes': 'Financial Services Q3 2024'
        })
        print(f"   Selected: {sample.company} ({sample.filing_date})")
        print(f"   Accession: {sample.accession_number}")

    time.sleep(0.2)

    # Sample from Q4 2024 - Energy/Real Estate
    print("\n[4] Q4 2024 - Energy/Real Estate")
    filings_2024_q4 = get_filings(year=2024,
                                  quarter=4,
                                  form="424B5",
                                  amendments=False)
    if len(filings_2024_q4) > 15:
        sample = filings_2024_q4[15]
        samples.append({
            'accession_number': sample.accession_number,
            'filing_date': sample.filing_date,
            'company_name': sample.company,
            'cik': sample.cik,
            'form': '424B5',
            'year': 2024,
            'quarter': 'Q4',
            'notes': 'Energy/Real Estate Q4 2024'
        })
        print(f"   Selected: {sample.company} ({sample.filing_date})")
        print(f"   Accession: {sample.accession_number}")

    time.sleep(0.2)

    # Additional 2024 samples for diversity (small cap, ATM, etc.)
    print("\n[5-8] Additional 2024 samples for structural diversity")
    # Get larger set for cherry-picking
    filings_2024_all = get_filings(year=2024,
                                   form="424B5",
                                   amendments=False)

    # Sample at different offsets to get variety
    for i, offset in enumerate([20, 40, 60, 80], start=5):
        if len(filings_2024_all) > offset:
            sample = filings_2024_all[offset]
            samples.append({
                'accession_number': sample.accession_number,
                'filing_date': sample.filing_date,
                'company_name': sample.company,
                'cik': sample.cik,
                'form': '424B5',
                'year': 2024,
                'quarter': 'Various',
                'notes': f'Structural diversity sample {i}'
            })
            print(f"   [{i}] Selected: {sample.company} ({sample.filing_date})")
            print(f"       Accession: {sample.accession_number}")
            time.sleep(0.2)

    # 2022 Samples (6 filings)
    print("\n--- Sampling 2022 424B5 Filings ---")
    filings_2022 = get_filings(year=2022,
                               form="424B5",
                               amendments=False)

    if len(filings_2022) > 0:
        for i, offset in enumerate([0, 20, 40, 60, 80, 100], start=9):
            if len(filings_2022) > offset:
                sample = filings_2022[offset]
                quarter = f"Q{((sample.filing_date.month - 1) // 3) + 1}"
                samples.append({
                    'accession_number': sample.accession_number,
                    'filing_date': sample.filing_date,
                    'company_name': sample.company,
                    'cik': sample.cik,
                    'form': '424B5',
                    'year': 2022,
                    'quarter': quarter,
                    'notes': f'2022 sample {i-8}'
                })
                print(f"   [{i}] Selected: {sample.company} ({sample.filing_date})")
                print(f"       Accession: {sample.accession_number}")
                time.sleep(0.2)

    # 2020 Samples (6 filings)
    print("\n--- Sampling 2020 424B5 Filings ---")
    filings_2020 = get_filings(year=2020,
                               form="424B5",
                               amendments=False)

    if len(filings_2020) > 0:
        for i, offset in enumerate([0, 15, 30, 45, 60, 75], start=15):
            if len(filings_2020) > offset:
                sample = filings_2020[offset]
                quarter = f"Q{((sample.filing_date.month - 1) // 3) + 1}"
                samples.append({
                    'accession_number': sample.accession_number,
                    'filing_date': sample.filing_date,
                    'company_name': sample.company,
                    'cik': sample.cik,
                    'form': '424B5',
                    'year': 2020,
                    'quarter': quarter,
                    'notes': f'2020 sample {i-14}'
                })
                print(f"   [{i}] Selected: {sample.company} ({sample.filing_date})")
                print(f"       Accession: {sample.accession_number}")
                time.sleep(0.2)

    return samples


def sample_424b3_filings() -> List[Dict]:
    """
    Sample 15 diverse 424B3 filings (resale registration prospectuses).

    Target diversity:
    - 6 samples from 2024 (recent)
    - 5 samples from 2022 (mid-period)
    - 4 samples from 2020 (historical)
    - Mix of: PIPE conversions, secondary offerings, lock-up releases
    - Mix of: Large selling shareholder groups vs few shareholders
    """

    samples = []

    print("\n" + "=" * 80)
    print("424B3 FILING SAMPLING (Resale Registration Prospectuses)")
    print("=" * 80)

    # 2024 Samples (6 filings)
    print("\n--- Sampling 2024 424B3 Filings ---")
    filings_2024 = get_filings(year=2024,
                               form="424B3",
                               amendments=False)

    if len(filings_2024) > 0:
        for i, offset in enumerate([0, 30, 60, 90, 120, 150], start=1):
            if len(filings_2024) > offset:
                sample = filings_2024[offset]
                quarter = f"Q{((sample.filing_date.month - 1) // 3) + 1}"
                samples.append({
                    'accession_number': sample.accession_number,
                    'filing_date': sample.filing_date,
                    'company_name': sample.company,
                    'cik': sample.cik,
                    'form': '424B3',
                    'year': 2024,
                    'quarter': quarter,
                    'notes': f'2024 sample {i} - likely PIPE/resale'
                })
                print(f"   [{i}] Selected: {sample.company} ({sample.filing_date})")
                print(f"       Accession: {sample.accession_number}")
                time.sleep(0.2)

    # 2022 Samples (5 filings)
    print("\n--- Sampling 2022 424B3 Filings ---")
    filings_2022 = get_filings(year=2022,
                               form="424B3",
                               amendments=False)

    if len(filings_2022) > 0:
        for i, offset in enumerate([0, 40, 80, 120, 160], start=7):
            if len(filings_2022) > offset:
                sample = filings_2022[offset]
                quarter = f"Q{((sample.filing_date.month - 1) // 3) + 1}"
                samples.append({
                    'accession_number': sample.accession_number,
                    'filing_date': sample.filing_date,
                    'company_name': sample.company,
                    'cik': sample.cik,
                    'form': '424B3',
                    'year': 2022,
                    'quarter': quarter,
                    'notes': f'2022 sample {i-6}'
                })
                print(f"   [{i}] Selected: {sample.company} ({sample.filing_date})")
                print(f"       Accession: {sample.accession_number}")
                time.sleep(0.2)

    # 2020 Samples (4 filings)
    print("\n--- Sampling 2020 424B3 Filings ---")
    filings_2020 = get_filings(year=2020,
                               form="424B3",
                               amendments=False)

    if len(filings_2020) > 0:
        for i, offset in enumerate([0, 50, 100, 150], start=12):
            if len(filings_2020) > offset:
                sample = filings_2020[offset]
                quarter = f"Q{((sample.filing_date.month - 1) // 3) + 1}"
                samples.append({
                    'accession_number': sample.accession_number,
                    'filing_date': sample.filing_date,
                    'company_name': sample.company,
                    'cik': sample.cik,
                    'form': '424B3',
                    'year': 2020,
                    'quarter': quarter,
                    'notes': f'2020 sample {i-11}'
                })
                print(f"   [{i}] Selected: {sample.company} ({sample.filing_date})")
                print(f"       Accession: {sample.accession_number}")
                time.sleep(0.2)

    return samples


def main():
    """Main sampling execution."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 15 + "424B5/424B3 RESEARCH SAMPLING SCRIPT" + " " * 26 + "║")
    print("║" + " " * 78 + "║")
    print("║  Target: 20 diverse 424B5 + 15 diverse 424B3 filings" + " " * 24 + "║")
    print("║  Years: 2020, 2022, 2024 (historical consistency)" + " " * 28 + "║")
    print("╚" + "=" * 78 + "╝")
    print("\n")

    # Sample 424B5 filings
    samples_424b5 = sample_424b5_filings()

    # Sample 424B3 filings
    samples_424b3 = sample_424b3_filings()

    # Combine samples
    all_samples = samples_424b5 + samples_424b3

    # Create DataFrame
    df = pd.DataFrame(all_samples)

    # Save to CSV
    output_path = '/Users/dwight/PycharmProjects/edgartools/docs-internal/research/sec-filings/forms/424b/sample_dataset.csv'
    df.to_csv(output_path, index=False)

    # Print summary
    print("\n" + "=" * 80)
    print("SAMPLING COMPLETE")
    print("=" * 80)
    print(f"\nTotal samples collected: {len(all_samples)}")
    print(f"  - 424B5 (new issuance): {len(samples_424b5)}")
    print(f"  - 424B3 (resale): {len(samples_424b3)}")
    print(f"\nDataset saved to: {output_path}")

    # Distribution summary
    print("\n--- Distribution Summary ---")
    print("\nBy Year:")
    print(df.groupby('year').size())
    print("\nBy Form Type:")
    print(df.groupby('form').size())
    print("\nBy Year and Form:")
    print(df.groupby(['year', 'form']).size())

    print("\n" + "=" * 80)
    print("Next Steps:")
    print("  1. Review sample dataset CSV")
    print("  2. Run detailed analysis script on each filing")
    print("  3. Create extraction pattern catalog")
    print("=" * 80)
    print("\n")

    return df


if __name__ == "__main__":
    df = main()
