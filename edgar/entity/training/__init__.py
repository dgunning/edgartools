"""
Entity Training Package

Tools for learning financial statement concept mappings from SEC filings.

This package provides scripts to:
- Learn canonical concept mappings from a diverse set of companies
- Learn industry-specific concept extensions
- Deploy learned mappings to the entity data directory
- View and analyze learning results

Usage:
    # Run canonical learning
    python -m edgar.entity.training.run_learning --companies 100

    # Run industry-specific learning
    python -m edgar.entity.training.run_industry_learning --industry banking --companies 150

    # Deploy learnings to entity data
    python -m edgar.entity.training.deploy --canonical
    python -m edgar.entity.training.deploy --industry banking

    # View learning results
    python -m edgar.entity.training.view
"""

from pathlib import Path

# Default output directory (relative to project root, untracked)
DEFAULT_OUTPUT_DIR = Path("training/output")

# Industry definitions with SIC ranges
INDUSTRIES = {
    'banking': {
        'name': 'Banking & Financial Services',
        'sic_ranges': [(6020, 6029)],
        'min_companies': 50,
    },
    'tech': {
        'name': 'Technology & Software',
        'sic_ranges': [(7370, 7379), (3570, 3579)],
        'min_companies': 50,
    },
    'healthcare': {
        'name': 'Healthcare & Pharmaceuticals',
        'sic_ranges': [(2833, 2836), (8000, 8099)],
        'min_companies': 50,
    },
    'energy': {
        'name': 'Energy & Oil/Gas',
        'sic_ranges': [(1300, 1399)],
        'min_companies': 50,
    },
    'insurance': {
        'name': 'Insurance',
        'sic_ranges': [(6300, 6399)],
        'min_companies': 30,
    },
    'retail': {
        'name': 'Retail Trade',
        'sic_ranges': [(5200, 5999)],
        'min_companies': 50,
    },
    'realestate': {
        'name': 'Real Estate & REITs',
        'sic_ranges': [(6500, 6553), (6798, 6798)],
        'min_companies': 50,
    },
    'utilities': {
        'name': 'Utilities',
        'sic_ranges': [(4910, 4941)],
        'min_companies': 50,
    },
    'consumergoods': {
        'name': 'Consumer Goods',
        'sic_ranges': [(2000, 2399)],
        'min_companies': 50,
    },
    'telecom': {
        'name': 'Telecommunications',
        'sic_ranges': [(4810, 4899)],
        'min_companies': 30,
    },
    'transportation': {
        'name': 'Transportation',
        'sic_ranges': [(4000, 4799)],
        'min_companies': 50,
    },
    'aerospace': {
        'name': 'Aerospace & Defense',
        'sic_ranges': [(3720, 3729), (3760, 3769)],
        'min_companies': 30,
    },
    'hospitality': {
        'name': 'Hospitality',
        'sic_ranges': [(7010, 7041)],
        'min_companies': 30,
    },
    'mining': {
        'name': 'Mining & Materials',
        'sic_ranges': [(1000, 1299), (1400, 1499)],
        'min_companies': 50,
    },
    'automotive': {
        'name': 'Automotive',
        'sic_ranges': [(3710, 3716)],
        'min_companies': 30,
    },
}

# Statement types to learn
STATEMENT_TYPES = [
    'BalanceSheet',
    'IncomeStatement',
    'CashFlowStatement',
    'StatementOfEquity',
    'ComprehensiveIncome'
]


def get_output_dir(output_path: str = None) -> Path:
    """
    Get the output directory path, creating it if necessary.

    Args:
        output_path: Optional custom output path. If None, uses DEFAULT_OUTPUT_DIR.

    Returns:
        Path to the output directory
    """
    if output_path:
        output_dir = Path(output_path)
    else:
        output_dir = DEFAULT_OUTPUT_DIR

    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def get_industry_output_dir(output_path: str = None) -> Path:
    """
    Get the industry-specific output directory.

    Args:
        output_path: Optional custom output path.

    Returns:
        Path to the industries output subdirectory
    """
    base_dir = get_output_dir(output_path)
    industry_dir = base_dir / "industries"
    industry_dir.mkdir(parents=True, exist_ok=True)
    return industry_dir


def get_entity_data_dir() -> Path:
    """Get the entity data directory for deployed mappings."""
    return Path(__file__).parent.parent / "data"


def get_industry_extensions_dir() -> Path:
    """Get the industry extensions directory for deployed industry mappings."""
    extensions_dir = get_entity_data_dir() / "industry_extensions"
    extensions_dir.mkdir(parents=True, exist_ok=True)
    return extensions_dir
