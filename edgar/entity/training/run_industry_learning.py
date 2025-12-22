#!/usr/bin/env python3
"""
Industry-Specific Financial Statement Concept Learning

This script learns industry-specific concepts by analyzing SEC filings
from companies within a specific SIC code range.

Usage:
    python -m edgar.entity.training.run_industry_learning --industry banking --companies 150
    python -m edgar.entity.training.run_industry_learning --industry tech --companies 200
    python -m edgar.entity.training.run_industry_learning --all --companies 150

Industries:
    banking     - SIC 6020-6029 (Commercial Banks)
    tech        - SIC 7370-7379, 3570-3579 (Software, Hardware)
    healthcare  - SIC 2833-2836, 8000-8099 (Pharma, Health Services)
    energy      - SIC 1300-1399, 4900-4949 (Oil/Gas, Utilities)
    insurance   - SIC 6300-6399 (Insurance)
    retail      - SIC 5200-5999 (Retail Trade)
"""

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from . import INDUSTRIES, STATEMENT_TYPES, get_industry_output_dir
from .run_learning import ConceptLearner

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_industry_companies(industry: str, max_companies: int = 200) -> List[str]:
    """
    Get list of tickers for companies in the specified industry.

    Args:
        industry: Industry key (banking, tech, etc.)
        max_companies: Maximum number of companies to return

    Returns:
        List of ticker symbols
    """
    from edgar.reference.company_subsets import get_companies_by_industry

    if industry not in INDUSTRIES:
        raise ValueError(f"Unknown industry: {industry}. Available: {list(INDUSTRIES.keys())}")

    industry_info = INDUSTRIES[industry]
    all_companies = []

    # Get companies for each SIC range
    for sic_start, sic_end in industry_info['sic_ranges']:
        try:
            df = get_companies_by_industry(sic_range=(sic_start, sic_end))
            if df is not None and not df.empty:
                # Filter for companies with tickers
                if 'ticker' in df.columns:
                    tickers = df['ticker'].dropna().tolist()
                    all_companies.extend(tickers)
        except Exception as e:
            logger.warning(f"Error getting companies for SIC {sic_start}-{sic_end}: {e}")

    # Remove duplicates and limit
    unique_tickers = list(dict.fromkeys(all_companies))  # Preserves order
    return unique_tickers[:max_companies]


def run_industry_learning(industry: str, max_companies: int, output_dir: Path,
                          min_occurrence: float = 0.30) -> dict:
    """
    Run concept learning for a specific industry.

    Args:
        industry: Industry key
        max_companies: Maximum companies to analyze
        output_dir: Output directory for results
        min_occurrence: Minimum occurrence rate threshold

    Returns:
        Summary dictionary with results
    """
    # ConceptLearner and STATEMENT_TYPES already imported at module level

    logger.info(f"Starting {industry} industry learning...")
    logger.info(f"Parameters: max_companies={max_companies}, min_occurrence={min_occurrence}")

    # Get industry companies
    tickers = get_industry_companies(industry, max_companies)
    logger.info(f"Found {len(tickers)} companies in {industry} industry")

    if len(tickers) < INDUSTRIES[industry]['min_companies']:
        logger.warning(
            f"Only {len(tickers)} companies found, minimum recommended is "
            f"{INDUSTRIES[industry]['min_companies']}"
        )

    # Initialize learner
    learner = ConceptLearner(min_occurrence_rate=min_occurrence)

    # Process companies
    for ticker in tickers:
        try:
            learner.process_company(ticker)
        except Exception as e:
            logger.error(f"Error processing {ticker}: {e}")

    logger.info(
        f"Processed {learner.companies_processed} companies, "
        f"{learner.successful_companies} successful"
    )

    # Generate industry extension output
    extension = generate_industry_extension(
        learner, industry, min_occurrence
    )

    # Save outputs
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save industry extension
    extension_file = output_dir / f"{industry}_extension.json"
    with open(extension_file, 'w') as f:
        json.dump(extension, f, indent=2)
    logger.info(f"Saved industry extension to {extension_file}")

    # Generate summary
    summary = {
        'industry': industry,
        'industry_name': INDUSTRIES[industry]['name'],
        'timestamp': datetime.now().isoformat(),
        'companies_analyzed': learner.companies_processed,
        'successful_companies': learner.successful_companies,
        'total_observations': learner.total_observations,
        'min_occurrence_rate': min_occurrence,
        'concepts_by_statement': {},
    }

    for stmt_type in STATEMENT_TYPES:
        if stmt_type in extension:
            summary['concepts_by_statement'][stmt_type] = len(
                extension[stmt_type].get('nodes', {})
            )

    # Save summary
    summary_file = output_dir / f"{industry}_learning_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)

    return summary


def generate_industry_extension(learner, industry: str,
                                min_occurrence: float) -> dict:
    """
    Generate industry extension from learned concepts.

    Filters to only include concepts that:
    1. Meet occurrence threshold within the industry
    2. Are NOT already in canonical (general) trees

    Args:
        learner: ConceptLearner with processed data
        industry: Industry key
        min_occurrence: Minimum occurrence rate

    Returns:
        Industry extension dictionary
    """
    from edgar.entity.mappings_loader import load_virtual_trees
    # STATEMENT_TYPES already imported at module level

    # Load canonical trees to exclude concepts already there
    canonical_trees = load_virtual_trees()
    canonical_concepts = set()
    for stmt_type, tree in canonical_trees.items():
        canonical_concepts.update(tree.get('nodes', {}).keys())

    logger.info(f"Excluding {len(canonical_concepts)} canonical concepts")

    # Build extension
    extension = {
        'metadata': {
            'industry': industry,
            'industry_name': INDUSTRIES[industry]['name'],
            'sic_ranges': INDUSTRIES[industry]['sic_ranges'],
            'companies_analyzed': learner.successful_companies,
            'min_occurrence_rate': min_occurrence,
            'generated': datetime.now().isoformat(),
        }
    }

    # Process each statement type
    for stmt_type in STATEMENT_TYPES:
        nodes = {}

        for concept_key, stats in learner.concept_stats.items():
            if stats.statement_type != stmt_type:
                continue

            # Extract clean concept name (remove :StatementType suffix if present)
            # The learner uses keys like "Assets:BalanceSheet"
            clean_concept = stats.concept  # Use the concept from stats, not the key

            # Calculate occurrence rate within this industry
            occurrence_rate = len(stats.company_ciks) / learner.successful_companies \
                if learner.successful_companies > 0 else 0

            if occurrence_rate < min_occurrence:
                continue

            # Skip if already in canonical (check clean concept name)
            if clean_concept in canonical_concepts:
                continue

            # Get most common label and parent
            most_common_label = max(stats.labels.items(), key=lambda x: x[1])[0] \
                if stats.labels else clean_concept
            most_common_parent = max(stats.parents.items(), key=lambda x: x[1])[0] \
                if stats.parents else None

            # Calculate average depth
            avg_depth = sum(stats.depths) / len(stats.depths) if stats.depths else 0

            # Use clean concept name as key (not the compound key with statement type)
            nodes[clean_concept] = {
                'concept': clean_concept,
                'label': most_common_label,
                'parent': most_common_parent,
                'depth': avg_depth,
                'occurrence_rate': round(occurrence_rate, 4),
                'is_abstract': stats.is_abstract_count > len(stats.depths) / 2,
                'is_total': stats.is_total_count > len(stats.depths) / 2,
                'children': [],  # Will be populated if needed
            }

        if nodes:
            extension[stmt_type] = {
                'statement_type': stmt_type,
                'nodes': nodes,
            }
            logger.info(f"  {stmt_type}: {len(nodes)} industry-specific concepts")

    return extension


def main():
    parser = argparse.ArgumentParser(
        description='Learn industry-specific financial statement concepts'
    )
    parser.add_argument(
        '--industry', '-i',
        type=str,
        required=False,
        choices=list(INDUSTRIES.keys()),
        help='Industry to analyze'
    )
    parser.add_argument(
        '--companies', '-c',
        type=int,
        default=150,
        help='Maximum number of companies to analyze (default: 150)'
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='Output directory (default: training/output/industries)'
    )
    parser.add_argument(
        '--min-occurrence', '-m',
        type=float,
        default=0.30,
        help='Minimum occurrence rate threshold (default: 0.30)'
    )
    parser.add_argument(
        '--list-industries',
        action='store_true',
        help='List available industries and exit'
    )
    parser.add_argument(
        '--all', '-a',
        action='store_true',
        help='Train all industries sequentially'
    )

    args = parser.parse_args()

    if args.list_industries:
        print("\nAvailable Industries:")
        print("-" * 60)
        for key, info in INDUSTRIES.items():
            sic_str = ', '.join(f"{s}-{e}" for s, e in info['sic_ranges'])
            print(f"  {key:12} - {info['name']}")
            print(f"               SIC: {sic_str}")
        return 0

    if not args.industry and not args.all:
        parser.error("--industry or --all is required (use --list-industries to see options)")

    output_dir = Path(args.output) if args.output else get_industry_output_dir()

    # Determine which industries to process
    if args.all:
        industries_to_process = list(INDUSTRIES.keys())
        print("\n" + "=" * 60)
        print("TRAINING ALL INDUSTRIES")
        print("=" * 60)
        print(f"Industries: {', '.join(industries_to_process)}")
        print(f"Companies per industry: {args.companies}")
        print(f"Min occurrence: {args.min_occurrence}")
        print("=" * 60 + "\n")
    else:
        industries_to_process = [args.industry]

    all_summaries = {}
    failed = []

    for industry in industries_to_process:
        try:
            summary = run_industry_learning(
                industry=industry,
                max_companies=args.companies,
                output_dir=output_dir,
                min_occurrence=args.min_occurrence
            )
            all_summaries[industry] = summary

            print("\n" + "-" * 60)
            print(f"COMPLETED: {industry.upper()}")
            print("-" * 60)
            print(f"Companies analyzed: {summary['successful_companies']}")
            print(f"Concepts learned: {sum(summary['concepts_by_statement'].values())}")
            for stmt, count in summary['concepts_by_statement'].items():
                print(f"  {stmt}: {count}")

        except Exception as e:
            logger.error(f"Learning failed for {industry}: {e}")
            failed.append(industry)

    # Final summary
    print("\n" + "=" * 60)
    if args.all:
        print("ALL INDUSTRIES COMPLETE")
    else:
        print(f"INDUSTRY LEARNING COMPLETE: {args.industry.upper()}")
    print("=" * 60)

    if all_summaries:
        print("\nSummary:")
        total_concepts = 0
        for industry, summary in all_summaries.items():
            concepts = sum(summary['concepts_by_statement'].values())
            total_concepts += concepts
            print(f"  {industry:12} - {summary['successful_companies']:3} companies, {concepts:3} concepts")

        if args.all:
            print(f"\nTotal: {len(all_summaries)} industries, {total_concepts} concepts")

    if failed:
        print(f"\nFailed: {', '.join(failed)}")

    print(f"\nOutput saved to: {output_dir}")
    print("=" * 60)

    return 1 if failed else 0


if __name__ == '__main__':
    exit(main())
