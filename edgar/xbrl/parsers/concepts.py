"""
Shared XBRL concept definitions for balance types and deprecated normalization lists.

get_balance_type() reads the balance the us-gaap and srt taxonomies declare
from a bundled element table (edgar/xbrl/data/taxonomy_elements.parquet), for
the balance column of statement and facts DataFrames.

DEPRECATED: Static normalization concept lists (CONSISTENT_POSITIVE_CONCEPTS,
LEGITIMATE_NEGATIVE_CONCEPTS) are kept for historical reference but no longer used.
Testing confirmed that SEC XBRL instance data is already consistent across companies.
See Issue #463 analysis for details.
"""
from functools import lru_cache
from importlib import resources
from typing import Any, Dict, Optional

# =============================================================================
# DEPRECATED CONCEPT LISTS (No longer used as of Issue #463)
# =============================================================================
# These lists were created to work around perceived inconsistencies in XBRL data.
# Testing revealed that raw SEC instance data is ALREADY consistent across companies.
#
# Historical context:
# - Issues #290, #334, #451 reported negative values for expenses
# - Root cause: EdgarTools was misusing calculation weights for display logic
# - These lists fixed symptoms but not the actual problem
# - Issue #463 removed calculation weight application during parsing
# - Result: Raw values preserved as-is (matching SEC CompanyFacts API)
#
# Kept for historical reference and potential future use cases.
# =============================================================================

CONSISTENT_POSITIVE_CONCEPTS = {
    # Research and Development Expenses
    'us-gaap_ResearchAndDevelopmentExpense',
    'us_gaap_ResearchAndDevelopmentExpense',
    'ResearchAndDevelopmentExpense',

    # Selling, General & Administrative Expenses
    'us-gaap_SellingGeneralAndAdministrativeExpense',
    'us_gaap_SellingGeneralAndAdministrativeExpense',
    'SellingGeneralAndAdministrativeExpense',

    # General and Administrative Expenses (separate from SG&A)
    'us-gaap_GeneralAndAdministrativeExpense',
    'us_gaap_GeneralAndAdministrativeExpense',
    'GeneralAndAdministrativeExpense',

    # Selling Expenses
    'us-gaap_SellingExpense',
    'us_gaap_SellingExpense',
    'SellingExpense',

    # Marketing and Advertising Expenses
    'us-gaap_SellingAndMarketingExpense',
    'us_gaap_SellingAndMarketingExpense',
    'SellingAndMarketingExpense',
    'us-gaap_MarketingExpense',
    'us_gaap_MarketingExpense',
    'MarketingExpense',
    'us-gaap_AdvertisingExpense',
    'us_gaap_AdvertisingExpense',
    'AdvertisingExpense',

    # Share-based Compensation Expenses
    'us-gaap_AllocatedShareBasedCompensationExpense',
    'us_gaap_AllocatedShareBasedCompensationExpense',
    'AllocatedShareBasedCompensationExpense',
    'us-gaap_ShareBasedCompensationArrangementByShareBasedPaymentAwardExpenseRecognized',
    'us_gaap_ShareBasedCompensationArrangementByShareBasedPaymentAwardExpenseRecognized',
    'ShareBasedCompensationArrangementByShareBasedPaymentAwardExpenseRecognized',

    # Operating Expenses (general)
    'us-gaap_OperatingExpenses',
    'us_gaap_OperatingExpenses',
    'OperatingExpenses',

    # Professional Services Expenses
    'us-gaap_ProfessionalServiceFees',
    'us_gaap_ProfessionalServiceFees',
    'ProfessionalServiceFees',

    # Compensation and Benefits
    'us-gaap_LaborAndRelatedExpense',
    'us_gaap_LaborAndRelatedExpense',
    'LaborAndRelatedExpense',
    'us-gaap_EmployeeBenefitsExpense',
    'us_gaap_EmployeeBenefitsExpense',
    'EmployeeBenefitsExpense',

    # Cost of Revenue and Cost of Goods/Services Sold (Issue #290, #451)
    'us-gaap_CostOfRevenue',
    'us_gaap_CostOfRevenue',
    'CostOfRevenue',
    'us-gaap_CostOfGoodsAndServicesSold',
    'us_gaap_CostOfGoodsAndServicesSold',
    'CostOfGoodsAndServicesSold',
    'us-gaap_CostOfGoodsSold',
    'us_gaap_CostOfGoodsSold',
    'CostOfGoodsSold',
    'us-gaap_CostOfServices',
    'us_gaap_CostOfServices',
    'CostOfServices',

    # Income Tax Expense (Issue #451)
    'us-gaap_IncomeTaxExpenseBenefit',
    'us_gaap_IncomeTaxExpenseBenefit',
    'IncomeTaxExpenseBenefit',
    'us-gaap_IncomeTaxRecoveryExpense',
    'us_gaap_IncomeTaxRecoveryExpense',
    'IncomeTaxRecoveryExpense',

    # Cash Flow Statement - Financing Activities (cash outflows)
    # These represent uses of cash that should always be positive
    'us-gaap_PaymentsForRepurchaseOfCommonStock',
    'us_gaap_PaymentsForRepurchaseOfCommonStock',
    'PaymentsForRepurchaseOfCommonStock',
    'us-gaap_PaymentsOfDividends',
    'us_gaap_PaymentsOfDividends',
    'PaymentsOfDividends',
    'us-gaap_PaymentsOfDividendsCommonStock',
    'us_gaap_PaymentsOfDividendsCommonStock',
    'PaymentsOfDividendsCommonStock',
    'us-gaap_PaymentsOfDividendsPreferredStockAndPreferenceStock',
    'us_gaap_PaymentsOfDividendsPreferredStockAndPreferenceStock',
    'PaymentsOfDividendsPreferredStockAndPreferenceStock'
}

# DEPRECATED: Concepts that can legitimately be negative
# This list is no longer used but kept for historical reference.
LEGITIMATE_NEGATIVE_CONCEPTS = {
    # Interest expense/income that can be net negative
    'us-gaap_InterestIncomeExpenseNet',
    'us_gaap_InterestIncomeExpenseNet',
    'InterestIncomeExpenseNet',

    # Foreign exchange gains/losses
    'us-gaap_ForeignCurrencyTransactionGainLossBeforeTax',
    'us_gaap_ForeignCurrencyTransactionGainLossBeforeTax',
    'ForeignCurrencyTransactionGainLossBeforeTax',

    # Restructuring reversals/credits
    'us-gaap_RestructuringChargesAndReversals',
    'us_gaap_RestructuringChargesAndReversals',
    'RestructuringChargesAndReversals'
}

# =============================================================================
# BALANCE TYPES FROM THE BUNDLED TAXONOMY (Issues #463, #1728)
# =============================================================================
# A filing imports us-gaap and srt rather than declaring their elements, so the
# element catalog parsed from the filing has no balance for a standard concept.
# edgar/xbrl/data/taxonomy_elements.parquet carries the FASB declarations for
# every us-gaap (2011-2026) and srt (2018-2026) element, built by
# scripts/build_taxonomy_elements.py. It replaced a hand-written table of 124
# concepts, three of which the taxonomy contradicted (#1728).

TAXONOMY_ELEMENTS_FILE = 'taxonomy_elements.parquet'
_STANDARD_PREFIXES = ('us-gaap', 'srt')


@lru_cache(maxsize=1)
def _standard_elements():
    """The bundled us-gaap and srt declarations, one row per element."""
    import pandas as pd

    ref = resources.files('edgar.xbrl.data').joinpath(TAXONOMY_ELEMENTS_FILE)
    with resources.as_file(ref) as path:
        return pd.read_parquet(path, columns=['prefix', 'name', 'type', 'balance', 'period_type',
                                              'abstract', 'substitution_group',
                                              'enum_domain', 'enum_linkrole', 'enum_head_usable'])


@lru_cache(maxsize=1)
def _standard_balances() -> Dict[str, str]:
    """``prefix:name`` -> 'debit'/'credit' for every bundled element that has a balance."""
    df = _standard_elements()
    df = df[df['balance'].notna()]
    return {f"{prefix}:{name}": balance
            for prefix, name, balance in zip(df['prefix'].astype(str), df['name'], df['balance'].astype(str), strict=True)}


@lru_cache(maxsize=1)
def _standard_abstracts() -> Dict[str, bool]:
    """``prefix:name`` -> the declared abstract flag for every bundled element."""
    df = _standard_elements()
    return {f"{prefix}:{name}": bool(abstract)
            for prefix, name, abstract in zip(df['prefix'].astype(str), df['name'], df['abstract'], strict=True)}


def _standard_key(concept: str) -> str:
    """Normalize 'us-gaap_Cash', 'us_gaap_Cash' or bare 'Cash' to 'us-gaap:Cash'."""
    if concept.startswith('us_gaap'):
        concept = 'us-gaap' + concept[len('us_gaap'):]
    if ':' in concept:
        return concept
    prefix, sep, name = concept.partition('_')
    if sep and prefix in _STANDARD_PREFIXES:
        return f"{prefix}:{name}"
    # A bare local name is read as a us-gaap element.
    return f"us-gaap:{concept}"


def get_balance_type(concept: str) -> Optional[str]:
    """
    The balance a standard taxonomy declares for a concept.

    Reads the bundled us-gaap and srt element declarations and accepts the
    colon and underscore spellings of a concept. Returns None for a concept the
    taxonomy declares without a balance (share counts, the cash-flow totals) and
    for one it does not declare at all (company extensions, dei).

    Args:
        concept: The concept name (e.g., 'us-gaap:Revenues', 'us-gaap_Revenues' or 'us_gaap_Revenues')

    Returns:
        'debit', 'credit', or None

    Example:
        >>> get_balance_type('us-gaap:Cash')
        'debit'
        >>> get_balance_type('us-gaap_Revenues')
        'credit'
        >>> get_balance_type('us-gaap:CommonStockSharesOutstanding') is None
        True
    """
    if not concept:
        return None
    return _standard_balances().get(_standard_key(concept))


@lru_cache(maxsize=1)
def _standard_declarations() -> Dict[str, Dict[str, Any]]:
    """``prefix:name`` -> the element's bundled declaration, missing values as None."""
    df = _standard_elements()
    df = df.astype(object).where(df.notna(), None)
    return {f"{row['prefix']}:{row['name']}": row for row in df.to_dict('records')}


def get_standard_declaration(concept: str) -> Optional[Dict[str, Any]]:
    """
    The standard taxonomy's declaration of a us-gaap or srt concept.

    A dict with ``type``, ``balance``, ``period_type``, ``abstract``,
    ``substitution_group`` and, for an extensible enumeration, ``enum_domain``,
    ``enum_linkrole`` and ``enum_head_usable`` (the enum2 attributes verbatim;
    None where FASB declares no value), or None for a concept the bundled table
    does not declare (company extensions, dei).

    Example:
        >>> get_standard_declaration('us-gaap:Assets')['period_type']
        'instant'
    """
    if not concept:
        return None
    declaration = _standard_declarations().get(_standard_key(concept))
    return dict(declaration) if declaration is not None else None


def get_standard_abstract(concept: str) -> Optional[bool]:
    """
    Whether the standard taxonomy declares a concept abstract.

    Reads the bundled us-gaap and srt element declarations and accepts the colon
    and underscore spellings. Returns None for a concept the taxonomy does not
    declare (company extensions, dei), so the caller can tell "not abstract"
    from "not known".

    Example:
        >>> get_standard_abstract('us-gaap:AwardTypeAxis')
        True
        >>> get_standard_abstract('us-gaap_Revenues')
        False
        >>> get_standard_abstract('abc_CustomHeading') is None
        True
    """
    if not concept:
        return None
    return _standard_abstracts().get(_standard_key(concept))


def resolve_balance(declared: Optional[str], concept: str) -> Optional[str]:
    """
    A concept's balance: the filing's own declaration, else the standard taxonomy's.

    Every place that reports a balance (statement rows, the facts DataFrame,
    calculation nodes) goes through here, so they cannot disagree.
    """
    return declared or get_balance_type(concept)
