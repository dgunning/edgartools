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
from typing import Optional

# Default output directory (relative to project root, untracked)
DEFAULT_OUTPUT_DIR = Path("training/output")

# Default occurrence threshold for learning
DEFAULT_OCCURRENCE_THRESHOLD = 0.30

# Industry definitions with SIC ranges and occurrence thresholds
# Thresholds are based on industry homogeneity analysis:
# - Homogeneous industries (similar concepts across companies): 25-30%
# - Heterogeneous industries (diverse sub-sectors): 18-22%
# - Small sample industries (<50 companies): 20-22%
INDUSTRIES = {
    'aerospace': {
        'name': 'Aerospace & Defense',
        'sic_ranges': [(3720, 3729), (3760, 3769)],
        'min_companies': 30,
        'default_threshold': 0.22,  # Small sample
    },
    'automotive': {
        'name': 'Automotive',
        'sic_ranges': [(3710, 3716)],
        'min_companies': 30,
        'default_threshold': 0.18,  # Heterogeneous
    },
    'banking': {
        'name': 'Banking & Financial Services',
        'sic_ranges': [(6020, 6099)],  # Expanded: savings banks, credit unions, mortgage banks
        'min_companies': 50,
        'default_threshold': 0.25,  # Lowered slightly for broader range
    },
    'consumergoods': {
        'name': 'Consumer Goods',
        'sic_ranges': [(2000, 2399)],
        'min_companies': 50,
        'default_threshold': 0.22,  # Moderate diversity
    },
    'energy': {
        'name': 'Energy & Oil/Gas',
        'sic_ranges': [(1300, 1399), (2911, 2911), (4610, 4619)],  # Expanded: refining, pipelines
        'min_companies': 50,
        'default_threshold': 0.20,  # Lowered for broader range
    },
    'healthcare': {
        'name': 'Healthcare & Pharmaceuticals',
        'sic_ranges': [(2833, 2836), (8000, 8099), (3841, 3845)],  # Expanded: medical devices
        'min_companies': 50,
        'default_threshold': 0.22,  # Lowered for broader range
    },
    'hospitality': {
        'name': 'Hospitality',
        'sic_ranges': [(7010, 7041)],
        'min_companies': 30,
        'default_threshold': 0.20,  # Small sample (22 companies)
    },
    'insurance': {
        'name': 'Insurance',
        'sic_ranges': [(6300, 6399)],
        'min_companies': 30,
        'default_threshold': 0.25,  # Homogeneous (50% avg rate)
    },
    'investment_companies': {
        'name': 'Investment Companies & Asset Management',
        'sic_ranges': [(6720, 6799)],
        'min_companies': 50,
        'default_threshold': 0.18,  # Heterogeneous
    },
    'mining': {
        'name': 'Mining & Materials',
        'sic_ranges': [(1000, 1299), (1400, 1499)],
        'min_companies': 50,
        'default_threshold': 0.22,  # Moderate diversity
    },
    'realestate': {
        'name': 'Real Estate & REITs',
        'sic_ranges': [(6500, 6553), (6798, 6798)],
        'min_companies': 50,
        'default_threshold': 0.18,  # Heterogeneous
    },
    'retail': {
        'name': 'Retail Trade',
        'sic_ranges': [(5200, 5999)],
        'min_companies': 50,
        'default_threshold': 0.18,  # Heterogeneous
    },
    'tech': {
        'name': 'Technology & Software',
        'sic_ranges': [(7370, 7379), (3570, 3579)],
        'min_companies': 50,
        'default_threshold': 0.22,  # Moderate diversity
    },
    'telecom': {
        'name': 'Telecommunications',
        'sic_ranges': [(4810, 4899)],
        'min_companies': 30,
        'default_threshold': 0.18,  # Heterogeneous
    },
    'transportation': {
        'name': 'Transportation',
        'sic_ranges': [(4000, 4799)],
        'min_companies': 50,
        'default_threshold': 0.22,  # Small sample + moderate
    },
    'utilities': {
        'name': 'Utilities',
        'sic_ranges': [(4910, 4941)],
        'min_companies': 50,
        'default_threshold': 0.22,  # Moderate diversity
    },
    'securities': {
        'name': 'Securities, Broker-Dealers & Asset Management',
        'sic_ranges': [(6200, 6299)],  # Expanded to include full broker-dealer range
        'min_companies': 50,
        'default_threshold': 0.20,  # Heterogeneous (brokers, advisors, ETFs)
    },
    'semiconductors': {
        'name': 'Semiconductors',
        'sic_ranges': [(3674, 3674)],  # Semiconductors and related devices
        'min_companies': 30,
        'default_threshold': 0.22,  # Moderate diversity (fabless, IDM, foundry)
    },
    'payment_networks': {
        'name': 'Payment Networks & Processors',
        # Note: SIC codes don't map cleanly to payment networks
        # (scattered across 7389, 6099, 6199), so we use a curated ticker list
        'tickers': [
            # Card Networks
            'V',      # Visa
            'MA',     # Mastercard
            'AXP',    # American Express
            'DFS',    # Discover Financial
            # Payment Processors
            'PYPL',   # PayPal
            'SQ',     # Block (Square)
            'FIS',    # Fidelity National Information Services
            'FISV',   # Fiserv
            'GPN',    # Global Payments
            'ADYEY',  # Adyen (ADR)
            # Payroll & Business Payments
            'PAYX',   # Paychex
            'ADP',    # Automatic Data Processing
            'BILL',   # Bill.com
            # Money Transfer
            'WU',     # Western Union
            'MGI',    # MoneyGram
            # Buy Now Pay Later / Fintech
            'AFRM',   # Affirm
            'FOUR',   # Shift4 Payments
            'RPAY',   # Repay Holdings
            'PAYO',   # Payoneer
            'TOST',   # Toast
            # Card Issuers with Payment Focus
            'COF',    # Capital One
            'SYF',    # Synchrony Financial
            # Digital/Crypto Payments
            'COIN',   # Coinbase
            # Regional Payment Processors
            'EVTC',   # Evertec
            'FLYW',   # Flywire
            'RELY',   # Remitly
            'PSFE',   # Paysafe
        ],
        'min_companies': 20,
        'default_threshold': 0.22,  # Moderate diversity across payment types
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


def get_output_dir(output_path: Optional[str] = None) -> Path:
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


def get_industry_output_dir(output_path: Optional[str] = None) -> Path:
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
