"""
Quick subset test of extractors on 10 filings (5x 424B5, 5x 424B3)
for rapid validation before full 35-filing run.
"""

import csv

from test_all_extractors import ExtractorTester

# Load sample dataset
sample_csv = '/Users/dwight/PycharmProjects/edgartools/docs-internal/research/sec-filings/forms/424b/sample_dataset.csv'
output_dir = '/Users/dwight/PycharmProjects/edgartools/docs-internal/research/sec-filings/forms/424b/results'

# Create subset: first 5 of each form type
samples = []
with open(sample_csv, 'r') as f:
    reader = csv.DictReader(f)
    all_samples = list(reader)

b5_samples = [s for s in all_samples if s['form'] == '424B5'][:5]
b3_samples = [s for s in all_samples if s['form'] == '424B3'][:5]

subset_samples = b5_samples + b3_samples

# Save subset to temp CSV
subset_csv = '/tmp/subset_424b_samples.csv'
with open(subset_csv, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=all_samples[0].keys())
    writer.writeheader()
    writer.writerows(subset_samples)

print(f"Testing subset of {len(subset_samples)} filings (5x 424B5, 5x 424B3)")

# Run test
tester = ExtractorTester(subset_csv)
tester.run_full_test(output_dir + '/subset')
